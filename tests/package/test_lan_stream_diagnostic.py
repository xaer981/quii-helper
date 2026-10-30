"""Offline checks for the opt-in saved-key LAN diagnostic example."""

import importlib
import json
import shutil
import struct
import subprocess
from unittest.mock import MagicMock, Mock

import pytest

from quii_helper import CameraStreamCredentials
from quii_helper.protocols.tcp.codec.message_codec import decode_tcp_header
from quii_helper.support.errors import QuiiConnectionError

example = importlib.import_module("examples.diagnose_lan_stream")


def media_message(payload):
    raw = bytearray(32)
    raw[0] = 0xA0
    struct.pack_into("<I", raw, 11, len(payload))
    return {
        "is_media": True,
        "payload": payload,
        "header": decode_tcp_header(bytes(raw), crypto_mode=0, key=b"").header,
    }


@pytest.mark.parametrize("failed_phase", [None, "handshake_setup_oem"])
def test_handshake_comparison_is_explicit_bounded_and_never_switches(
    monkeypatch, capsys, tmp_path, failed_phase
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CAMERA_CONNECTION_MODE", "cloud")
    saved = CameraStreamCredentials("synthetic-id", "K" * 32, "private-auth")
    monkeypatch.setattr(
        example.CameraStreamCredentials, "load", Mock(return_value=saved)
    )
    monkeypatch.setattr(example.shutil, "which", lambda name: name)
    monkeypatch.setattr(
        example, "uuid4", lambda: Mock(hex="private-diagnostic-client")
    )
    factory = MagicMock()
    session = factory.return_value.__enter__.return_value
    session.play_accepted = True
    monkeypatch.setattr(example, "LanTcpSession", factory)
    monkeypatch.setattr(
        example,
        "_keyframe_dimensions",
        lambda *args: {"status": "no_h264_keyframe"},
    )

    def observe(session, packer, *, name, seconds, progress, **kwargs):
        assert seconds == 10
        if name == failed_phase:
            raise QuiiConnectionError(
                "private-diagnostic-client must not be printed"
            )
        return {
            "phase": name,
            "cpacket_dimensions": {"352x288": 190},
            "frame_capture": None,
        }, b""

    monkeypatch.setattr(example, "_observe_phase", observe)
    args = [
        "--host",
        "127.0.0.1",
        "--compare-handshakes",
        "--oem",
        "G0000",
        "--stream",
        "2",
        "--seconds",
        "10",
        "--save-frames",
    ]
    if failed_phase:
        with pytest.raises(QuiiConnectionError):
            example.main(args)
    else:
        example.main(args)
    calls = factory.call_args_list
    assert len(calls) == 5 and factory.return_value.__exit__.call_count == 5
    assert [call.kwargs for call in calls] == [
        {"handshake": "setup_path", "client_id": ""},
        {"handshake": "setup_oem", "client_id": ""},
        {"handshake": "fast_oem", "client_id": ""},
        {"handshake": "setup_oem", "client_id": "private-diagnostic-client"},
        {"handshake": "fast_oem", "client_id": "private-diagnostic-client"},
    ]
    for call in calls:
        settings = call.args[0]
        assert settings.connection_mode == "lan" and settings.stream == 2
        assert (
            settings.oem == "G0000" and settings.auth_code == saved.auth_code
        )
        assert settings.stream_key == saved.stream_key
        assert not settings.cloud_account and not settings.cloud_password
    session.request_stream_switch.assert_not_called()
    session.request_device_query.assert_not_called()
    report_text = next((tmp_path / "data").glob("*/report.json")).read_text()
    report = json.loads(report_text)
    assert report["completed"] is (failed_phase is None)
    assert [phase["handshake"] for phase in report["phases"]] == [
        "setup_path",
        "setup_oem",
        "fast_oem",
        "setup_oem",
        "fast_oem",
    ]
    assert [phase["client_id_present"] for phase in report["phases"]] == [
        False,
        False,
        False,
        True,
        True,
    ]
    assert len(report["failures"]) == (1 if failed_phase else 0)
    output = capsys.readouterr().out + report_text
    for secret in (
        saved.stream_key,
        saved.auth_code,
        "private-diagnostic-client",
    ):
        assert secret not in output


@pytest.mark.parametrize(
    "options",
    [
        ["--compare-handshakes"],
        ["--compare-handshakes", "--oem", ""],
        ["--compare-handshakes", "--oem", ",,,"],
        ["--compare-handshakes", "--oem", "bad\x00id"],
        ["--compare-handshakes", "--oem", "x" * 257],
        ["--compare-handshakes", "--oem", "G0000", "--stream", "4"],
        ["--oem", "G0000"],
        ["--stream", "1"],
    ],
)
def test_invalid_handshake_flags_fail_before_loading_credentials(
    monkeypatch, options
):
    load = Mock(side_effect=AssertionError("no credential access"))
    monkeypatch.setattr(example.CameraStreamCredentials, "load", load)
    with pytest.raises(SystemExit):
        example.main(["--host", "127.0.0.1", *options])
    load.assert_not_called()


@pytest.mark.parametrize("failed_phase", [None, "switch_2_to_1"])
def test_example_is_lan_only_and_runs_all_selectors_after_switch_failure(
    monkeypatch, capsys, tmp_path, failed_phase
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CAMERA_CONNECTION_MODE", "cloud")
    monkeypatch.setenv("CLOUD_PASSWORD", "never-print-this-secret")
    saved = CameraStreamCredentials("synthetic-id", "K" * 32, "private-auth")
    load = Mock(return_value=saved)
    monkeypatch.setattr(example.CameraStreamCredentials, "load", load)
    monkeypatch.setattr(example.shutil, "which", lambda name: "ffprobe")
    factory = MagicMock()
    session = factory.return_value.__enter__.return_value
    session.play_accepted = True
    session.stream_switch_pending = False
    monkeypatch.setattr(example, "LanTcpSession", factory)
    active = [False]

    def enter():
        active[0] = True
        return session

    def leave(*args):
        active[0] = False
        return False

    factory.return_value.__enter__.side_effect = enter
    factory.return_value.__exit__.side_effect = leave

    def inspect(*args):
        assert not active[0], "decoder must run only after disconnect"
        return {"status": "ok", "width": 640, "height": 480}

    monkeypatch.setattr(example, "_keyframe_dimensions", inspect)

    def observe(
        session,
        packer,
        *,
        name,
        seconds,
        capture_path,
        progress,
        readonly_info,
    ):
        assert readonly_info is None
        if name == failed_phase:
            raise QuiiConnectionError("synthetic switch rejection")
        assert capture_path is None
        assert seconds == 20
        return (
            {
                "phase": name,
                "cpacket_dimensions": {"640x480": 1},
                "frame_capture": None,
            },
            b"idr",
        )

    monkeypatch.setattr(example, "_observe_phase", observe)
    args = ["--host", "127.0.0.1", "--channel", "2"]
    if failed_phase:
        with pytest.raises(QuiiConnectionError, match="synthetic"):
            example.main(args)
    else:
        example.main(args)
    configs = [call.args[0] for call in factory.call_args_list]
    assert [config.stream for config in configs] == [1, 2, 3]
    for config in configs:
        assert config.connection_mode == "lan"
        assert config.channel == 2 and config.device_host == "127.0.0.1"
        assert config.stream_key == saved.stream_key
        assert config.auth_code == saved.auth_code
        assert not config.cloud_account and not config.cloud_password
    requests = [
        call.args[0] for call in session.request_stream_switch.call_args_list
    ]
    assert requests == [1, 1]
    assert all(
        call.kwargs == {"timeout": None}
        for call in session.request_stream_switch.call_args_list
    )
    assert factory.return_value.__exit__.call_count == 3
    session.request_device_query.assert_not_called()
    assert not (tmp_path / "data").exists()
    output = capsys.readouterr().out
    for secret in (
        saved.stream_key,
        saved.auth_code,
        "never-print-this-secret",
    ):
        assert secret not in output


@pytest.mark.parametrize("seconds", ["0", "5", "31", "nan", "inf"])
def test_invalid_duration_fails_before_loading_secrets(monkeypatch, seconds):
    load = Mock(side_effect=AssertionError("no credential access"))
    monkeypatch.setattr(example.CameraStreamCredentials, "load", load)
    with pytest.raises(SystemExit):
        example.main(["--host", "127.0.0.1", "--seconds", seconds])
    load.assert_not_called()


def test_missing_ffprobe_fails_before_loading_secrets(monkeypatch):
    load = Mock(side_effect=AssertionError("no credential access"))
    monkeypatch.setattr(example.CameraStreamCredentials, "load", load)
    monkeypatch.setattr(example.shutil, "which", lambda name: None)
    with pytest.raises(SystemExit):
        example.main(["--host", "127.0.0.1"])
    load.assert_not_called()


def test_phase_preserves_media_audio_and_defers_h264_analysis(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(example.time, "monotonic", lambda: clock[0])
    session = Mock(active_stream=1, stream_switch_pending=False)
    packer = Mock(stats={})
    frame = {
        "frame_tag": 0xE1,
        "width": 1920,
        "height": 1080,
        "codec": 1,
        "nal_offset": 0,
        "bitstream": b"synthetic-h264",
    }
    packer.feed.side_effect = [
        [frame],
        [{"frame_tag": 0xE3, "codec": 4, "sample_rate": 8000, "channels": 1}],
    ]
    messages = iter(
        [
            media_message(b"video"),
            {"is_media": False, "header": Mock(packet_type=9, raw=bytes(32))},
            media_message(b"audio"),
        ]
    )

    def receive(**kwargs):
        clock[0] += 1
        return next(messages)

    session.recv_message.side_effect = receive
    inspect_frame = Mock(
        side_effect=AssertionError("no subprocess while receiving")
    )
    monkeypatch.setattr(example, "_keyframe_dimensions", inspect_frame)
    result, keyframe = example._observe_phase(
        session, packer, name="switched_high", seconds=3
    )
    assert result["counts"] == {"frame_e1": 1, "command_09": 1, "frame_e3": 1}
    assert result["cpacket_dimensions"] == {"1920x1080": 1}
    assert result["last_keyframe_h264"] == {"status": "not_analyzed"}
    assert result["audio_codec_rate_channels"] == {"4/8000/1": 1}
    assert result["switch_reply_statuses"] == [0]
    assert result["switch_status"] == "not_requested"
    assert keyframe == b"synthetic-h264"
    inspect_frame.assert_not_called()


@pytest.mark.parametrize(
    "arrivals,expected",
    [
        ([2 + index * 0.05 for index in range(21)], 20.0),
        ([1.0, 3.0, 5.0], 0.5),
        ([1.0], None),
        ([1.0, 1.0, 1.0], None),
        ([], None),
    ],
)
def test_arrival_fps_uses_receive_times_not_headers_or_capture(
    monkeypatch, arrivals, expected
):
    clock = [0.0]
    monkeypatch.setattr(example.time, "monotonic", lambda: clock[0])
    session = Mock(stream_switch_pending=False)
    remaining = list(arrivals)

    def receive(*, timeout):
        if not remaining or remaining[0] > clock[0] + timeout:
            clock[0] += timeout
            raise TimeoutError()
        clock[0] = remaining.pop(0)
        return media_message(b"video")

    session.recv_message.side_effect = receive
    packer = Mock(stats={})
    packer.feed.return_value = [
        {
            "frame_tag": 0xE1,
            "width": 352,
            "height": 288,
            "codec": 1,
            "fps": 99,
            "nal_offset": 0,
            "bitstream": b"I",
        }
    ]
    result, _ = example._observe_phase(
        session, packer, name="initial_stream_3", seconds=6
    )
    timing = result["video_timing"]
    assert timing["frames"] == len(arrivals)
    assert timing["arrival_fps"] == expected
    assert timing["window_fps"] == round(len(arrivals) / 6, 3)
    assert timing["first_arrival_seconds"] == (
        round(arrivals[0], 4) if arrivals else None
    )
    assert timing["last_arrival_seconds"] == (
        round(arrivals[-1], 4) if arrivals else None
    )
    assert result["frame_capture"] is None


@pytest.mark.parametrize("ack_at", [None, 7.0])
def test_phase_saves_media_without_ack_and_recognizes_late_reply(
    monkeypatch, tmp_path, ack_at
):
    clock = [0.0]
    monkeypatch.setattr(example.time, "monotonic", lambda: clock[0])
    session = Mock(active_stream=2, stream_switch_pending=True)

    def receive(**kwargs):
        clock[0] += 0.5
        if clock[0] == ack_at:
            session.active_stream = 1
            session.stream_switch_pending = False
            return {
                "is_media": False,
                "header": Mock(packet_type=9, raw=bytes(32)),
            }
        return media_message(b"video")

    session.recv_message.side_effect = receive
    packer = Mock(stats={})
    frame = {
        "frame_tag": 0xE1,
        "width": 352,
        "height": 288,
        "codec": 1,
        "nal_offset": 0,
        "bitstream": b"I",
    }
    # All frames completed from this payload have the same receive timestamp.
    packer.feed.return_value = [frame, frame]
    path = tmp_path / "switch_2_to_1.h264"
    result, keyframe = example._observe_phase(
        session, packer, name="switch_2_to_1", seconds=8, capture_path=path
    )
    count = 32 if ack_at is None else 30
    assert path.read_bytes() == b"I" * count
    assert keyframe == b"I"
    assert result["frame_capture"]["retained_frames"] == count
    assert result["video_timing"]["frames"] == count
    assert result["video_timing"]["first_arrival_seconds"] == 0.5
    assert result["video_timing"]["last_arrival_seconds"] == 8.0
    assert result["elapsed_seconds"] == 8
    assert result["switch_status"] == (
        "unconfirmed" if ack_at is None else "acknowledged"
    )
    assert result["switch_pending"] is (ack_at is None)
    assert result["switch_reply_statuses"] == ([] if ack_at is None else [0])
    assert session.active_stream == (2 if ack_at is None else 1)


def test_example_completes_all_windows_without_switch_ack(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.chdir(tmp_path)
    saved = CameraStreamCredentials("synthetic-id", "K" * 32, "private-auth")
    monkeypatch.setattr(
        example.CameraStreamCredentials, "load", lambda _: saved
    )
    monkeypatch.setattr(example.shutil, "which", lambda name: name)
    monkeypatch.setattr(example, "_keyframe_dimensions", lambda *args: {})
    monkeypatch.setattr(example, "_save_frames", lambda *args: {})
    factory = MagicMock()
    session = factory.return_value.__enter__.return_value
    session.play_accepted = True
    monkeypatch.setattr(example, "LanTcpSession", factory)

    def observe(session, packer, *, name, progress, **kwargs):
        pending = name.startswith("switch_")
        session.stream_switch_pending = pending
        progress.update(
            cpacket_dimensions={"352x288": 1},
            frame_capture=None,
            switch_status="unconfirmed" if pending else "not_requested",
            switch_pending=pending,
        )
        return progress, b""

    monkeypatch.setattr(example, "_observe_phase", observe)
    example.main(["--host", "127.0.0.1", "--save-frames"])
    report = json.loads(
        next((tmp_path / "data").glob("*/report.json")).read_text()
    )
    assert report["completed"] and report["failures"] == []
    assert len(report["phases"]) == 5
    assert [row["requested_stream"] for row in report["phases"]] == [
        1,
        2,
        1,
        3,
        1,
    ]
    assert [row["initial_stream"] for row in report["phases"]] == [
        1,
        2,
        2,
        3,
        3,
    ]
    assert all(row["status"] == "completed" for row in report["phases"])
    assert report["phases"][2]["switch_status"] == "unconfirmed"
    assert report["phases"][4]["switch_status"] == "unconfirmed"
    assert session.request_stream_switch.call_count == 2
    assert factory.return_value.__exit__.call_count == 3
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["completed"]


def test_failed_phase_keeps_statistics_and_last_known_switch_state(
    monkeypatch,
):
    clock = [0.0]
    monkeypatch.setattr(example.time, "monotonic", lambda: clock[0])
    session = Mock(active_stream=2, stream_switch_pending=True)
    packer = Mock(stats={"completed": 1})
    packer.feed.return_value = [
        {"frame_tag": 0xE3, "codec": 4, "sample_rate": 8000, "channels": 1}
    ]
    reads = [
        media_message(b"audio"),
        QuiiConnectionError("LAN TCP stream switch timed out"),
    ]

    def receive(**kwargs):
        clock[0] += 1
        value = reads.pop(0)
        if isinstance(value, Exception):
            session.active_stream = None
            session.stream_switch_pending = False
            raise value
        return value

    session.recv_message.side_effect = receive
    progress = {}
    with pytest.raises(QuiiConnectionError, match="timed out"):
        example._observe_phase(
            session,
            packer,
            name="switched_high",
            seconds=10,
            progress=progress,
        )
    assert progress["counts"] == {"frame_e3": 1}
    assert progress["cframe"] == {"completed": 1}
    assert progress["elapsed_seconds"] == 2
    assert progress["switch_status"] == "unconfirmed"
    assert "acknowledged_stream" not in progress
    assert progress["switch_pending"] is True


@pytest.mark.parametrize("stage", ["send_switch", "receive"])
def test_failure_report_contains_phase_and_reason_without_exception_secrets(
    monkeypatch, tmp_path, capsys, stage
):
    monkeypatch.chdir(tmp_path)
    secret = "private-auth-value-never-publish"
    saved = CameraStreamCredentials("synthetic-id", "K" * 32, secret)
    monkeypatch.setattr(
        example.CameraStreamCredentials, "load", lambda _: saved
    )
    monkeypatch.setattr(example.shutil, "which", lambda name: name)
    factory = MagicMock()
    session = factory.return_value.__enter__.return_value
    session.play_accepted = True
    session.stream_switch_pending = False
    monkeypatch.setattr(example, "LanTcpSession", factory)
    monkeypatch.setattr(example, "_keyframe_dimensions", lambda *args: {})
    error = QuiiConnectionError("LAN TCP stream switch timed out " + secret)
    if stage == "send_switch":
        session.request_stream_switch.side_effect = [error, None]

    def observe(session, packer, *, name, progress, **kwargs):
        progress.update(cpacket_dimensions={"352x288": 1}, frame_capture=None)
        if name == "switch_2_to_1":
            progress["counts"] = {"frame_e0": 4}
            raise error
        return progress, b""

    monkeypatch.setattr(example, "_observe_phase", observe)
    with pytest.raises(QuiiConnectionError):
        example.main(["--host", "127.0.0.1", "--save-frames"])
    report_path = next((tmp_path / "data").glob("*/report.json"))
    text = report_path.read_text()
    report = json.loads(text)
    assert not report["completed"]
    assert report["failure"] == {
        "phase": "switch_2_to_1",
        "stage": stage,
        "type": "QuiiConnectionError",
        "reason": "stream switch timed out",
    }
    assert report["phases"][2]["status"] == "failed"
    assert report["phases"][-1]["status"] == "completed"
    assert report["failures"] == [report["failure"]]
    assert len(report["phases"]) == 5
    assert factory.return_value.__exit__.call_count == 3
    output = capsys.readouterr().out
    assert json.loads(output.splitlines()[-1]) == {"completed": False}
    assert secret not in text and secret not in output


@pytest.mark.parametrize("pending,oversize", [(True, False), (False, True)])
def test_phase_observes_pre_ack_but_does_not_probe_oversize_keyframes(
    monkeypatch, pending, oversize
):
    clock = [0.0]
    monkeypatch.setattr(example.time, "monotonic", lambda: clock[0])
    session = Mock(active_stream=2, stream_switch_pending=pending)

    def receive(**kwargs):
        clock[0] += 1
        return media_message(b"video")

    session.recv_message.side_effect = receive
    packer = Mock(stats={})
    packer.feed.return_value = [
        {
            "frame_tag": 0xE1,
            "width": 640,
            "height": 480,
            "codec": 1,
            "nal_offset": 0,
            "bitstream": (
                b"x" * (2 * 1024 * 1024 + 1) if oversize else b"old-idr"
            ),
        }
    ]
    result, keyframe = example._observe_phase(
        session, packer, name="switched_high", seconds=1
    )
    assert result["counts"]["frame_e1"] == 1
    assert keyframe == (b"" if oversize else b"old-idr")
    assert result["switch_status"] == (
        "unconfirmed" if pending else "not_requested"
    )


def test_ffprobe_uses_only_memory_input_and_returns_dimensions(monkeypatch):
    run = Mock(
        return_value=subprocess.CompletedProcess(
            [], 0, b'{"streams":[{"width":640,"height":480}]}', b""
        )
    )
    monkeypatch.setattr(example.subprocess, "run", run)
    assert example._keyframe_dimensions("ffprobe", b"idr") == {
        "status": "ok",
        "width": 640,
        "height": 480,
    }
    assert run.call_args.kwargs["input"] == b"idr"
    assert run.call_args.kwargs["timeout"] == 5
    args = run.call_args.args[0]
    assert args[args.index("-i") + 1] == "pipe:0"
    assert args[args.index("-protocol_whitelist") + 1] == "pipe"


@pytest.mark.parametrize(
    "output",
    [
        b"not-json",
        b'{"streams":[]}',
        b'{"streams":[{"width":0,"height":480}]}',
    ],
)
def test_invalid_ffprobe_output_is_not_reported_as_resolution(
    monkeypatch, output
):
    monkeypatch.setattr(
        example.subprocess,
        "run",
        Mock(return_value=subprocess.CompletedProcess([], 0, output, b"")),
    )
    assert example._keyframe_dimensions("ffprobe", b"idr") == {
        "status": "ffprobe_failed"
    }


@pytest.mark.parametrize(
    "failure",
    [
        OSError(),
        subprocess.TimeoutExpired("ffprobe", 5),
        subprocess.CalledProcessError(1, "ffprobe"),
    ],
)
def test_ffprobe_failure_is_explicit_metadata(monkeypatch, failure):
    monkeypatch.setattr(example.subprocess, "run", Mock(side_effect=failure))
    assert example._keyframe_dimensions("ffprobe", b"idr") == {
        "status": "ffprobe_failed"
    }


def test_missing_ffmpeg_fails_before_loading_secrets(monkeypatch):
    load = Mock(side_effect=AssertionError("no credential access"))
    monkeypatch.setattr(example.CameraStreamCredentials, "load", load)
    monkeypatch.setattr(
        example.shutil,
        "which",
        lambda name: "ffprobe" if name == "ffprobe" else None,
    )
    with pytest.raises(SystemExit):
        example.main(["--host", "127.0.0.1", "--save-frames"])
    load.assert_not_called()


@pytest.mark.parametrize("interrupted", [False, True])
def test_save_frames_is_private_opt_in_and_writes_report_after_close(
    monkeypatch, tmp_path, capsys, interrupted
):
    monkeypatch.chdir(tmp_path)
    saved = CameraStreamCredentials("synthetic-id", "K" * 32, "private-auth")
    monkeypatch.setattr(
        example.CameraStreamCredentials, "load", Mock(return_value=saved)
    )
    monkeypatch.setattr(example.shutil, "which", lambda name: name)
    factory = MagicMock()
    session = factory.return_value.__enter__.return_value
    session.play_accepted = True
    session.stream_switch_pending = False
    monkeypatch.setattr(example, "LanTcpSession", factory)
    monkeypatch.setattr(
        example, "_keyframe_dimensions", lambda *args: {"status": "ok"}
    )
    paths = []
    active = [False]

    def enter():
        active[0] = True
        return session

    def leave(*args):
        active[0] = False
        return False

    factory.return_value.__enter__.side_effect = enter
    factory.return_value.__exit__.side_effect = leave

    def observe(
        session,
        packer,
        *,
        name,
        seconds,
        capture_path,
        progress,
        readonly_info,
    ):
        assert readonly_info is None
        if interrupted and name == "switch_2_to_1":
            raise KeyboardInterrupt()
        capture = None
        if capture_path is not None:
            paths.append(capture_path)
            capture = {"raw_file": capture_path.name, "samples": []}
        return (
            {
                "phase": name,
                "cpacket_dimensions": {"640x480": 1},
                "frame_capture": capture,
            },
            b"idr",
        )

    def render(*args):
        assert not active[0], "decoder must run only after disconnect"
        return {"status": "no_h264_samples"}

    monkeypatch.setattr(example, "_observe_phase", observe)
    monkeypatch.setattr(example, "_save_frames", render)
    args = ["--host", "127.0.0.1", "--save-frames"]
    if interrupted:
        with pytest.raises(KeyboardInterrupt):
            example.main(args)
    else:
        example.main(args)
    assert factory.return_value.__exit__.call_count == (
        2 if interrupted else 3
    )
    reports = list((tmp_path / "data").glob("lan-diagnostic-*/report.json"))
    assert len(reports) == 1
    result = json.loads(reports[0].read_text())
    assert result["completed"] is not interrupted
    assert [path.name for path in paths] == (
        ["initial_stream_1.h264", "initial_stream_2.h264"]
        if interrupted
        else [
            "initial_stream_1.h264",
            "initial_stream_2.h264",
            "switch_2_to_1.h264",
            "initial_stream_3.h264",
            "switch_3_to_1.h264",
        ]
    )
    if example.os.name != "nt":
        assert reports[0].stat().st_mode & 0o077 == 0
        assert reports[0].parent.stat().st_mode & 0o077 == 0
    assert saved.stream_key not in reports[0].read_text()
    assert saved.auth_code not in reports[0].read_text()
    assert "Private camera images/video" in capsys.readouterr().out


def test_capture_starts_at_keyframe_and_maps_bursty_arrivals(
    monkeypatch, tmp_path
):
    clock = [0.0]
    monkeypatch.setattr(example.time, "monotonic", lambda: clock[0])
    session = Mock(active_stream=1, stream_switch_pending=False)
    tags = iter([0xE0, 0xE1, 0xE0, 0xE0])
    packer = Mock(stats={})

    def receive(**kwargs):
        clock[0] += 1
        tag = next(tags)
        packer.feed.return_value = [
            {
                "frame_tag": tag,
                "width": 640,
                "height": 480,
                "codec": 1,
                "nal_offset": 2,
                "bitstream": b"xxI" if tag == 0xE1 else b"xxP",
            }
        ]
        return media_message(b"video")

    session.recv_message.side_effect = receive
    path = tmp_path / "capture.h264"
    result, _ = example._observe_phase(
        session, packer, name="initial_high", seconds=4, capture_path=path
    )
    assert path.read_bytes() == b"IPP"
    capture = result["frame_capture"]
    assert capture["retained_frames"] == 3 and capture["bytes"] == 3
    assert [sample["frame_index"] for sample in capture["samples"]] == [
        0,
        1,
        1,
    ]
    assert capture["missing_sample_seconds"] == [5.0, 15.0]
    with pytest.raises(FileExistsError):
        example._observe_phase(
            session, packer, name="again", seconds=1, capture_path=path
        )
    assert path.read_bytes() == b"IPP"


def test_capture_limit_stops_before_overflow(monkeypatch, tmp_path):
    clock = [0.0]
    monkeypatch.setattr(example.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(example, "MAX_CAPTURE_BYTES", 1)
    session = Mock(active_stream=1, stream_switch_pending=False)
    packer = Mock(stats={})
    packer.feed.return_value = [
        {
            "frame_tag": 0xE1,
            "width": 640,
            "height": 480,
            "codec": 1,
            "nal_offset": 0,
            "bitstream": b"I",
        }
    ]

    def receive(**kwargs):
        clock[0] += 1
        return media_message(b"video")

    session.recv_message.side_effect = receive
    path = tmp_path / "bounded.h264"
    with pytest.raises(QuiiConnectionError, match="capture exceeds"):
        example._observe_phase(
            session, packer, name="high", seconds=3, capture_path=path
        )
    assert path.read_bytes() == b"I"


def test_frame_extraction_deduplicates_indexes_but_keeps_sample_times(
    monkeypatch, tmp_path
):
    path = tmp_path / "high.h264"
    samples = [
        {"frame_index": i, "target_seconds": t}
        for i, t in [(0, 0), (1, 0.5), (1, 1)]
    ]

    def render(command, **kwargs):
        directory = tmp_path / "high_frames"
        (directory / "frame_01.jpg").write_bytes(b"jpeg1")
        (directory / "frame_02.jpg").write_bytes(b"jpeg2")
        assert command[command.index("-protocol_whitelist") + 1] == "file,pipe"
        assert command[command.index("-fps_mode") + 1] == "passthrough"
        assert "-vsync" not in command and "-xerror" in command
        assert kwargs["timeout"] == 60
        return subprocess.CompletedProcess(
            command,
            0,
            (
                "frame:0 pts:0\n"
                "lavfi.signalstats.SATMIN=0\nlavfi.signalstats.SATHIGH=0\n"
                "lavfi.signalstats.SATAVG=0\nlavfi.signalstats.SATMAX=0\n"
                "frame:1 pts:1\n"
                "lavfi.signalstats.SATAVG=18\nlavfi.signalstats.SATMAX=42\n"
            ),
            "",
        )

    monkeypatch.setattr(example.subprocess, "run", render)
    result = example._save_frames("ffmpeg", path, samples)
    assert result["status"] == "ok"
    assert len(result["samples"]) == 3
    assert result["samples"][0]["SATAVG"] == 0
    assert result["samples"][1]["file"] == result["samples"][2]["file"]
    assert result["samples"][2]["SATAVG"] == 18


@pytest.mark.parametrize(
    "failure", [OSError(), subprocess.TimeoutExpired("ffmpeg", 60)]
)
def test_frame_extraction_errors_are_reported(monkeypatch, tmp_path, failure):
    monkeypatch.setattr(example.subprocess, "run", Mock(side_effect=failure))
    assert example._save_frames(
        "ffmpeg", tmp_path / "high.h264", [{"frame_index": 0}]
    ) == {"status": "ffmpeg_failed", "error": {"type": type(failure).__name__}}


def test_old_ffmpeg_falls_back_only_for_missing_fps_mode(
    monkeypatch, tmp_path
):
    commands = []

    def run(command, **kwargs):
        commands.append(list(command))
        if len(commands) == 1:
            raise subprocess.CalledProcessError(
                1, command, stderr="Unrecognized option 'fps_mode'."
            )
        assert command[command.index("-vsync") + 1] == "0"
        assert "-fps_mode" not in command and "-xerror" in command
        (tmp_path / "high_frames" / "frame_01.jpg").write_bytes(b"jpeg")
        return subprocess.CompletedProcess(
            command,
            0,
            "frame:0\nlavfi.signalstats.SATAVG=0\nlavfi.signalstats.SATMAX=0\n",
            "",
        )

    monkeypatch.setattr(example.subprocess, "run", run)
    result = example._save_frames(
        "ffmpeg", tmp_path / "high.h264", [{"frame_index": 0}]
    )
    assert result["status"] == "ok" and len(commands) == 2
    assert "-fps_mode" in commands[0]


def test_ffmpeg_decode_error_is_not_retried_or_dumped(monkeypatch, tmp_path):
    run = Mock(
        side_effect=subprocess.CalledProcessError(
            1, "ffmpeg", stderr="private/path/secret invalid H.264 data"
        )
    )
    monkeypatch.setattr(example.subprocess, "run", run)
    result = example._save_frames(
        "ffmpeg", tmp_path / "high.h264", [{"frame_index": 0}]
    )
    assert run.call_count == 1
    assert result == {
        "status": "ffmpeg_failed",
        "error": {"type": "CalledProcessError", "returncode": 1},
    }
    assert "secret" not in json.dumps(result)


def test_startup_error_report_identifies_initial_phase(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    saved = CameraStreamCredentials("synthetic-id", "K" * 32, "private-auth")
    monkeypatch.setattr(
        example.CameraStreamCredentials, "load", lambda _: saved
    )
    monkeypatch.setattr(example.shutil, "which", lambda name: name)
    factory = MagicMock()
    factory.return_value.__enter__.side_effect = QuiiConnectionError(
        "LAN TCP setup was rejected"
    )
    monkeypatch.setattr(example, "LanTcpSession", factory)
    with pytest.raises(QuiiConnectionError):
        example.main(["--host", "127.0.0.1", "--save-frames"])
    report = json.loads(
        next((tmp_path / "data").glob("*/report.json")).read_text()
    )
    assert report["failure"]["stage"] == "open"
    assert report["failure"]["phase"] == "initial_stream_1"
    assert report["failure"]["reason"] == "setup was rejected"
    assert report["phases"][0]["status"] == "failed"
    assert len(report["failures"]) == len(report["phases"]) == 3


def test_failure_metadata_keeps_safe_status_and_socket_errno():
    error = QuiiConnectionError("LAN TCP receive failed; private-auth")
    error.__cause__ = OSError(10054, "private/path")
    assert example._failure_details(error) == {
        "type": "QuiiConnectionError",
        "reason": "receive failed",
        "cause_type": type(error.__cause__).__name__,
        "errno": 10054,
    }
    assert example._failure_details(
        QuiiConnectionError(
            "LAN TCP stream switch rejected with status 2 private-auth"
        )
    ) == {
        "type": "QuiiConnectionError",
        "reason": "stream switch rejected",
        "status": 2,
    }


@pytest.mark.parametrize(
    "stdout",
    [
        "",
        "frame:0\nlavfi.signalstats.SATAVG=nan\nlavfi.signalstats.SATMAX=0\n",
    ],
)
def test_missing_or_invalid_chroma_does_not_claim_success(
    monkeypatch, tmp_path, stdout
):
    def render(command, **kwargs):
        (tmp_path / "high_frames" / "frame_01.jpg").write_bytes(b"jpeg")
        return subprocess.CompletedProcess(command, 0, stdout, "")

    monkeypatch.setattr(example.subprocess, "run", render)
    result = example._save_frames(
        "ffmpeg", tmp_path / "high.h264", [{"frame_index": 0}]
    )
    assert result["status"] == "ffmpeg_failed"
    assert result["error"]["type"] == "ValueError"


def test_real_ffmpeg_extracts_grayscale_then_color_without_network(tmp_path):
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        pytest.skip("optional FFmpeg integration requires external tools")
    path = tmp_path / "synthetic.h264"
    generated = subprocess.run(
        [
            ffmpeg,
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
            "-pix_fmt",
            "yuv420p",
            "-f",
            "h264",
            str(path),
        ],
        capture_output=True,
        timeout=15,
    )
    if generated.returncode and b"Unknown encoder" in generated.stderr:
        pytest.skip("synthetic fixture requires libx264")
    assert generated.returncode == 0, generated.stderr.decode(
        "utf-8", "replace"
    )
    assert example._keyframe_dimensions(ffprobe, path.read_bytes()) == {
        "status": "ok",
        "width": 64,
        "height": 48,
    }
    result = example._save_frames(
        ffmpeg,
        path,
        [
            {"frame_index": 0, "target_seconds": 0},
            {"frame_index": 2, "target_seconds": 1},
        ],
    )
    assert result["status"] == "ok"
    assert result["samples"][0]["SATAVG"] == 0
    assert result["samples"][1]["SATAVG"] > 50
