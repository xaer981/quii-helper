"""Read a device-local archive through the existing Camera CGI API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import TypedDict
from urllib.parse import urlsplit

from quii_helper import Camera, CameraStreamCredentials
from quii_helper.camera.device_cgi.archive import archive_record_key
from quii_helper.cli.configuration import (
    _load_cli_config,
    _PreflightError,
    _setting_problem,
)
from quii_helper.config import AutonomousConfig
from quii_helper.device.cgi.models import DeviceRecordFileInfo
from quii_helper.support.errors import ConfigurationError

MAX_RECORDS = 10000


class ArchiveRecord(TypedDict):
    """Explicit metadata whitelist; never serialize raw responses or URLs."""

    record_id: str
    file_name: str
    file_type: str
    occur_type: str
    channel_id: str
    start_time: str
    end_time: str
    stream: str
    picture_index: str
    frame_rate: int | None
    file_size_kib: int | None


class ArchiveList(TypedDict):
    """Versioned list snapshot, private metadata but not a credential file."""

    version: int
    device: dict[str, str]
    query: dict[str, str | int]
    records: list[ArchiveRecord]


def _device_time(value: str) -> str:
    """Accept unambiguous device-local calendar times, without UTC guessing."""
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        if parsed.isoformat(sep=" ", timespec="seconds") != value:
            raise ValueError
    except ValueError:
        raise argparse.ArgumentTypeError(
            "Use device-local YYYY-MM-DD HH:MM:SS without a timezone."
        ) from None
    return value


def _positive_int(value: str) -> int:
    try:
        number = int(value)
        if number < 1:
            raise ValueError
    except ValueError:
        raise argparse.ArgumentTypeError("Use a positive integer.") from None
    return number


def _port(value: str) -> int:
    number = _positive_int(value)
    if number > 65535:
        raise argparse.ArgumentTypeError("Use a port from 1 to 65535.")
    return number


def _channel(value: str) -> int:
    number = _positive_int(value)
    if number > 65535:
        raise argparse.ArgumentTypeError("Use a channel from 1 to 65535.")
    return number


def _occurrence(value: str) -> str:
    """Allow firmware-specific filters, but not blank or control characters."""
    if not value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise argparse.ArgumentTypeError(
            "Use a nonempty native occurrence filter."
        )
    return value


def add_archive_parser(
    commands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the installed archive list command without loading settings."""
    archive = commands.add_parser("archive", help="read the local archive")
    operations = archive.add_subparsers(dest="archive_command", required=True)
    listing = operations.add_parser(
        "list", help="list saved pictures/videos over LAN, without cloud"
    )
    listing.add_argument(
        "--from",
        dest="start",
        type=_device_time,
        required=True,
        help="search start: device-local YYYY-MM-DD HH:MM:SS",
    )
    listing.add_argument(
        "--to",
        dest="end",
        type=_device_time,
        required=True,
        help="search end: device-local YYYY-MM-DD HH:MM:SS",
    )
    listing.add_argument(
        "--channel", type=_channel, help="default: CAMERA_CHANNEL / 1"
    )
    listing.add_argument(
        "--type",
        dest="file_type",
        choices=("all", "video", "picture"),
        default="all",
        help="all combines video and picture searches",
    )
    listing.add_argument(
        "--occur-type",
        type=_occurrence,
        default="all",
        help="native occurrence filter, e.g. all, manual, event",
    )
    listing.add_argument(
        "--stream",
        choices=("all", "main", "sub"),
        default="all",
        help="archive stream filter, not live quality (default: all)",
    )
    listing.add_argument(
        "--max-pages",
        type=_positive_int,
        default=32,
        help="page cap per search/type (default: 32)",
    )
    listing.add_argument("--scheme", choices=("http", "https"), default="http")
    listing.add_argument(
        "--cgi-port", type=_port, help="default: HTTP 80 / HTTPS 443"
    )
    listing.add_argument(
        "--credentials",
        type=Path,
        metavar="FILE",
        help="explicit saved key/auth JSON; only device ID/auth are used",
    )
    listing.add_argument(
        "--json",
        action="store_true",
        help="write the list snapshot to stdout instead of a table",
    )
    listing.add_argument(
        "--output",
        type=Path,
        metavar="FILE",
        help="also save private metadata as a new .json file; never replace a file",
    )


