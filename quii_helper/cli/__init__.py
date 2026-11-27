"""Installed commands for quii-helper."""

import argparse
import ssl
import sys
from collections.abc import Sequence
from dataclasses import replace
from importlib.util import find_spec
from pathlib import Path
from shutil import which
from time import monotonic
from urllib.error import URLError

from quii_helper import Camera
from quii_helper.camera.connection.credentials import CameraStreamCredentials
from quii_helper.cli.archive import (
    add_archive_parser,
    list_archive,
    resolve_archive_search,
)
from quii_helper.cli.archive_download import (
    add_archive_download_parser,
    download_archive,
)
from quii_helper.cli.configuration import (
    _load_cli_config,
    _PreflightError,
    _setting_problem,
)
from quii_helper.cli.presentation import display_path, print_status
from quii_helper.config import AutonomousConfig
from quii_helper.config.settings_loader import SettingsLoader as SettingsLoader
from quii_helper.config.validation import (
    REQUIRED_CAMERA_APP_FIELDS,
    is_missing_config_value,
)
from quii_helper.protocols.tcp.live.session import (
    LanTcpConnectError,
    LanTcpRejectedError,
    validate_lan_config,
)
from quii_helper.support.errors import ConfigurationError

RTSP_STARTUP_TIMEOUT_SECONDS = 45.0


def _load_lan_config(credentials: Path | None) -> AutonomousConfig:
    config, loader = _load_cli_config()
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


def _load_cloud_config() -> AutonomousConfig:
    config, loader = _load_cli_config(scope="cloud")
    required = {
        "cloud_account": "CLOUD_ACCOUNT",
        "cloud_password": "CLOUD_PASSWORD",
        "device_id": "DEVICE_ID",
        **REQUIRED_CAMERA_APP_FIELDS,
    }
    for field, name in required.items():
        value = getattr(config, field)
        if is_missing_config_value(value):
            hint = (
                "Use a positive integer from your app/region."
                if isinstance(value, int)
                else f"Set {name} for your cloud account and app."
            )
            raise _PreflightError(
                _setting_problem(
                    loader,
                    ConfigurationError.for_setting(name, hint),
                    scope="cloud",
                )
            )
    return replace(config, connection_mode="cloud")


