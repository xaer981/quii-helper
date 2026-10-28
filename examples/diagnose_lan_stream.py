"""Compare LAN selectors or opt-in native handshakes using a saved key.

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
from uuid import uuid4

from quii_helper import AutonomousConfig, CameraStreamCredentials
from quii_helper.media.frames.assembler_state import (
    VIDEO_FRAME_TAGS,
    access_unit_from_frame,
)
from quii_helper.media.frames.cframe_pack import QuiiCFramePack
from quii_helper.protocols.tcp.live.packet_builder import (
    validate_live_identity,
)
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
        "separate media encryption is not supported",
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


def _record_failure(
    error: BaseException,
    stage: str,
    phase: dict[str, Any] | None,
    captures: list[tuple[dict[str, Any], bytes]],
) -> dict[str, Any]:
    """Retain a safe failure even if opening or sending failed before receive."""
    failure = {"stage": stage, **_failure_details(error)}
    if phase is not None:
        failure["phase"] = phase["phase"]
        phase.update(status="failed", error=failure)
        if not any(item is phase for item, _ in captures):
            captures.append((phase, b""))
    print(json.dumps({"completed": False, "failure": failure}), flush=True)
    return failure


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
    """Measure received frames, including media before an optional switch ACK."""
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
    last_video: float | None = None
    video_frames = 0
    first_retained_video: float | None = None
    result = progress if progress is not None else {}
    switch_pending = session.stream_switch_pending
    switch_requested = switch_pending
    try:
        with (
            _open_private(capture_path) if capture_path else nullcontext()
        ) as output:
            while (remaining := seconds - (time.monotonic() - started)) > 0:
                try:
                    message = session.recv_message(timeout=min(0.5, remaining))
                except TimeoutError:
                    continue
                switch_pending = session.stream_switch_pending
                arrived = time.monotonic()
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
                        video_frames += 1
                        if first_video is None:
                            first_video = arrived
                        last_video = arrived
                        sizes[f'{frame["width"]}x{frame["height"]}'] += 1
                        codec = frame["codec"]
                        if not (codec == 1 or 0x10 <= codec <= 0x1F):
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
                        if first_retained_video is None:
                            first_retained_video = arrived
                        elapsed = arrived - first_retained_video
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
        elapsed = time.monotonic() - started
        span = (
            last_video - first_video
            if first_video is not None and last_video is not None
            else 0.0
        )
        result.update(
            {
                "phase": name,
                "elapsed_seconds": round(elapsed, 3),
                "switch_status": (
                    "not_requested"
                    if not switch_requested
                    else (
                        "acknowledged"
                        if not switch_pending and 0 in replies
                        else "unconfirmed"
                    )
                ),
                "switch_pending": switch_pending,
                "switch_reply_statuses": replies,
                "video_timing": {
                    "frames": video_frames,
                    "first_arrival_seconds": (
                        round(first_video - started, 4)
                        if first_video is not None
                        else None
                    ),
                    "last_arrival_seconds": (
                        round(last_video - started, 4)
                        if last_video is not None
                        else None
                    ),
                    "arrival_span_seconds": round(span, 4),
                    "arrival_fps": (
                        round((video_frames - 1) / span, 3)
                        if video_frames > 1 and span > 0
                        else None
                    ),
                    "window_fps": (
                        round(video_frames / elapsed, 3)
                        if elapsed > 0
                        else None
                    ),
                },
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
    """Compare selectors or handshakes; retain files only on explicit opt-in.

    Each selector starts independently. A connection failure stops that session,
    not the remaining selectors. Missing switch ACKs do not stop observation or
    imply success. Only the explicit IP/key are used, with no retries/fallback.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="Camera LAN IP address")
    parser.add_argument("--channel", type=int, default=1)
    parser.add_argument(
        "--compare-handshakes",
        action="store_true",
        help="Compare path and OEM setup/FastPlay with/without a client ID; no switches",
    )
    parser.add_argument(
        "--oem",
        help="Original app CAMERA_OEM; required by --compare-handshakes",
    )
    parser.add_argument(
        "--stream",
        type=int,
        choices=(1, 2, 3),
        help="One selector for --compare-handshakes (default: 1)",
    )
    parser.add_argument(
        "--credentials",
        type=Path,
        default=Path("data/stream_credentials.json"),
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=20,
        help="Receive seconds per observation window (6-30)",
    )
    parser.add_argument(
        "--save-frames",
        action="store_true",
        help="Save private H.264/JPEG/report files under data/; requires FFmpeg",
    )
    args = parser.parse_args(argv)
    if args.compare_handshakes:
        if args.oem is None:
            parser.error("--compare-handshakes requires --oem CAMERA_OEM")
        try:
            validate_live_identity(args.oem.replace(",", ""), "")
        except ValueError:
            parser.error(
                "--oem must be nonempty, at most 256 UTF-8 bytes, no NUL"
            )
    elif args.oem is not None or args.stream is not None:
        parser.error("--oem and --stream require --compare-handshakes")
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
    failures: list[dict[str, Any]] = []
    first_error: QuiiConnectionError | None = None
    stage = "open"
    current_phase: dict[str, Any] | None = None
    plans: tuple[
        tuple[int, str, str, tuple[tuple[str, int | None], ...]], ...
    ] = (
        (1, "setup_path", "", (("initial_stream_1", None),)),
        (
            2,
            "setup_path",
            "",
            (("initial_stream_2", None), ("switch_2_to_1", 1)),
        ),
        (
            3,
            "setup_path",
            "",
            (("initial_stream_3", None), ("switch_3_to_1", 1)),
        ),
    )
    if args.compare_handshakes:
        # Same format as vEye Pro's UUID fallback, not its real Android ID.
        client_id = uuid4().hex
        plans = tuple(
            (args.stream or 1, handshake, identity, ((name, None),))
            for name, handshake, identity in (
                ("handshake_setup_path", "setup_path", ""),
                ("handshake_setup_oem", "setup_oem", ""),
                ("handshake_fast_oem", "fast_oem", ""),
                ("handshake_setup_oem_client", "setup_oem", client_id),
                ("handshake_fast_oem_client", "fast_oem", client_id),
            )
        )
    try:
        for initial_stream, handshake, client_id, phases in plans:
            stage = "open"
            profile = {
                "handshake": handshake,
                "client_id_present": bool(client_id),
            }
            current_phase = {
                **profile,
                "phase": phases[0][0],
                "status": "opening",
                "initial_stream": initial_stream,
                "requested_stream": initial_stream,
            }
            config = AutonomousConfig(
                connection_mode="lan",
                device_host=args.host,
                device_id=saved.device_id,
                stream_key=saved.stream_key,
                auth_code=saved.auth_code,
                oem=args.oem or "",
                channel=args.channel,
                stream=initial_stream,
                connect_timeout=5,
            )
            packer = QuiiCFramePack()
            start = len(captures)
            try:
                with LanTcpSession(
                    config, handshake=handshake, client_id=client_id
                ) as session:
                    for name, target in phases:
                        current_phase = {
                            **profile,
                            "phase": name,
                            "status": "in_progress",
                            "initial_stream": initial_stream,
                            "requested_stream": (
                                initial_stream if target is None else target
                            ),
                        }
                        captures.append((current_phase, b""))
                        print(json.dumps({"starting_phase": name}), flush=True)
                        if target is not None:
                            stage = "send_switch"
                            # One switch per connection prevents late-ACK ambiguity.
                            session.request_stream_switch(target, timeout=None)
                        capture_path = (
                            directory / (name + ".h264") if directory else None
                        )
                        stage = "receive"
                        result, keyframe = _observe_phase(
                            session,
                            packer,
                            name=name,
                            seconds=args.seconds,
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
                        if not session.play_accepted:
                            raise QuiiConnectionError(
                                "probe phase was not acknowledged"
                            )
                        result["status"] = "completed"
            except QuiiConnectionError as error:
                failures.append(
                    _record_failure(error, stage, current_phase, captures)
                )
                if first_error is None:
                    first_error = error
            # No decoder subprocess runs while a camera socket is open.
            stage = "analyze"
            for result, keyframe in captures[start:]:
                current_phase = result
                result["last_keyframe_h264"] = _keyframe_dimensions(
                    ffprobe, keyframe
                )
                capture = result.get("frame_capture")
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
        completed = not failures
    except BaseException as error:
        failures.append(_record_failure(error, stage, current_phase, captures))
        raise
    finally:
        if directory is not None:
            with _open_private(directory / "report.json", "w") as report:
                json.dump(
                    {
                        "completed": completed,
                        "failure": failures[0] if failures else None,
                        "failures": failures,
                        "phases": [result for result, _ in captures],
                    },
                    report,
                    indent=2,
                )
    print(json.dumps({"completed": completed}), flush=True)
    if first_error is not None:
        raise first_error


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
