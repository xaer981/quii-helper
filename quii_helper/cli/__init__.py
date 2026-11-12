"""Installed commands for quii-helper."""

import argparse
import sys
from collections.abc import Sequence
from dataclasses import replace
from importlib.util import find_spec
from pathlib import Path
from shutil import which
from time import monotonic

from quii_helper import Camera
from quii_helper.camera.connection.credentials import CameraStreamCredentials
from quii_helper.config import AutonomousConfig
from quii_helper.config.settings_loader import (
    CHANNEL_SETTINGS,
    STREAM_SETTINGS,
    SettingsLoader,
)
from quii_helper.protocols.tcp.live.session import (
    LanTcpConnectError,
    LanTcpRejectedError,
    validate_lan_config,
)
from quii_helper.support.errors import ConfigurationError

RTSP_STARTUP_TIMEOUT_SECONDS = 45.0


class _PreflightError(ValueError):
    """An error whose message is safe to display on the CLI."""


def _setting_problem(loader: SettingsLoader, error: ConfigurationError) -> str:
    if not error.setting or not error.hint:
        return "Check LAN settings in .env and the process environment."
    names = {
        CHANNEL_SETTINGS[0]: CHANNEL_SETTINGS,
        STREAM_SETTINGS[0]: STREAM_SETTINGS,
    }.get(error.setting, (error.setting,))
    name, source = loader.setting_origin(*names)
    return f"{name} ({source}): {error.hint}"


def _load_lan_config(credentials: Path | None) -> AutonomousConfig:
    try:
        loader = SettingsLoader()
    except (OSError, ValueError):
        raise _PreflightError(
            "Cannot resolve the application directory."
        ) from None
    try:
        config = AutonomousConfig.from_settings(loader.load())
    except ConfigurationError as exc:
        raise _PreflightError(_setting_problem(loader, exc)) from None
    except (OSError, ValueError):
        raise _PreflightError(
            "Cannot load configuration. Check that .env is readable UTF-8."
        ) from None
    if config.connection_mode != "lan":
        name, source = loader.setting_origin("CAMERA_CONNECTION_MODE")
        raise _PreflightError(
            f"{name} ({source}): Set it to lan for this check."
        )
    if not config.device_host:
        name, source = loader.setting_origin("CAMERA_DEVICE_HOST")
        raise _PreflightError(
            f"{name} ({source}): Set CAMERA_DEVICE_HOST to the camera's numeric IP address."
        )
    if credentials is not None:
        try:
            saved = CameraStreamCredentials.load(credentials)
        except ConfigurationError as exc:
            if exc.setting and exc.hint:
                raise _PreflightError(
                    f"{exc.setting.lower()} (saved JSON): {exc.hint}"
                ) from None
            raise _PreflightError(
                "Invalid saved JSON. Pass a file written by CameraStreamCredentials.save()."
            ) from None
        except (OSError, ValueError, RuntimeError):
            raise _PreflightError(
                "Cannot open saved JSON. Check the file and permissions for --credentials."
            ) from None
        config = replace(
            config, stream_key=saved.stream_key, auth_code=saved.auth_code
        )
    for name, value in (
        ("STREAM_KEY", config.stream_key),
        ("AUTH_CODE", config.auth_code),
    ):
        if not value:
            _, source = loader.setting_origin(name)
            raise _PreflightError(
                f"{name} ({source}): Set {name}, or pass --credentials FILE."
            )
    try:
        validate_lan_config(config)
    except ConfigurationError as exc:
        raise _PreflightError(_setting_problem(loader, exc)) from None
    return config


def _rtsp_port(value: str) -> int:
    try:
        port = int(value)
        if 1 <= port <= 65535:
            return port
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("use a port from 1 to 65535")


def _serve_lan_rtsp(
    config: AutonomousConfig, port: int, *, reconnect: bool
) -> int:
    def status(message: str) -> None:
        if message.startswith("LAN RTSP reconnect"):
            print(message, flush=True)

    stream = None
    try:
        camera = Camera(config=config, status=status)
        try:
            stream = camera.serve_rtsp(port=port, reconnect=reconnect)
        except OSError:
            print(
                "Cannot start the local RTSP listener. Try a different --port.",
                file=sys.stderr,
            )
            return 1
        with stream:
            print("Waiting for LAN preview video...", flush=True)
            deadline = monotonic() + RTSP_STARTUP_TIMEOUT_SECONDS
            while not stream.playback_started:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    stream.wait(timeout=0)
                    if stream.playback_started:
                        break
                    print(
                        "No playable H.264 video before the startup deadline. "
                        "Check CAMERA_CHANNEL and CAMERA_STREAM.",
                        file=sys.stderr,
                    )
                    return 1
                stream.wait(timeout=min(remaining, 0.25))
            if stream.ready:
                print(f"RTSP stream ready: {stream.url}", flush=True)
            stream.wait()
    except KeyboardInterrupt:
        return 130
    except LanTcpConnectError:
        problem = "Cannot connect to the camera over LAN. Check CAMERA_DEVICE_HOST and CAMERA_STREAM_PORT."
    except LanTcpRejectedError:
        problem = "The camera rejected LAN setup or playback. Check the saved key/auth pair and stream selection."
    except Exception:
        problem = (
            "The LAN RTSP stream stopped after startup."
            if stream is not None and stream.playback_started
            else "LAN preview failed before RTSP was ready. Check device compatibility and the saved key/auth pair."
        )
    else:
        return 0
    print(problem, file=sys.stderr)
    return 1


def _report_doctor(problem: str | None) -> int:
    if problem is None:
        print("LAN configuration: OK (offline only).")
    else:
        print(f"LAN configuration: FAIL. {problem}")
    ffmpeg = "found on PATH" if which("ffmpeg") else "not found on PATH"
    audio = "module found" if find_spec("miniaudio") else "module not found"
    print(f"FFmpeg: {ffmpeg} (needed for JPEG/MP4 rendering).")
    print(f"miniaudio: {audio} (needed for microphone/headphones).")
    return 1 if problem else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run an offline settings check or start a LAN-only RTSP stream."""
    parser = argparse.ArgumentParser(prog="quii-helper")
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="check LAN settings offline")
    rtsp = commands.add_parser("rtsp", help="serve LAN video on localhost")
    rtsp.add_argument(
        "--port",
        type=_rtsp_port,
        default=8554,
        help="local RTSP port (default: 8554)",
    )
    rtsp.add_argument(
        "--reconnect",
        action="store_true",
        help="retry a lost LAN preview on the same RTSP URL after startup",
    )
    for command in (doctor, rtsp):
        command.add_argument(
            "--credentials",
            type=Path,
            metavar="FILE",
            help="saved key/auth JSON",
        )
    args = parser.parse_args(argv)

    try:
        config = _load_lan_config(args.credentials)
    except _PreflightError as exc:
        if args.command == "doctor":
            return _report_doctor(str(exc))
        print(f"LAN configuration: FAIL. {exc}", file=sys.stderr)
        return 1
    if args.command == "doctor":
        return _report_doctor(None)
    return _serve_lan_rtsp(config, args.port, reconnect=args.reconnect)
