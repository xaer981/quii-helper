import json
import shutil
import struct
import subprocess
import time
from unittest.mock import Mock

import pytest

from quii_helper.media.archive import frames as frame_module
from quii_helper.media.archive import video as video_module
from quii_helper.media.archive.frames import ArchiveMedia, nal_units
from quii_helper.protocols.tcp.archive import download
from quii_helper.support.errors import CameraCaptureError, MediaRenderError
from tests.protocols.tcp.test_archive_download import cpacket, peer
from tests.protocols.tcp.test_archive_packets import (
    FILENAME,
    plain,
    video_record,
)
from tests.protocols.tcp.test_lan_session import command, config, media

STAMP = 0x6ABAA2CC


def video_packet(data, *, ms=0, codec=1, marker=0xE1, fps_raw=80, width=64):
    return (
        struct.pack(
            "<4sIIHBBHH",
            b"\0\0\x01" + bytes([marker]),
            len(data),
            STAMP,
            ms,
            codec,
            fps_raw,
            width,
            48,
        )
        + data
    )


def audio_packet(data=b"\xd5" * 320, *, ms=100, codec=4):
    return (
        struct.pack(
            "<4sIIHBBHH",
            b"\0\0\x01\xe3",
            len(data),
            STAMP,
            ms,
            codec,
            1,
            8000,
            0,
        )
        + data
    )


@pytest.fixture(params=["baseline", "high"], scope="module")
def units(request):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip(
            "FFmpeg and ffprobe required for real archive export tests"
        )
    raw = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=64x48:rate=20",
            "-frames:v",
            "4",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-tune",
            "zerolatency",
            "-profile:v",
            request.param,
            "-x264-params",
            "aud=1:keyint=10:bframes=0",
            "-f",
            "h264",
            "pipe:1",
        ],
        check=True,
        capture_output=True,
        timeout=10,
    ).stdout
    nals = nal_units(raw)
    result = []
    for nal in nals:
        if nal[0] & 31 == 9:
            result.append(bytearray())
        result[-1].extend(b"\0\0\0\1" + nal)
    assert len(result) == 4
    assert any(n[0] & 31 == 5 for n in nal_units(result[0]))
    assert all(
        not any(n[0] & 31 == 5 for n in nal_units(data)) for data in result[1:]
    )
    return list(map(bytes, result))


def collected(units, *, audio=False):
    result = ArchiveMedia("video", 1024 * 1024)
    for i, (data, stamp) in enumerate(zip(units, (0, 50, 250, 350))):
        packet = video_packet(data, ms=stamp, marker=0xE1 if i == 0 else 0xE0)
        for offset in range(0, len(packet), 7):
            result.feed(packet[offset : offset + 7])
        if i == 0 and audio:
            result.feed(audio_packet())
    result.finish()
    return result


@pytest.mark.parametrize("fps_raw", [0, 80])
def test_equal_timestamps_preserve_all_frames_and_positive_final_duration(
    fps_raw,
):
    source = ArchiveMedia("video", 1024 * 1024)
    data = b"\0\0\1\x67\x42\0\x1e\0\0\1\x68\0\0\1\x65body"
    for ms in (80, 80, 80, 120):
        source.feed(video_packet(data, ms=ms, fps_raw=fps_raw))
    source.finish()
    assert len(source.frames) == 4
    assert [
        f.timestamp_ms - source.frames[0].timestamp_ms for f in source.frames
    ] == [0, 0, 0, 40]
    assert source.last_duration_ms() == (40 if fps_raw == 0 else 50)
    assert source.duration_seconds == pytest.approx(
        0.08 if fps_raw == 0 else 0.09
    )


def test_all_equal_timestamps_without_fps_fail_instead_of_guessing_duration():
    source = ArchiveMedia("video", 1024 * 1024)
    data = b"\0\0\1\x67\x42\0\x1e\0\0\1\x68\0\0\1\x65body"
    for _ in range(3):
        source.feed(video_packet(data, ms=80, fps_raw=0))
    with pytest.raises(
        CameraCaptureError, match="known FPS or a positive frame interval"
    ):
        source.finish()