def _bootstrap(output: Path, *, overwrite: bool) -> int:
    """Explicitly fetch cloud credentials and publish a private JSON file."""
    try:
        target = output.expanduser().absolute()
        name = target.name.lower()
        if sys.platform == "win32":
            # Win32 trims trailing dots/spaces; NTFS streams alias the same file.
            name = name.split(":", 1)[0].rstrip(" .")
        if name == ".env" or name.startswith(".env."):
            raise _PreflightError(
                "Output must not be an .env configuration file."
            )
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise _PreflightError(
                "Output must be a regular file, not a symlink or directory."
            )
        if target.exists() and not overwrite:
            raise _PreflightError(
                "Output already exists. Use --overwrite only to deliberately replace it; no cloud request was made."
            )
        config = _load_cloud_config()
        target.parent.mkdir(parents=True, exist_ok=True)
        if not config.tls_verify:
            print(
                "WARNING: TLS certificate verification is disabled by configuration.",
                file=sys.stderr,
            )
        print_status("Contacting cloud for login and device token...", "cyan")
        try:
            credentials = Camera(
                config=config, status=lambda _: None
            ).fetch_stream_credentials()
        except (ssl.SSLCertVerificationError, URLError) as exc:
            verification_failed = isinstance(
                exc, ssl.SSLCertVerificationError
            ) or isinstance(
                getattr(exc, "reason", None), ssl.SSLCertVerificationError
            )
            problem = (
                "TLS certificate verification failed. Check the cloud endpoint and certificate trust; no insecure retry was attempted."
                if verification_failed
                else "Cloud bootstrap failed before saving. Check cloud connectivity and TLS settings."
            )
            print(problem, file=sys.stderr)
            return 1
        except Exception:
            print(
                "Cloud bootstrap failed before saving. Check cloud account/app/region settings, connectivity and TLS.",
                file=sys.stderr,
            )
            return 1
        try:
            credentials.save(target, overwrite=overwrite)
        except FileExistsError:
            print(
                "Output appeared during bootstrap and was not replaced. Inspect it before retrying; --overwrite permits replacement.",
                file=sys.stderr,
            )
            return 1
        except Exception:
            print(
                "Cannot save streaming credentials. Check output permissions and filesystem support; do not repeat the cloud request blindly.",
                file=sys.stderr,
            )
            return 1
    except KeyboardInterrupt:
        return 130
    except _PreflightError as exc:
        print(f"Cloud bootstrap: FAIL. {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError):
        print(
            "Cannot prepare the output destination. Check its path and permissions; no cloud request was made.",
            file=sys.stderr,
        )
        return 1
    print_status(
        "Streaming credentials saved. Keep the JSON private and reuse it with --credentials for LAN playback.",
        "bold green",
    )
    if sys.stdout.isatty():
        print(f"File: {display_path(target)}")
        print(
            "Next: quii-helper rtsp --credentials FILE (replace FILE with the saved path)."
        )
    return 0


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
            print_status(message, "yellow")

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
            print_status("Waiting for LAN preview video...", "cyan")
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
                print_status(f"RTSP stream ready: {stream.url}", "bold green")
                if sys.stdout.isatty():
                    retry = "on" if reconnect else "off"
                    print(
                        f"Channel {config.channel} | Stream {config.stream} | Reconnect {retry}"
                    )
                    print(
                        "Open the URL in VLC. Press Ctrl+C to stop.",
                        flush=True,
                    )
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


def _report_doctor(
    problem: str | None, *, saved_credentials: bool = False
) -> int:
    if problem is None:
        print_status("LAN configuration: OK (offline only).", "bold green")
    else:
        print_status(f"LAN configuration: FAIL. {problem}", "bold red")
    ffmpeg = "found on PATH" if which("ffmpeg") else "not found on PATH"
    audio = "module found" if find_spec("miniaudio") else "module not found"
    print(f"FFmpeg: {ffmpeg} (needed for JPEG/MP4 rendering).")
    print(f"miniaudio: {audio} (needed for microphone/headphones).")
    if problem is None:
        command = "quii-helper rtsp"
        if saved_credentials:
            command += " --credentials FILE"
        print(f"Next: {command} to check live video over LAN.")
    return 1 if problem else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run offline checks, cloud bootstrap, LAN RTSP or local archive commands."""
    parser = argparse.ArgumentParser(
        prog="quii-helper",
        description="Work with QUII cameras and intercoms. LAN commands never fall back to cloud.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Start here:\n"
            "  quii-helper doctor                       Check configuration offline\n"
            "  quii-helper rtsp                         Open LAN video in VLC\n"
            "  quii-helper archive --help               Browse saved media\n"
            "\nUse COMMAND --help for command options."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    download = add_archive_download_parser(add_archive_parser(commands))
    bootstrap = commands.add_parser(
        "bootstrap",
        help="cloud: fetch and save a key/auth pair explicitly",
    )
    bootstrap.add_argument(
        "--output",
        type=Path,
        default=Path("data/stream_credentials.json"),
        metavar="FILE",
        help="private JSON destination (default: data/stream_credentials.json)",
    )
    bootstrap.add_argument(
        "--overwrite",
        action="store_true",
        help="deliberately fetch again and replace an existing credentials file",
    )
    doctor = commands.add_parser(
        "doctor", help="offline: check LAN settings and tools"
    )
    rtsp = commands.add_parser(
        "rtsp", help="LAN: serve live video on localhost"
    )
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

    if args.command == "archive":
        if args.archive_command == "download":
            return download_archive(download, args)
        resolve_archive_search(parser, args)
        return list_archive(args)

    if args.command == "bootstrap":
        return _bootstrap(args.output, overwrite=args.overwrite)

    try:
        config = _load_lan_config(args.credentials)
    except _PreflightError as exc:
        if args.command == "doctor":
            return _report_doctor(str(exc))
        print(f"LAN configuration: FAIL. {exc}", file=sys.stderr)
        return 1
    if args.command == "doctor":
        return _report_doctor(
            None, saved_credentials=args.credentials is not None
        )
    return _serve_lan_rtsp(config, args.port, reconnect=args.reconnect)
