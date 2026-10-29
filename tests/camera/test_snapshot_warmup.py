"""Snapshot timing and rendering with synthetic media only."""

import importlib
import re
import shutil
import subprocess
from unittest.mock import Mock

import pytest

from quii_helper import AutonomousConfig, Camera, CameraCaptureError
from quii_helper.camera.runtime import lan_capture
from quii_helper.media.h264.core.analysis import analyze_h264_annexb_stream
from tests.camera.test_lan_media import ANNEXB, fake_renderer
from tests.media.audio.test_frames import audio_cpacket
from tests.media.frames.test_parsing import _cpacket
from tests.protocols.tcp.test_lan_session import config


@pytest.mark.parametrize("mode", ["lan", "cloud"])
def test_snapshot_forwards_warmup_without_mutating_camera(
    monkeypatch, tmp_path, mode
):
    api = importlib.import_module("quii_helper.camera.api")
    capture = Mock(
        return_value={
            "media_result": {"snapshot": True, "snapshot_path": "image.jpg"}
        }
    )
    monkeypatch.setattr(
        api,
        f"capture_{'lan' if mode == 'lan' else 'preview'}_summary",
        capture,
    )
    camera = Camera(AutonomousConfig(connection_mode=mode), data_dir=tmp_path)
    assert (
        camera.snapshot(timeout_seconds=3, warmup_seconds=1).name
        == "image.jpg"
    )
    assert capture.call_args.kwargs["settings"].snapshot_warmup_seconds == 1
    assert capture.call_args.kwargs["settings"].capture_seconds == 3
    assert capture.call_args.kwargs["settings"].stop_when_decodable
    assert camera.preview_settings.snapshot_warmup_seconds == 0
    camera.snapshot(timeout_seconds=3)
    assert capture.call_args.kwargs["settings"].snapshot_warmup_seconds == 0


@pytest.mark.parametrize(
    "value", [-1, 3, float("inf"), float("nan"), True, False, "1"]
)
def test_invalid_snapshot_warmup_fails_before_connection(
    monkeypatch, tmp_path, value
):
    camera = Camera(AutonomousConfig(), data_dir=tmp_path)
    capture = Mock(side_effect=AssertionError("network forbidden"))
    monkeypatch.setattr(camera, "_capture_summary", capture)
    with pytest.raises(ValueError, match="warmup_seconds"):
        camera.snapshot(timeout_seconds=3, warmup_seconds=value)
    capture.assert_not_called()
    assert not list(tmp_path.iterdir())


def scripted_camera(monkeypatch, tmp_path, events, *, timeout=3):
    clock = [0.0]
    monkeypatch.setattr(lan_capture.time, "monotonic", lambda: clock[0])
    camera = Camera(config(), data_dir=tmp_path)
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    queue = iter(events)

    def receive(**kwargs):
        try:
            stamp, payload = next(queue)
        except StopIteration:
            clock[0] = timeout
            raise TimeoutError() from None
        clock[0] = stamp
        return {"is_media": True, "payload": payload}

    session.recv_message.side_effect = receive
    monkeypatch.setattr(
        camera.connector, "create_lan_session", lambda: session
    )
    return camera, session


def test_warmup_keeps_reference_frames_and_waits_for_new_video(
    monkeypatch, tmp_path
):
    pframe = b"\x00\x00\x01\x41p"
    camera, session = scripted_camera(
        monkeypatch,
        tmp_path,
        [
            (0.2, _cpacket(ANNEXB)),
            (0.7, audio_cpacket(b"audio")),
            (1.3, audio_cpacket(b"audio")),
            (1.4, _cpacket(pframe, frame_tag=0xE0)),
        ],
    )
    render = fake_renderer(monkeypatch)
    camera.snapshot(timeout_seconds=3, warmup_seconds=1)
    assembled = render.call_args.args[1]
    assert assembled.stream_bytes == ANNEXB + pframe
    assert len(assembled.frames) == 2
    assert render.call_args.kwargs["last_snapshot_frame"]
    assert session.recv_message.call_count == 4
    session.__exit__.assert_called_once()


@pytest.mark.parametrize(
    "events",
    [
        [],
        [(0.2, _cpacket(ANNEXB))],
        [(1.8, _cpacket(ANNEXB))],
        [(0.2, _cpacket(ANNEXB)), (1.5, audio_cpacket(b"audio"))],
        [(0.2, _cpacket(ANNEXB) * 20)],
        [(0.2, _cpacket(ANNEXB)), (2.1, _cpacket(ANNEXB))],
    ],
)
def test_unfinished_warmup_does_not_return_an_early_snapshot(
    monkeypatch, tmp_path, events
):
    camera, session = scripted_camera(monkeypatch, tmp_path, events, timeout=2)
    render = fake_renderer(monkeypatch)
    with pytest.raises(CameraCaptureError, match="warmup did not finish"):
        camera.snapshot(timeout_seconds=2, warmup_seconds=1)
    session.__exit__.assert_called_once()
    render.assert_not_called()
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("warmup,colored", [(0, False), (1, True)])
def test_real_jpeg_uses_later_pframe_after_warmup(
    monkeypatch, tmp_path, warmup, colored
):
    if not shutil.which("ffmpeg"):
        pytest.skip("optional FFmpeg integration")
    encoded = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=gray:s=64x48:r=2:d=1",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=64x48:r=2:d=1",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0",
            "-c:v",
            "libx264",
            "-bf",
            "0",
            "-x264-params",
            "aud=1:scenecut=0",
            "-g",
            "100",
            "-pix_fmt",
            "yuv420p",
            "-f",
            "h264",
            "pipe:1",
        ],
        capture_output=True,
        check=True,
        timeout=15,
    ).stdout
    starts = [
        m.start() for m in re.finditer(b"\x00\x00(?:\x00)?\x01\x09", encoded)
    ]
    assert len(starts) == 4 and starts[0] == 0
    units = [
        encoded[start:end]
        for start, end in zip(starts, [*starts[1:], len(encoded)])
    ]
    assert analyze_h264_annexb_stream(units[0])["has_idr"]
    assert not analyze_h264_annexb_stream(units[2])["has_idr"]
    assert analyze_h264_annexb_stream(units[2])["counts"]["non_idr_slice"]
    events = [
        (
            0.1 + index * 0.5,
            _cpacket(
                unit,
                frame_tag=0xE1 if index == 0 else 0xE0,
                width=64,
                height=48,
                fps_raw=8,
            ),
        )
        for index, unit in enumerate(units)
    ]
    camera, _ = scripted_camera(monkeypatch, tmp_path, events)
    path = camera.snapshot(timeout_seconds=3, warmup_seconds=warmup)
    rgb = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(path),
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "pipe:1",
        ],
        capture_output=True,
        check=True,
        timeout=15,
    ).stdout
    assert len(rgb) == 64 * 48 * 3
    red_pixels = sum(rgb[i] - rgb[i + 1] > 50 for i in range(0, len(rgb), 3))
    assert (red_pixels > 64 * 48 // 2) == colored
    assert not list(tmp_path.glob("*.h264"))
    # A nonexistent selected frame must not report an older JPEG as success.
    from quii_helper.media.h264.io.ffmpeg import (
        write_h264_snapshot_from_best_source,
    )

    previous = path.read_bytes()
    raw = tmp_path / "missing-frame.h264"
    raw.write_bytes(encoded)
    ok, error = write_h264_snapshot_from_best_source(
        raw,
        tmp_path / "unused.mp4",
        path,
        mp4_ok=False,
        ffmpeg_skipped_reason="",
        frame_index=999,
    )
    assert not ok and error
    assert path.read_bytes() == previous
