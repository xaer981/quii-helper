"""Exercise Camera against synthetic loopback QUII, never the vendor network."""

import json
import shutil
import socket
import struct
import subprocess
import threading
import time
from contextlib import contextmanager
from unittest.mock import Mock

import pytest

from quii_helper import Camera, CameraCaptureError, QuiiConnectionError
from quii_helper.camera.runtime import lan_capture
from quii_helper.protocols.tcp.codec.message_codec import decode_tcp_header
from tests.media.audio.test_frames import audio_cpacket
from tests.media.frames.test_parsing import _cpacket
from tests.protocols.tcp.test_lan_session import (
    KEY,
    command,
    config,
    media,
    setup_reply,
)
from tests.streaming.test_rtsp_server import _recv_until, _rtsp_request

ANNEXB = (
    b"\x00\x00\x00\x01\x67sps"
    b"\x00\x00\x00\x01\x68pps"
    b"\x00\x00\x00\x01\x65idr"
)


def _read_exact(sock, size):
    result = bytearray()
    while len(result) < size:
        part = sock.recv(size - len(result))
        if not part:
            raise EOFError
        result.extend(part)
    return bytes(result)


@contextmanager
def local_camera(
    packets, *, setup_status=0, disconnect=False, before_media=None
):
    stop, closed = threading.Event(), threading.Event()
    errors = []
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.settimeout(2)

        def run():
            try:
                with listener.accept()[0] as sock:
                    sock.settimeout(2)
                    _read_exact(sock, 32)
                    sock.sendall(setup_reply(status=setup_status))
                    if setup_status:
                        return
                    play = decode_tcp_header(
                        _read_exact(sock, 32), crypto_mode=2, key=KEY
                    )
                    assert play.header.packet_type == 1
                    _read_exact(sock, play.read_size)
                    sock.sendall(command())
                    if before_media is not None:
                        assert before_media.wait(2)
                    sock.sendall(b"".join(packets))
                    if not disconnect:
                        while not stop.is_set():
                            try:
                                if not sock.recv(4096):
                                    closed.set()
                                    return
                            except TimeoutError:
                                continue
            except (
                EOFError,
                ConnectionResetError,
                ConnectionAbortedError,
                BrokenPipeError,
            ):
                closed.set()
            except Exception as exc:
                errors.append(exc)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        try:
            yield listener.getsockname()[1], closed
        finally:
            stop.set()
            thread.join(3)
            assert not thread.is_alive()
            assert not errors


def test_local_camera_accepts_windows_connection_abort(monkeypatch):
    monkeypatch.setattr(
        "tests.camera.test_lan_media._read_exact",
        Mock(side_effect=ConnectionAbortedError(10053, "connection aborted")),
    )
    with local_camera([]) as (port, closed):
        with socket.create_connection(("127.0.0.1", port)):
            assert closed.wait(2)


def test_local_camera_reports_unexpected_socket_errors(monkeypatch):
    failed = threading.Event()

    def invalid_read(sock, size):
        failed.set()
        raise OSError(10022, "invalid socket argument")

    monkeypatch.setattr(
        "tests.camera.test_lan_media._read_exact", invalid_read
    )
    with pytest.raises(AssertionError):
        with local_camera([]) as (port, _):
            with socket.create_connection(("127.0.0.1", port)):
                assert failed.wait(2)


@pytest.fixture(autouse=True)
def no_cloud_or_door(monkeypatch):
    fail = Mock(side_effect=AssertionError("cloud/door call forbidden"))
    monkeypatch.setattr(
        "quii_helper.camera.connection.session.fetch_runtime_credentials", fail
    )
    monkeypatch.setattr("quii_helper.camera.api.request_open_door", fail)
    yield fail
    fail.assert_not_called()


def camera_for(port, tmp_path, **kwargs):
    return Camera(config=config(stream_port=port), data_dir=tmp_path, **kwargs)


def fake_renderer(monkeypatch):
    render = Mock(
        return_value={
            "written": True,
            "snapshot": True,
            "snapshot_path": "image.jpg",
            "mp4": True,
            "mp4_path": "video.mp4",
        }
    )
    monkeypatch.setattr(lan_capture, "write_assembled_h264_stream", render)
    return render