def test_equal_timestamps_still_reject_backward_time_and_large_gaps():
    data = b"\0\0\1\x65body"
    for stamp, ms in ((STAMP, 79), (STAMP + 60, 80)):
        source = ArchiveMedia("video", 1024 * 1024)
        source.feed(video_packet(data, ms=80))
        bad = bytearray(video_packet(data, ms=ms))
        struct.pack_into("<I", bad, 8, stamp)
        with pytest.raises(
            CameraCaptureError, match="nonmonotonic or discontinuous"
        ):
            source.feed(bytes(bad))


@pytest.mark.parametrize(
    "timestamps,fps_raw,expected_duration",
    [((80, 80, 120, 180), 80, 0.15), ((80, 80, 80, 120), 0, 0.08)],
)
def test_real_duplicate_timestamp_export_keeps_frames_and_timeline(
    tmp_path, units, timestamps, fps_raw, expected_duration
):
    source = ArchiveMedia("video", 1024 * 1024)
    for data, ms in zip(units, timestamps):
        source.feed(video_packet(data, ms=ms, fps_raw=fps_raw))
    source.finish()
    output = video_module.render_archive_mp4(
        source,
        directory=tmp_path / "scratch",
        executable=video_module.require_ffmpeg(),
        deadline=time.monotonic() + 15,
        max_bytes=1024 * 1024,
    )
    target = tmp_path / "duplicates.mp4"
    target.write_bytes(output)
    info = json.loads(
        subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v",
                "-show_streams",
                "-show_packets",
                "-of",
                "json",
                str(target),
            ],
            capture_output=True,
            check=True,
            timeout=10,
        ).stdout
    )
    assert info["streams"][0]["nb_frames"] == "4"
    assert float(info["streams"][0]["duration"]) == pytest.approx(
        expected_duration, abs=0.002
    )
    assert [float(p["pts_time"]) for p in info["packets"]] == pytest.approx(
        [(ms - timestamps[0]) / 1000 for ms in timestamps],
        abs=0.001,
    )
    decoded = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-xerror",
            "-i",
            str(target),
            "-fps_mode",
            "passthrough",
            "-enc_time_base:v",
            "1/1000000",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        timeout=10,
    )
    assert decoded.returncode == 0 and decoded.stderr == b""
    assert not list((tmp_path / "scratch").iterdir())


@pytest.mark.parametrize("audio", [False, True])
def test_real_export_preserves_vfr_frame_count_timestamps_and_supported_audio(
    tmp_path, units, audio
):
    source = collected(units, audio=audio)
    scratch = tmp_path / "scratch"
    result = video_module.render_archive_mp4(
        source,
        directory=scratch,
        executable=video_module.require_ffmpeg(),
        deadline=time.monotonic() + 15,
        max_bytes=1024 * 1024,
    )
    assert result[4:8] == b"ftyp"
    target = tmp_path / "result.mp4"
    target.write_bytes(result)
    parsed = json.loads(
        subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_packets",
                "-of",
                "json",
                str(target),
            ],
            capture_output=True,
            check=True,
            timeout=10,
        ).stdout
    )
    streams = parsed["streams"]
    assert streams[0]["codec_name"] == "h264"
    assert streams[0]["nb_frames"] == "4"
    assert float(streams[0]["duration"]) == pytest.approx(0.4, abs=0.002)
    packets = [p for p in parsed["packets"] if p["codec_type"] == "video"]
    assert [float(p["pts_time"]) for p in packets] == pytest.approx(
        [0, 0.05, 0.25, 0.35], abs=0.001
    )
    assert [float(p["duration_time"]) for p in packets] == pytest.approx(
        [0.05, 0.2, 0.1, 0.05], abs=0.001
    )
    assert len(streams) == (2 if audio else 1)
    if audio:
        assert streams[1]["codec_name"] == "aac"
    decoded = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(target), "-f", "null", "-"],
        capture_output=True,
        timeout=10,
    )
    assert decoded.returncode == 0 and decoded.stderr == b""
    assert not list(scratch.iterdir())


