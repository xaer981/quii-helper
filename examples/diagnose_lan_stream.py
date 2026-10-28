"""Compare initial-high and switched-high LAN playback using a saved key.

Run from a checkout: python -m examples.diagnose_lan_stream --host CAMERA_IP.
Requires ffprobe on PATH. Add --save-frames (and FFmpeg) to retain private
H.264/JPEG samples under data/. No .env/assets, cloud, talk or door commands
are used. The lower-level session API is internal, not a stable Camera method.
"""

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from collections import Counter
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from quii_helper import AutonomousConfig, CameraStreamCredentials
from quii_helper.media.frames.assembler_state import (
    VIDEO_FRAME_TAGS,
    access_unit_from_frame,
)
from quii_helper.media.frames.cframe_pack import QuiiCFramePack
from quii_helper.protocols.tcp.live.session import LanTcpSession
from quii_helper.support.errors import QuiiConnectionError

SAMPLE_SECONDS = (0.0, 0.5, 1.0, 5.0, 15.0)
MAX_CAPTURE_BYTES = 64 * 1024 * 1024


def _failure_details(error: BaseException) -> dict[str, Any]:
    """Report error categories, never arbitrary exception text or credentials."""
    result: dict[str, Any] = {"type": type(error).__name__}
    message = str(error)
    for reason in (
        "stream switch timed out",
        "stream switch send failed",
        "command SHA256 check failed",
        "receive failed",
        "startup failed",
        "invalid LAN TCP packet type",
        "unsupported LAN TCP crypto/SHA profile",
        "setup was rejected",
        "no video frames in probe phase",
        "probe phase was not acknowledged",
        "stream switch was not acknowledged",
        "diagnostic H.264 capture exceeds 64 MiB",
        "frame sample count mismatch",
        "missing chroma measurements",
        "invalid chroma measurement",
        "empty frame image",
    ):
        if reason in message:
            result["reason"] = reason
            break
    status = re.search(
        r"(play|stream switch) rejected with status (\d{1,3})\b", message
    )
    if status and int(status[2]) <= 255:
        result.update(reason=f"{status[1]} rejected", status=int(status[2]))
    if isinstance(error, subprocess.CalledProcessError):
        result["returncode"] = error.returncode
    cause = error.__cause__
    if cause is not None:
        result["cause_type"] = type(cause).__name__
    for item in (error, cause):
        if isinstance(item, OSError):
            if isinstance(item.errno, int):
                result["errno"] = item.errno
            winerror = getattr(item, "winerror", None)
            if isinstance(winerror, int):
                result["winerror"] = winerror
    return result


def _open_private(path: Path, mode: str = "wb") -> Any:
    """Create an owner-only artifact exclusively inside the private run folder."""
    descriptor = os.open(
        path,
        os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0),
        0o600,
    )
    return os.fdopen(descriptor, mode)