def test_snapshot_assembles_fragments_and_skips_frames_before_keyframe(
    tmp_path, monkeypatch
):
    render = fake_renderer(monkeypatch)
    frame = _cpacket(ANNEXB, fps_raw=80)
    packets = [
        media(_cpacket(b"\x00\x00\x01\x41p", frame_tag=0xE0)),
        media(frame[:8]),
        media(frame[8:23]),
        media(frame[23:]),
    ]
    with local_camera(packets) as (port, closed):
        camera = camera_for(port, tmp_path)
        assert camera.snapshot(timeout_seconds=0.2).name == "image.jpg"
        assert closed.wait(2)
    assembled = render.call_args.args[1]
    assert assembled.stream_bytes == ANNEXB
    assert len(assembled.frames) == 1
    assert render.call_args.kwargs["input_fps"] == 20
    assert render.call_args.kwargs["render_video"] is False
    assert not list(
        tmp_path.iterdir()
    )  # Unused timestamp reservation removed.


@pytest.mark.parametrize("method", ["save_video", "record"])
def test_video_waits_full_window_and_does_not_stretch_sparse_frames(
    tmp_path, monkeypatch, method
):
    render = fake_renderer(monkeypatch)
    with local_camera([media(_cpacket(ANNEXB, fps_raw=80))]) as (port, _):
        camera = camera_for(port, tmp_path)
        start = time.monotonic()
        assert getattr(camera, method)(0.12).name == "video.mp4"
        assert time.monotonic() - start >= 0.12
    assert render.call_args.kwargs["input_fps"] == 20
    assert "target_duration_seconds" not in render.call_args.kwargs
    assert len(render.call_args.args[1].frames) == 1


def test_empty_capture_has_no_artifacts_and_snapshot_reports_failure(tmp_path):
    with local_camera([]) as (port, _):
        result = camera_for(port, tmp_path).capture(duration_seconds=0.03)
        assert result.summary["media_collection"]["media_frame_count"] == 0
        assert result.summary["media_result"] is None
    with local_camera([]) as (port, _):
        with pytest.raises(CameraCaptureError, match="not produced"):
            camera_for(port, tmp_path).snapshot(timeout_seconds=0.03)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("method", ["snapshot", "save_video", "serve_rtsp"])
def test_rejected_setup_never_falls_back_to_cloud(tmp_path, method):
    with local_camera([], setup_status=1) as (port, _):
        camera = camera_for(port, tmp_path)
        with pytest.raises(QuiiConnectionError, match="setup was rejected"):
            if method == "serve_rtsp":
                with camera.serve_rtsp(port=0) as stream:
                    stream.wait(timeout=2)
            elif method == "snapshot":
                camera.snapshot(timeout_seconds=0.05)
            else:
                camera.save_video(0.05)


