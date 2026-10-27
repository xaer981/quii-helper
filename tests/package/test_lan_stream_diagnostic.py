"""Offline checks for the opt-in saved-key LAN diagnostic example."""

import importlib
import json
import shutil
import subprocess
from unittest.mock import MagicMock, Mock

import pytest

from quii_helper import CameraStreamCredentials
from quii_helper.support.errors import QuiiConnectionError

example = importlib.import_module("examples.diagnose_lan_stream")


@pytest.mark.parametrize("failed_phase", [None, "switched_high"])
def test_example_is_lan_only_and_closes_on_switch_failure(
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

    def observe(session, packer, *, name, seconds, capture_path):
        if name == failed_phase:
            raise QuiiConnectionError("synthetic switch rejection")
        session.active_stream = (
            1 if name in {"initial_high", "switched_high"} else 2
        )
        assert capture_path is None
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
    assert [config.stream for config in configs] == [1, 2]
    for config in configs:
        assert config.connection_mode == "lan"
        assert config.channel == 2 and config.device_host == "127.0.0.1"
        assert config.stream_key == saved.stream_key
        assert config.auth_code == saved.auth_code
        assert not config.cloud_account and not config.cloud_password
    requests = [
        call.args[0] for call in session.request_stream_switch.call_args_list
    ]
    assert requests == ([1] if failed_phase else [1, 2])
    assert factory.return_value.__exit__.call_count == 2
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
    packer = Mock()
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
            {"is_media": True, "payload": b"video", "header": Mock()},
            {"is_media": False, "header": Mock(packet_type=9, raw=bytes(32))},
            {"is_media": True, "payload": b"audio", "header": Mock()},
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
    assert keyframe == b"synthetic-h264"
    inspect_frame.assert_not_called()


@pytest.mark.parametrize("pending,oversize", [(True, False), (False, True)])
def test_phase_does_not_probe_pre_ack_or_oversize_keyframes(
    monkeypatch, pending, oversize
):
    clock = [0.0]
    monkeypatch.setattr(example.time, "monotonic", lambda: clock[0])
    session = Mock(active_stream=2, stream_switch_pending=pending)

    def receive(**kwargs):
        clock[0] += 1
        return {"is_media": True, "payload": b"video", "header": Mock()}

    session.recv_message.side_effect = receive
    packer = Mock()
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
    assert keyframe == b""


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

    def observe(session, packer, *, name, seconds, capture_path):
        if interrupted and name == "switched_high":
            raise KeyboardInterrupt()
        session.active_stream = (
            1 if name in {"initial_high", "switched_high"} else 2
        )
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
        # Both context exits have occurred before B rendering; A needs only one.
        assert factory.return_value.__exit__.call_count >= len(paths)
        return {"status": "no_h264_samples"}

    monkeypatch.setattr(example, "_observe_phase", observe)
    monkeypatch.setattr(example, "_save_frames", render)
    args = ["--host", "127.0.0.1", "--save-frames"]
    if interrupted:
        with pytest.raises(KeyboardInterrupt):
            example.main(args)
    else:
        example.main(args)
    assert factory.return_value.__exit__.call_count == 2
    reports = list((tmp_path / "data").glob("lan-diagnostic-*/report.json"))
    assert len(reports) == 1
    result = json.loads(reports[0].read_text())
    assert result["completed"] is not interrupted
    assert [path.name for path in paths] == (
        ["initial_high.h264"]
        if interrupted
        else ["initial_high.h264", "switched_high.h264"]
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
    packer = Mock()

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
        return {"is_media": True, "payload": b"video", "header": Mock()}

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
    packer = Mock()
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
        return {"is_media": True, "payload": b"video", "header": Mock()}

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
    ) == {"status": "ffmpeg_failed"}


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
    assert example._save_frames(
        "ffmpeg", tmp_path / "high.h264", [{"frame_index": 0}]
    ) == {"status": "ffmpeg_failed"}


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