def _save_frames(
    ffmpeg: str, path: Path, samples: list[dict[str, Any]]
) -> dict[str, Any]:
    """Decode selected frames after disconnecting; report chroma, not a verdict."""
    if not samples:
        return {"status": "no_h264_samples"}
    indexes = sorted({sample["frame_index"] for sample in samples})
    directory = path.with_name(path.stem + "_frames")
    expression = "+".join(f"eq(n\\,{index})" for index in indexes)
    try:
        directory.mkdir(mode=0o700)
        command = [
            ffmpeg,
            "-nostdin",
            "-n",
            "-v",
            "error",
            "-xerror",
            "-threads",
            "2",
            "-protocol_whitelist",
            "file,pipe",
            "-f",
            "h264",
            "-i",
            str(path),
            "-vf",
            "select=" + expression + ",signalstats,metadata=mode=print:file=-",
            "-fps_mode",
            "passthrough",
            "-threads",
            "2",
            "-q:v",
            "2",
            str(directory / "frame_%02d.jpg"),
        ]
        try:
            result = subprocess.run(
                command, check=True, capture_output=True, text=True, timeout=60
            )
        except subprocess.CalledProcessError as error:
            # Older FFmpeg lacks fps_mode; retry only an option-parser failure.
            if "Unrecognized option 'fps_mode'" not in (error.stderr or ""):
                raise
            index = command.index("-fps_mode")
            command[index : index + 2] = ["-vsync", "0"]
            result = subprocess.run(
                command, check=True, capture_output=True, text=True, timeout=60
            )
        chroma: list[dict[str, float]] = []
        for line in result.stdout.splitlines():
            if line.startswith("frame:"):
                chroma.append({})
            elif chroma and line.startswith("lavfi.signalstats.SAT"):
                name, value = line.split("=", 1)
                field = name.rsplit(".", 1)[-1]
                if field in {"SATAVG", "SATMAX"}:
                    chroma[-1][field] = float(value)
        images = sorted(directory.glob("frame_*.jpg"))
        if not len(images) == len(indexes) == len(chroma):
            raise ValueError("frame sample count mismatch")
        if any(set(values) != {"SATAVG", "SATMAX"} for values in chroma):
            raise ValueError("missing chroma measurements")
        if any(
            not math.isfinite(value) or value < 0
            for values in chroma
            for value in values.values()
        ):
            raise ValueError("invalid chroma measurement")
        if any(image.stat().st_size == 0 for image in images):
            raise ValueError("empty frame image")
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        return {"status": "ffmpeg_failed", "error": _failure_details(error)}
    selected = dict(zip(indexes, zip(images, chroma)))
    return {
        "status": "ok",
        "samples": [
            {
                **sample,
                "file": selected[sample["frame_index"]][0]
                .relative_to(path.parent)
                .as_posix(),
                **selected[sample["frame_index"]][1],
            }
            for sample in samples
        ],
    }


def _keyframe_dimensions(ffprobe: str, keyframe: bytes) -> dict[str, Any]:
    """Inspect one bounded H.264 keyframe in memory; never guess from CPacket."""
    if not keyframe:
        return {"status": "no_h264_keyframe"}
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-protocol_whitelist",
                "pipe",
                "-f",
                "h264",
                "-i",
                "pipe:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "json",
            ],
            input=keyframe,
            capture_output=True,
            check=True,
            timeout=5,
        )
        stream = json.loads(result.stdout)["streams"][0]
        width, height = int(stream["width"]), int(stream["height"])
        if width <= 0 or height <= 0:
            raise ValueError("invalid dimensions")
    except (
        OSError,
        subprocess.SubprocessError,
        ValueError,
        KeyError,
        IndexError,
        TypeError,
    ):
        return {"status": "ffprobe_failed"}
    return {"status": "ok", "width": width, "height": height}


