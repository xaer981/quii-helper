import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from quii_helper.media.audio.recording import AudioRecording
from quii_helper.media.frames.assembler import AssembledH264Stream
from quii_helper.media.h264.io import writer
from quii_helper.media.h264.io.writer import _write_stream_bytes
from quii_helper.support.errors import MediaRenderError
from tests.media.audio.test_recording import audio, video


@pytest.mark.parametrize(
    "video,snapshot,mp4_ok,jpg_ok,retained",
    [
        (True, True, True, False, True),
        (True, True, False, True, True),
        (True, True, False, False, True),
        (True, True, True, True, False),
        (True, False, True, False, False),
        (False, True, False, True, False),
        (False, False, False, False, True),
    ],
)
def test_raw_stream_survives_any_requested_render_failure(
    tmp_path, monkeypatch, video, snapshot, mp4_ok, jpg_ok, retained
):
    payload = b"\x00\x00\x00\x01\x65idr"
    assembled = SimpleNamespace(
        has_access_units=True,
        stream_bytes=payload,
        frames=[],
        summary={"assembled_units": 1},
        audio=None,
    )
    monkeypatch.setattr(
        writer,
        "assemble_h264_stream_from_messages",
        lambda messages, **kwargs: assembled,
    )
    monkeypatch.setattr(
        writer,
        "write_h264_mp4_if_decodable",
        Mock(return_value=(mp4_ok, "", "")),
    )
    monkeypatch.setattr(
        writer,
        "write_h264_snapshot_from_best_source",
        Mock(return_value=(jpg_ok, "")),
    )
    result = writer.write_h264_stream(
        tmp_path / "clip", [], render_video=video, render_snapshot=snapshot
    )
    raw = tmp_path / "clip.h264"
    assert raw.exists() == retained
    assert result["stream_path"] == (str(raw) if retained else "")
    if retained:
        assert raw.read_bytes() == payload


class H264WriterTests:
    def test_write_stream_bytes_reports_raw_stream_write_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stream_path = Path(tmp) / "clip.h264"
            stream_path.mkdir()

            with pytest.raises(
                MediaRenderError, match="unable to write raw H.264 stream"
            ):
                _write_stream_bytes(stream_path, b"\x00\x00\x00\x01\x65idr")


def test_numbered_capture_writes_do_not_overwrite_another_capture(
    tmp_path, monkeypatch
):
    assembled = SimpleNamespace(
        has_access_units=True,
        stream_bytes=b"\x00\x00\x00\x01\x65idr",
        frames=[],
        summary={"assembled_units": 1},
        audio=None,
    )
    monkeypatch.setattr(
        writer,
        "assemble_h264_stream_from_messages",
        lambda _, **kwargs: assembled,
    )
    original = tmp_path / "clip.h264"
    original.write_bytes(b"existing capture")
    for name in ("clip.1", "clip.2"):
        result = writer.write_h264_stream(
            tmp_path / name, [], render_video=False, render_snapshot=False
        )
        assert Path(result["stream_path"]).name == name + ".h264"
        assert (
            tmp_path / (name + ".h264")
        ).read_bytes() == assembled.stream_bytes
    assert original.read_bytes() == b"existing capture"


@pytest.mark.parametrize(
    "fps,reason", [(None, "unknown"), (20, "after video ends")]
)
def test_unusable_audio_timing_warns_without_changing_video(
    tmp_path, monkeypatch, fps, reason
):
    recording = AudioRecording()
    recording.start_video(video())
    recording.feed(audio(data=b"audio", ms=900))
    assembled = AssembledH264Stream(
        b"\x00\x00\x00\x01\x65idr",
        [],
        {"assembled_units": 1},
        recording,
    )
    render = Mock(return_value=(True, "", ""))
    monkeypatch.setattr(writer, "write_h264_mp4_if_decodable", render)
    with pytest.warns(UserWarning, match=reason):
        result = writer.write_assembled_h264_stream(
            tmp_path / "clip",
            assembled,
            input_fps=fps,
            render_snapshot=False,
        )
    assert render.call_args.kwargs["audio"] is None
    assert render.call_args.kwargs["input_fps"] is fps
    assert not result["summary"]["audio"]["included"]
    assert reason in result["summary"]["audio"]["skipped_reason"]