def test_capture_memory_limit_fails_without_partial_success_or_artifacts(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(lan_capture, "MAX_LAN_CAPTURE_BYTES", len(ANNEXB))
    render = fake_renderer(monkeypatch)
    with local_camera([media(_cpacket(ANNEXB) * 2)]) as (port, _):
        with pytest.raises(CameraCaptureError, match="buffer limit"):
            camera_for(port, tmp_path).save_video(0.05)
    render.assert_not_called()
    assert not list(tmp_path.iterdir())


def test_rtsp_publishes_only_after_keyframe_and_close_unblocks_tcp(tmp_path):
    statuses = []
    ready = threading.Event()

    def status(message):
        statuses.append(message)
        if message.startswith("RTSP stream ready:"):
            ready.set()

    frame = _cpacket(ANNEXB)
    with local_camera(
        [
            media(_cpacket(b"\x00\x00\x01\x41p", frame_tag=0xE0)),
            media(frame[:9]),
            media(frame[9:]),
        ]
    ) as (port, closed):
        camera = camera_for(port, tmp_path, status=status)
        with camera.serve_rtsp(port=0) as stream:
            assert ready.wait(2)
            assert stream.assembler.access_unit_count == 1
            assert stream.stats["h264"]["frames"] == 1
            worker = stream._thread
        assert not worker.is_alive()
        assert closed.wait(2)
        assert stream._error is None
    assert not any("credentials" in item for item in statuses)
    assert sum(item.startswith("RTSP stream ready:") for item in statuses) == 1
    assert not list(tmp_path.iterdir())


def test_rtsp_eof_stops_listener_and_wait_reports_error(tmp_path):
    with local_camera([], disconnect=True) as (port, _):
        with camera_for(port, tmp_path).serve_rtsp(port=0) as stream:
            with pytest.raises(QuiiConnectionError, match="receive failed"):
                stream.wait(timeout=2)
            assert not stream.server._running


def test_lan_tcp_to_rtsp_client_receives_rtp(tmp_path):
    release = threading.Event()
    with local_camera([media(_cpacket(ANNEXB))], before_media=release) as (
        port,
        _,
    ):
        with camera_for(port, tmp_path).serve_rtsp(port=0) as stream:
            try:
                with socket.create_connection(
                    ("127.0.0.1", stream.server.port), timeout=2
                ) as viewer:
                    viewer.sendall(
                        _rtsp_request(
                            "SETUP",
                            stream.url + "/trackID=0",
                            1,
                            {
                                "Transport": "RTP/AVP/TCP;unicast;interleaved=0-1"
                            },
                        )
                    )
                    assert b"200 OK" in _recv_until(viewer, b"\r\n\r\n")
                    viewer.sendall(_rtsp_request("PLAY", stream.url, 2))
                    assert b"200 OK" in _recv_until(viewer, b"\r\n\r\n")
                    release.set()
                    header = _read_exact(viewer, 4)
                    assert header[:2] == b"$\x00"
                    packet = _read_exact(
                        viewer, int.from_bytes(header[2:], "big")
                    )
                    assert packet[12:] == b"\x67sps"
            finally:
                release.set()


def test_rtsp_close_during_lan_setup_prevents_play(tmp_path, monkeypatch):
    camera = camera_for(34567, tmp_path)
    entered, released = threading.Event(), threading.Event()
    session = camera.connector.create_lan_session()
    play = Mock(side_effect=AssertionError("play after close"))
    monkeypatch.setattr(session._client, "send_live_open", play)
    monkeypatch.setattr(session._client, "connect", lambda **kw: None)
    monkeypatch.setattr(session._client, "send_setup", lambda: None)

    def setup():
        entered.set()
        assert released.wait(2)
        return {"raw": setup_reply(), "status": 0, "crypto_mode": 2}

    monkeypatch.setattr(session._client, "recv_setup", setup)
    monkeypatch.setattr(
        camera.connector, "create_lan_session", lambda: session
    )
    monkeypatch.setattr(
        "quii_helper.camera.streaming.rtsp.PRODUCER_JOIN_TIMEOUT_SECONDS", 0.01
    )
    stream = camera.serve_rtsp(port=0)
    try:
        assert entered.wait(2)
        worker = stream._thread
        stream.close()
        assert session._closed.is_set()
        with pytest.raises(RuntimeError, match="still stopping"):
            stream.start()
    finally:
        released.set()
        stream.wait(timeout=2)
        stream.close()
    assert not worker.is_alive()
    assert stream._error is None
    play.assert_not_called()


@pytest.fixture
def encoded_frame():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg/ffprobe required for real rendering regression")
    return subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=green:size=64x48:rate=20",
            "-frames:v",
            "1",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-tune",
            "zerolatency",
            "-f",
            "h264",
            "pipe:1",
        ],
        check=True,
        capture_output=True,
        timeout=10,
    ).stdout


def test_real_tcp_to_jpeg_and_mp4_preserves_source_fps(
    tmp_path, encoded_frame
):
    frame = _cpacket(encoded_frame, fps_raw=80, width=64, height=48)
    with local_camera([media(frame)]) as (port, _):
        image = camera_for(port, tmp_path).snapshot(timeout_seconds=0.1)
        assert image.read_bytes().startswith(b"\xff\xd8")
    with local_camera([media(frame * 20)]) as (port, _):
        video = camera_for(port, tmp_path).save_video(0.1)
        probe = json.loads(
            subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_streams",
                    "-of",
                    "json",
                    str(video),
                ],
                timeout=10,
            )
        )["streams"][0]
        assert probe["nb_frames"] == "20"
        assert probe["r_frame_rate"] == "20/1"
        assert float(probe["duration"]) == pytest.approx(1.0, abs=0.06)
    assert len(list(tmp_path.glob("*.jpg"))) == 1
    assert len(list(tmp_path.glob("*.mp4"))) == 1
    assert not list(tmp_path.glob("*.h264"))