def _observe_phase(
    session: LanTcpSession,
    packer: QuiiCFramePack,
    *,
    name: str,
    seconds: float,
    capture_path: Path | None = None,
    progress: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bytes]:
    """Collect one window without running subprocesses or losing ACK media."""
    started = time.monotonic()
    counts: Counter[str] = Counter()
    sizes: Counter[str] = Counter()
    audio: Counter[str] = Counter()
    replies: list[int] = []
    keyframe = b""
    samples: list[dict[str, Any]] = []
    retained = 0
    retained_bytes = 0
    first_video: float | None = None
    result = progress if progress is not None else {}
    active_stream = session.active_stream
    switch_pending = session.stream_switch_pending
    try:
        with (
            _open_private(capture_path) if capture_path else nullcontext()
        ) as output:
            while (remaining := seconds - (time.monotonic() - started)) > 0:
                try:
                    message = session.recv_message(timeout=min(0.5, remaining))
                except TimeoutError:
                    continue
                active_stream = session.active_stream
                switch_pending = session.stream_switch_pending
                header = message["header"]
                if not message["is_media"]:
                    counts[f"command_{header.packet_type:02x}"] += 1
                    if header.packet_type == 9:
                        replies.append(header.raw[11])
                    continue
                for frame in packer.feed(message["payload"]):
                    tag = frame["frame_tag"]
                    counts[f"frame_{tag:02x}"] += 1
                    if tag in VIDEO_FRAME_TAGS:
                        sizes[f'{frame["width"]}x{frame["height"]}'] += 1
                        codec = frame["codec"]
                        if session.stream_switch_pending or not (
                            codec == 1 or 0x10 <= codec <= 0x1F
                        ):
                            continue
                        unit = access_unit_from_frame(frame)
                        if tag == 0xE1 and len(unit) <= 2 * 1024 * 1024:
                            keyframe = unit
                        if (
                            output is None
                            or not unit
                            or (not retained and tag != 0xE1)
                        ):
                            continue
                        if retained_bytes + len(unit) > MAX_CAPTURE_BYTES:
                            raise QuiiConnectionError(
                                "diagnostic H.264 capture exceeds 64 MiB"
                            )
                        output.write(unit)
                        retained_bytes += len(unit)
                        now = time.monotonic()
                        if first_video is None:
                            first_video = now
                        elapsed = now - first_video
                        while (
                            len(samples) < len(SAMPLE_SECONDS)
                            and elapsed >= SAMPLE_SECONDS[len(samples)]
                        ):
                            samples.append(
                                {
                                    "target_seconds": SAMPLE_SECONDS[
                                        len(samples)
                                    ],
                                    "frame_index": retained,
                                    "arrival_seconds": round(elapsed, 4),
                                }
                            )
                        retained += 1
                    elif tag == 0xE3:
                        audio[
                            f'{frame["codec"]}/{frame["sample_rate"]}/{frame["channels"]}'
                        ] += 1
    finally:
        result.update(
            {
                "phase": name,
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "acknowledged_stream": active_stream,
                "switch_pending": switch_pending,
                "switch_reply_statuses": replies,
                "counts": dict(counts),
                "cpacket_dimensions": dict(sizes),
                "last_keyframe_h264": {"status": "not_analyzed"},
                "audio_codec_rate_channels": dict(audio),
                "cframe": dict(packer.stats),
                "frame_capture": (
                    {
                        "raw_file": capture_path.name,
                        "retained_frames": retained,
                        "bytes": retained_bytes,
                        "samples": samples,
                        "missing_sample_seconds": list(
                            SAMPLE_SECONDS[len(samples) :]
                        ),
                    }
                    if capture_path
                    else None
                ),
            }
        )
    return result, keyframe