def _output_path(path: Path) -> Path:
    """Refuse existing files and unsafe destinations before any camera read."""
    target = path.expanduser().absolute()
    name = target.name.lower()
    if sys.platform == "win32":
        # Skip the drive/UNC anchor, not validation of parent folder names.
        for part in target.parts[1:]:
            if part in {".", ".."}:
                continue
            if part != part.rstrip(" .") or any(
                ord(char) < 32 or char in '<>:"|?*' for char in part
            ):
                raise _PreflightError(
                    "Output path contains an invalid Windows filename."
                )
            if part.split(".", 1)[0].rstrip(" ").upper() in {
                "CON",
                "PRN",
                "AUX",
                "NUL",
                "CONIN$",
                "CONOUT$",
                *(f"COM{i}" for i in "123456789\xb9\xb2\xb3"),
                *(f"LPT{i}" for i in "123456789\xb9\xb2\xb3"),
            }:
                raise _PreflightError(
                    "Output path must not contain a Windows device filename."
                )
    if (
        name == ".env"
        or name.startswith(".env.")
        or target.suffix.lower() != ".json"
    ):
        raise _PreflightError("Output must be a .json list, not an .env file.")
    if target.is_symlink() or target.exists():
        raise _PreflightError(
            "Output already exists or is a symlink; choose a new file."
        )
    if any(
        parent.exists() and not parent.is_dir() for parent in target.parents
    ):
        raise _PreflightError("Output parent must be a directory.")
    return target


def _load_archive_config(credentials: Path | None) -> AutonomousConfig:
    """Require only direct CGI inputs, not playback or cloud credentials."""
    config, loader = _load_cli_config()
    for setting, missing, hint in (
        (
            "CAMERA_CONNECTION_MODE",
            config.connection_mode != "lan",
            "Set it to lan for archive commands.",
        ),
        (
            "CAMERA_DEVICE_HOST",
            not config.device_host.strip(),
            "Set the local camera IP or hostname.",
        ),
    ):
        if missing:
            raise _PreflightError(
                _setting_problem(
                    loader, ConfigurationError.for_setting(setting, hint)
                )
            )
    if credentials is not None:
        try:
            saved = CameraStreamCredentials.load(credentials)
        except (OSError, ValueError, RuntimeError):
            raise _PreflightError(
                "Cannot read saved JSON; check --credentials and its format/permissions."
            ) from None
        if config.device_id and config.device_id != saved.device_id:
            raise _PreflightError(
                "DEVICE_ID and saved JSON refer to different devices."
            )
        config = replace(
            config, device_id=saved.device_id, auth_code=saved.auth_code
        )
    if not config.auth_code.strip():
        raise _PreflightError(
            _setting_problem(
                loader,
                ConfigurationError.for_setting(
                    "AUTH_CODE", "Set AUTH_CODE, or pass --credentials FILE."
                ),
            )
        )
    host = config.device_host.strip()
    try:
        if any(c.isspace() or ord(c) < 32 or c in "/\\@?#" for c in host):
            raise ValueError
        parsed = urlsplit(f"http://{host}:80/tdkcgi")
        if not parsed.hostname or parsed.port != 80:
            raise ValueError
    except ValueError:
        raise _PreflightError(
            "CAMERA_DEVICE_HOST must be an IP or hostname, not a URL or host:port."
        ) from None
    return replace(config, device_host=host)


def _metadata(record: DeviceRecordFileInfo) -> ArchiveRecord:
    """Keep native selectors for future download, without raw/URL payloads."""
    return ArchiveRecord(
        record_id=record.record_id,
        file_name=record.file_name,
        file_type=record.file_type,
        occur_type=record.occur_type,
        channel_id=record.channel_id,
        start_time=record.start_time,
        end_time=record.end_time,
        stream=record.stream,
        picture_index=record.picture_index,
        frame_rate=record.frame_rate,
        file_size_kib=record.file_size,
    )