@pytest.mark.parametrize(
    "codec,method", [(4, "save_video"), (5, "record"), (4, "capture")]
)
def test_mp4_automatically_muxes_audio_without_shortening_video(
    tmp_path, encoded_frame, codec, method
):
    stamp = 0x6AA12345
    packets = [media(audio_cpacket(b"before-keyframe", codec=codec, ms=0))]
    for index in range(20):
        packet = bytearray(
            _cpacket(
                encoded_frame,
                fps_raw=80,
                width=64,
                height=48,
                frame_stamp=stamp,
            )
        )
        packet[12:14] = (index * 50).to_bytes(2, "little")
        packets.append(media(bytes(packet)))
        if index == 4:
            for audio_index in range(10):
                packets.append(
                    media(
                        audio_cpacket(
                            (b"\xaa" * 4 + b"\x2a" * 4) * 40,
                            codec=codec,
                            ms=200 + audio_index * 40,
                        )
                    )
                )
    with local_camera(packets) as (port, _):
        camera = camera_for(port, tmp_path)
        if method == "capture":
            result = camera.capture(
                duration_seconds=0.15, stop_when_decodable=False
            )
            video = result.require_video()
            assert (
                result.require_snapshot().read_bytes().startswith(b"\xff\xd8")
            )
            assert result.summary["media_result"]["summary"]["audio"][
                "included"
            ]
        else:
            video = getattr(camera, method)(0.15)
    probe = json.loads(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(video),
            ],
            timeout=10,
        )
    )
    tracks = {item["codec_type"]: item for item in probe["streams"]}
    assert set(tracks) == {"video", "audio"}
    assert tracks["video"]["codec_name"] == "h264"
    assert tracks["video"]["nb_frames"] == "20"
    assert tracks["audio"]["codec_name"] == "aac"
    assert tracks["audio"]["sample_rate"] == "8000"
    assert tracks["audio"]["channels"] == 1
    assert float(probe["format"]["duration"]) == pytest.approx(1.0, abs=0.06)
    assert float(tracks["audio"]["start_time"]) == pytest.approx(0, abs=0.02)
    pcm = subprocess.check_output(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(video),
            "-map",
            "0:a:0",
            "-f",
            "s16le",
            "pipe:1",
        ],
        timeout=10,
    )
    samples = struct.unpack(f"<{len(pcm) // 2}h", pcm)
    onset = next(
        index for index, sample in enumerate(samples) if abs(sample) > 512
    )
    assert 0.15 <= onset / 8000 <= 0.23
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-xerror",
            "-i",
            str(video),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-f",
            "null",
            "-",
        ],
        check=True,
        capture_output=True,
        timeout=10,
    )
    assert all(path.suffix in {".mp4", ".jpg"} for path in tmp_path.iterdir())
    assert len(list(tmp_path.glob("*.mp4"))) == 1


def test_snapshot_does_not_collect_audio(tmp_path, monkeypatch):
    render = fake_renderer(monkeypatch)
    with local_camera(
        [
            media(_cpacket(ANNEXB)),
            media(audio_cpacket()),
        ]
    ) as (port, _):
        camera_for(port, tmp_path).snapshot(timeout_seconds=0.1)
    assert render.call_args.args[1].audio is None


def test_audio_counts_towards_the_shared_capture_memory_limit(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        lan_capture, "MAX_LAN_CAPTURE_BYTES", len(ANNEXB) + 319
    )
    render = fake_renderer(monkeypatch)
    with local_camera(
        [
            media(_cpacket(ANNEXB, frame_stamp=0x6AA12345)),
            media(audio_cpacket(b"a" * 320, ms=0)),
        ]
    ) as (port, _):
        with pytest.raises(CameraCaptureError, match="buffer limit"):
            camera_for(port, tmp_path).save_video(0.1)
    render.assert_not_called()


def test_unsupported_audio_warns_but_preserves_video_capture(
    tmp_path, monkeypatch
):
    render = fake_renderer(monkeypatch)
    with local_camera(
        [
            media(_cpacket(ANNEXB, frame_stamp=0x6AA12345)),
            media(audio_cpacket(codec=9)),
        ]
    ) as (port, _):
        with pytest.warns(UserWarning, match="video-only"):
            camera_for(port, tmp_path).save_video(0.1)
    assembled = render.call_args.args[1]
    assert assembled.stream_bytes == ANNEXB
    assert assembled.audio.skipped_reason and not assembled.audio.data