def test_real_file_download_then_export_closes_socket_before_remux(
    tmp_path, units, monkeypatch
):
    packets = b"".join(
        video_packet(data, ms=stamp)
        for data, stamp in zip(units, (0, 0, 250, 350))
    )
    sock, _, factory = peer([command(2), media(packets), command(8)])
    render = download.render_archive_mp4

    def checked_render(*args, **kwargs):
        assert sock.closed
        return render(*args, **kwargs)

    monkeypatch.setattr(download, "render_archive_mp4", checked_render)
    result = download.download_record_bytes(
        config(),
        video_record(file_name=FILENAME),
        temporary_directory=tmp_path,
        timeout=15,
        transport_factory=factory,
    )
    assert result[4:8] == b"ftyp" and sock.closed
    header, _ = plain(sock.sent[1])
    assert header[24] == 1 and header[28:] == b"\0" * 4
    assert not list(tmp_path.iterdir())


def test_keyboard_interrupt_during_export_cleans_private_files(
    tmp_path, monkeypatch, units
):
    monkeypatch.setattr(
        video_module.subprocess, "run", Mock(side_effect=KeyboardInterrupt())
    )
    with pytest.raises(KeyboardInterrupt):
        video_module.render_archive_mp4(
            collected(units),
            directory=tmp_path,
            executable="ffmpeg",
            deadline=time.monotonic() + 5,
            max_bytes=100000,
        )
    assert not list(tmp_path.iterdir())


def test_export_expired_deadline_creates_no_temporary_directory(
    tmp_path, units
):
    target = tmp_path / "absent"
    with pytest.raises(CameraCaptureError, match="timed out"):
        video_module.render_archive_mp4(
            collected(units),
            directory=target,
            executable="ffmpeg",
            deadline=time.monotonic() - 1,
            max_bytes=100000,
        )
    assert not target.exists()


def test_rejected_or_incomplete_video_does_not_call_export(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(download, "require_ffmpeg", lambda: "ffmpeg")
    export = Mock(
        side_effect=AssertionError("partial video must not be exported")
    )
    monkeypatch.setattr(download, "render_archive_mp4", export)
    sock, _, factory = peer([command(2, status=3)])
    with pytest.raises(OSError):
        download.download_record_bytes(
            config(),
            video_record(),
            temporary_directory=tmp_path,
            transport_factory=factory,
        )
    assert sock.closed and not list(tmp_path.iterdir())
    export.assert_not_called()


def test_jpeg_download_does_not_need_ffmpeg_or_touch_data_dir(
    tmp_path, monkeypatch
):
    from tests.protocols.tcp.test_archive_download import JPEG
    from tests.protocols.tcp.test_archive_packets import record

    monkeypatch.setattr(
        download,
        "require_ffmpeg",
        Mock(side_effect=AssertionError("FFmpeg forbidden for JPEG")),
    )
    sock, _, factory = peer([command(2), media(cpacket()), command(8)])
    target = tmp_path / "absent"
    assert (
        download.download_record_bytes(
            config(),
            record(),
            temporary_directory=target,
            transport_factory=factory,
        )
        == JPEG
    )
    assert sock.closed and not target.exists()


def test_missing_ffmpeg_preflight_does_not_connect_or_create_tempfiles(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(video_module.shutil, "which", lambda name: None)
    factory = Mock(side_effect=AssertionError("network forbidden"))
    with pytest.raises(MediaRenderError, match="requires FFmpeg"):
        download.download_record_bytes(
            config(),
            video_record(),
            temporary_directory=tmp_path,
            transport_factory=factory,
        )
    factory.assert_not_called()
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "failure",
    [
        subprocess.CalledProcessError(1, "ffmpeg"),
        subprocess.TimeoutExpired("ffmpeg", 1),
        OSError("disk full"),
    ],
)
def test_export_failure_cleans_private_intermediates(
    tmp_path, monkeypatch, units, failure
):
    source = collected(units, audio=True)

    def fail(command, **kwargs):
        paths = [
            command[i + 1] for i, value in enumerate(command) if value == "-i"
        ]
        assert len(paths) == 2
        raise failure

    monkeypatch.setattr(video_module.subprocess, "run", fail)
    with pytest.raises(CameraCaptureError):
        video_module.render_archive_mp4(
            source,
            directory=tmp_path,
            executable="ffmpeg",
            deadline=time.monotonic() + 5,
            max_bytes=100000,
        )
    assert not list(tmp_path.iterdir())


def test_complete_oversized_output_is_rejected_not_size_truncated(
    tmp_path, units
):
    with pytest.raises(CameraCaptureError, match="MP4 exceeds max_bytes"):
        video_module.render_archive_mp4(
            collected(units),
            directory=tmp_path,
            executable=video_module.require_ffmpeg(),
            deadline=time.monotonic() + 10,
            max_bytes=32,
        )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "bad",
    [
        video_packet(b"\0\0\1\x65body", codec=2),
        audio_packet(codec=9),
        video_packet(b"\0\0\1\x65body", ms=1000),
        video_packet(b"\0\0\1\x65body", ms=50, width=128),
        cpacket(),
    ],
)
def test_unsupported_or_discontinuous_video_is_not_silently_exported(
    units, bad
):
    source = ArchiveMedia("video", 1024 * 1024)
    source.feed(video_packet(units[0]))
    with pytest.raises(CameraCaptureError):
        source.feed(bad)