def _save_list(target: Path, data: str) -> None:
    """Publish a complete UTF-8 snapshot without clobbering a racing writer."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=target.parent,
            prefix=".archive-list-",
            delete=False,
        ) as output:
            temporary = Path(output.name)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.link(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _print_table(records: list[ArchiveRecord]) -> None:
    """Escape terminal controls while preserving snapshot row numbers."""
    print("INDEX\tTYPE\tCHANNEL\tSTART\tEND\tOCCURRENCE\tSIZE_KiB\tFILE")
    for index, record in enumerate(records, 1):
        values = (
            record["file_type"],
            record["channel_id"],
            record["start_time"],
            record["end_time"],
            record["occur_type"],
            record["file_size_kib"],
            record["file_name"],
        )
        cells = [
            (
                "?"
                if value is None
                else json.dumps(str(value), ensure_ascii=True)[1:-1]
            )
            for value in values
        ]
        print(f"{index}\t" + "\t".join(cells))
    print(f"Records: {len(records)} (complete search).")


def list_archive(args: argparse.Namespace) -> int:
    """Read complete native searches; emit/save no partial successful list."""
    try:
        target = _output_path(args.output) if args.output is not None else None
        config = _load_archive_config(args.credentials)
        channel = args.channel if args.channel is not None else config.channel
        if not 1 <= channel <= 65535:
            raise _PreflightError(
                "CAMERA_CHANNEL (or its configured alias): Use an integer from 1 to 65535."
            )
    except KeyboardInterrupt:
        print("Archive listing interrupted.", file=sys.stderr)
        return 130
    except _PreflightError as exc:
        print(f"Archive configuration: FAIL. {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError):
        print(
            "Cannot resolve archive output; check the path and permissions.",
            file=sys.stderr,
        )
        return 1
    if args.scheme == "https" and not config.tls_verify:
        print(
            "WARNING: TLS certificate verification is disabled by configuration.",
            file=sys.stderr,
        )
    elif args.scheme == "http":
        print(
            "WARNING: CGI HTTP sends authentication without TLS; use only a trusted LAN.",
            file=sys.stderr,
        )
    print(
        "Reading the configured LAN archive; no cloud requests.",
        file=sys.stderr,
    )
    port = (
        args.cgi_port
        if args.cgi_port is not None
        else (443 if args.scheme == "https" else 80)
    )
    records: list[ArchiveRecord] = []
    seen: set[tuple[str, ...]] = set()
    try:
        camera = Camera(
            config=config, connection_mode="lan", status=lambda _: None
        )
        result = camera.list_record_files(
            start_time=args.start.replace(" ", "t") + "z",
            end_time=args.end.replace(" ", "t") + "z",
            channel_id=channel,
            file_type=args.file_type,
            occur_type=args.occur_type,
            stream=args.stream,
            max_pages=args.max_pages,
            scheme=args.scheme,
            port=port,
            debug=False,
        )
        if result.error != 0 or not result.completed:
            print(
                "Archive query failed or is incomplete; no list was emitted. Narrow the calendar-day range or check --max-pages and device support.",
                file=sys.stderr,
            )
            return 1
        for record in result.records:
            key = archive_record_key(record)
            if key not in seen:
                if len(seen) >= MAX_RECORDS:
                    print(
                        "Archive exceeds the 10000-record limit; narrow --from/--to.",
                        file=sys.stderr,
                    )
                    return 1
                seen.add(key)
                records.append(_metadata(record))
        snapshot = ArchiveList(
            version=1,
            device={"host": config.device_host, "device_id": config.device_id},
            query={
                "start_time": args.start,
                "end_time": args.end,
                "channel_id": channel,
                "file_type": args.file_type,
                "occur_type": args.occur_type,
                "stream": args.stream,
            },
            records=records,
        )
        data = (
            json.dumps(snapshot, ensure_ascii=True, indent=2, allow_nan=False)
            + "\n"
        )
        if target is not None:
            _save_list(target, data)
        if args.json:
            print(data, end="")
        else:
            _print_table(records)
        if target is not None:
            print(
                "Archive list saved; metadata is private, not a credential file.",
                file=sys.stderr,
            )
        return 0
    except KeyboardInterrupt:
        print(
            "Archive listing interrupted; stopped without cloud fallback.",
            file=sys.stderr,
        )
        return 130
    except Exception:
        print(
            "Archive listing or output failed. Check LAN CGI/auth/TLS, storage, and output permissions; check any saved file before retrying. No insecure retry or cloud fallback was attempted.",
            file=sys.stderr,
        )
        return 1