def main(argv: list[str] | None = None) -> None:
    """Compare two sessions; save private A/B samples only with --save-frames.

    Only the explicit IP and saved credentials are used. Firmware rejection or
    missing acknowledgement stops the test without retries or cloud fallback.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="Camera LAN IP address")
    parser.add_argument("--channel", type=int, default=1)
    parser.add_argument(
        "--credentials",
        type=Path,
        default=Path("data/stream_credentials.json"),
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=20,
        help="Receive seconds per high comparison (6-30); warmup/restore use 6",
    )
    parser.add_argument(
        "--save-frames",
        action="store_true",
        help="Save private H.264/JPEG/report files under data/; requires FFmpeg",
    )
    args = parser.parse_args(argv)
    if not math.isfinite(args.seconds) or not 6 <= args.seconds <= 30:
        parser.error("--seconds must be finite and between 6 and 30")
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        parser.error("ffprobe must be installed and available on PATH")
    ffmpeg = shutil.which("ffmpeg") if args.save_frames else None
    if args.save_frames and ffmpeg is None:
        parser.error("--save-frames requires ffmpeg on PATH")
    saved = CameraStreamCredentials.load(args.credentials)
    directory = None
    if args.save_frames:
        Path("data").mkdir(exist_ok=True)
        directory = Path(
            tempfile.mkdtemp(prefix="lan-diagnostic-", dir="data")
        ).resolve()
        print(
            json.dumps(
                {
                    "private_artifacts": str(directory),
                    "warning": "Private camera images/video; do not upload",
                }
            ),
            flush=True,
        )
    captures: list[tuple[dict[str, Any], bytes]] = []
    completed = False
    failure: dict[str, Any] | None = None
    stage = "open"
    current_phase: dict[str, Any] | None = None
    plans = (
        (1, (("initial_high", None, args.seconds),)),
        (
            2,
            (
                ("initial_low", None, 6),
                ("switched_high", 1, args.seconds),
                ("switched_back_low", 2, 6),
            ),
        ),
    )
    try:
        for initial_stream, phases in plans:
            stage = "open"
            current_phase = {"phase": phases[0][0], "status": "opening"}
            config = AutonomousConfig(
                connection_mode="lan",
                device_host=args.host,
                device_id=saved.device_id,
                stream_key=saved.stream_key,
                auth_code=saved.auth_code,
                channel=args.channel,
                stream=initial_stream,
                connect_timeout=5,
            )
            packer = QuiiCFramePack()
            start = len(captures)
            with LanTcpSession(config) as session:
                for name, target, seconds in phases:
                    current_phase = {"phase": name, "status": "in_progress"}
                    captures.append((current_phase, b""))
                    print(json.dumps({"starting_phase": name}), flush=True)
                    if target is not None:
                        stage = "send_switch"
                        session.request_stream_switch(target, timeout=5)
                    capture_path = (
                        directory / (name + ".h264")
                        if directory
                        and name in {"initial_high", "switched_high"}
                        else None
                    )
                    stage = "receive"
                    result, keyframe = _observe_phase(
                        session,
                        packer,
                        name=name,
                        seconds=seconds,
                        capture_path=capture_path,
                        progress=current_phase,
                    )
                    current_phase.update(result)
                    result = current_phase
                    captures[-1] = (result, keyframe)
                    stage = "validate"
                    if not result["cpacket_dimensions"]:
                        raise QuiiConnectionError(
                            "no video frames in probe phase"
                        )
                    if (
                        not session.play_accepted
                        or session.stream_switch_pending
                    ):
                        raise QuiiConnectionError(
                            "probe phase was not acknowledged"
                        )
                    if session.active_stream != (
                        initial_stream if target is None else target
                    ):
                        raise QuiiConnectionError(
                            "stream switch was not acknowledged"
                        )
                    result["cframe"] = dict(packer.stats)
                    result["status"] = "completed"
            # No decoder subprocess runs while a camera socket is open.
            stage = "analyze"
            for result, keyframe in captures[start:]:
                current_phase = result
                result["last_keyframe_h264"] = _keyframe_dimensions(
                    ffprobe, keyframe
                )
                capture = result["frame_capture"]
                if (
                    capture is not None
                    and directory is not None
                    and ffmpeg is not None
                ):
                    result["saved_frames"] = _save_frames(
                        ffmpeg,
                        directory / capture["raw_file"],
                        capture["samples"],
                    )
                print(json.dumps(result), flush=True)
        completed = True
    except BaseException as error:
        failure = {"stage": stage, **_failure_details(error)}
        if current_phase is not None:
            failure["phase"] = current_phase["phase"]
            current_phase.update(status="failed", error=failure)
            if not captures or captures[-1][0] is not current_phase:
                if not any(item is current_phase for item, _ in captures):
                    captures.append((current_phase, b""))
        print(json.dumps({"completed": False, "failure": failure}), flush=True)
        raise
    finally:
        if directory is not None:
            with _open_private(directory / "report.json", "w") as report:
                json.dump(
                    {
                        "completed": completed,
                        "failure": failure,
                        "phases": [result for result, _ in captures],
                    },
                    report,
                    indent=2,
                )
    print(json.dumps({"completed": True}), flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