def test_eof_requires_keyframe_parameter_sets_and_complete_packet(units):
    for packets in (b"", video_packet(units[1]), video_packet(units[0])[:-1]):
        source = ArchiveMedia("video", 1024 * 1024)
        source.feed(packets)
        with pytest.raises(CameraCaptureError):
            source.finish()


def test_repeated_keyframe_configuration_must_not_change(units):
    source = collected(units)
    changed = units[0].replace(
        source.sps, source.sps[:-1] + bytes([source.sps[-1] ^ 1])
    )
    with pytest.raises(CameraCaptureError, match="parameter sets changed"):
        source.feed(video_packet(changed, ms=500))


def test_payload_and_frame_count_limits_cover_ignored_and_retained_data(
    units, monkeypatch
):
    small = ArchiveMedia("video", 10)
    with pytest.raises(CameraCaptureError, match="max_bytes"):
        small.feed(video_packet(units[0])[:20])
    source = ArchiveMedia("video", 1024 * 1024)
    source.feed(video_packet(units[0]))
    monkeypatch.setattr(frame_module, "MAX_ARCHIVE_VIDEO_FRAMES", 1)
    with pytest.raises(CameraCaptureError, match="frame-count"):
        source.feed(video_packet(units[1], ms=50))


def test_nal_count_is_bounded_before_start_code_and_unit_lists_are_built():
    source = ArchiveMedia("video", 1024 * 1024)
    with pytest.raises(CameraCaptureError, match="per-frame NAL limit"):
        source.feed(video_packet(b"\0\0\1\x09" * 4097))


def test_audio_entirely_outside_clip_is_not_replaced_with_a_silent_track(
    units,
):
    source = ArchiveMedia("video", 1024 * 1024)
    source.feed(video_packet(units[0]))
    source.feed(audio_packet(ms=100))
    with pytest.raises(
        CameraCaptureError, match="audio starts after video ends"
    ):
        source.finish()


@pytest.mark.parametrize("marker", [0xE7, 0xE8])
def test_native_non_media_metadata_does_not_become_video_or_audio(
    units, marker
):
    source = collected(units)
    count, audio_bytes = len(source.frames), len(source.audio.data)
    source.feed(video_packet(b"metadata", marker=marker, codec=4, ms=500))
    source.finish()
    assert len(source.frames) == count
    assert len(source.audio.data) == audio_bytes
