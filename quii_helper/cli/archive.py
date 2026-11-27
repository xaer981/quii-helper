"""Read a device-local archive through the existing Camera CGI API."""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import tempfile
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from typing import TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

from quii_helper import Camera, CameraStreamCredentials
from quii_helper.camera.device_cgi.archive import archive_record_key
from quii_helper.cli.configuration import (
    _load_cli_config,
    _PreflightError,
    _setting_problem,
)
from quii_helper.cli.presentation import rich_table
from quii_helper.config import AutonomousConfig
from quii_helper.device.cgi.models import DeviceRecordFileInfo
from quii_helper.device.security.streamkey import validate_stream_credentials
from quii_helper.support.errors import ConfigurationError, QuiiConnectionError

MAX_RECORDS = 10000
_SEARCH_DEFAULTS = {
    "channel": None,
    "file_type": "all",
    "occur_type": "all",
    "stream": "all",
    "max_pages": 32,
    "scheme": "http",
    "cgi_port": None,
}


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


def _device_date(value: str) -> str:
    try:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError
    except ValueError:
        raise argparse.ArgumentTypeError(
            "Use a device-local date: YYYY-MM-DD."
        ) from None
    return value


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


def add_archive_search_options(parser: argparse.ArgumentParser) -> None:
    options = parser.add_argument_group("LAN archive search")
    options.add_argument(
        "--date",
        type=_device_date,
        metavar="YYYY-MM-DD",
        help="search a whole day on the device's clock instead of --from/--to",
    )
    options.add_argument(
        "--from",
        dest="start",
        type=_device_time,
        metavar="TIME",
        help="search start: device-local YYYY-MM-DD HH:MM:SS",
    )
    options.add_argument(
        "--to",
        dest="end",
        type=_device_time,
        metavar="TIME",
        help="search end: device-local YYYY-MM-DD HH:MM:SS",
    )
    options.add_argument(
        "--channel", type=_channel, help="default: CAMERA_CHANNEL / 1"
    )
    options.add_argument(
        "--type",
        dest="file_type",
        choices=("all", "video", "picture"),
        help="default: all (combines video and picture searches)",
    )
    options.add_argument(
        "--occur-type",
        type=_occurrence,
        help="native occurrence filter, e.g. all, manual, event",
    )
    options.add_argument(
        "--stream",
        choices=("all", "main", "sub"),
        help="archive stream filter, not live quality (default: all)",
    )
    options.add_argument(
        "--max-pages",
        type=_positive_int,
        help="page cap per search/type (default: 32)",
    )
    options.add_argument(
        "--scheme", choices=("http", "https"), help="default: http"
    )
    options.add_argument(
        "--cgi-port", type=_port, help="default: HTTP 80 / HTTPS 443"
    )


def resolve_archive_search(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    *,
    saved: bool = False,
) -> None:
    if saved:
        if any(
            getattr(args, name) is not None
            for name in ("date", "start", "end", *_SEARCH_DEFAULTS)
        ):
            parser.error(
                "--from-list cannot be combined with LAN archive search options"
            )
        return
    if args.date is not None:
        if args.start is not None or args.end is not None:
            parser.error("use --date or --from and --to, not both")
        args.start, args.end = f"{args.date} 00:00:00", f"{args.date} 23:59:59"
    elif args.start is None or args.end is None:
        parser.error("provide --date YYYY-MM-DD or both --from and --to")
    if args.start >= args.end:
        parser.error("--from must be before --to (device-local time)")
    for name, default in _SEARCH_DEFAULTS.items():
        if getattr(args, name) is None:
            setattr(args, name, default)


def add_archive_parser(
    commands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> argparse._SubParsersAction[argparse.ArgumentParser]:
    """Register the installed archive list command without loading settings."""
    archive = commands.add_parser(
        "archive", help="LAN: list or download archive media"
    )
    operations = archive.add_subparsers(dest="archive_command", required=True)
    listing = operations.add_parser(
        "list", help="list saved pictures/videos over LAN, without cloud"
    )
    add_archive_search_options(listing)
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
    return operations


def _output_path(path: Path, *, media: bool = False) -> Path:
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
    suffixes = {".jpg", ".jpeg", ".mp4"} if media else {".json"}
    if (
        name == ".env"
        or name.startswith(".env.")
        or (target.suffix.lower() not in suffixes)
    ):
        raise _PreflightError(
            "Output must be a .jpg, .jpeg, or .mp4 file, not an .env file."
            if media
            else "Output must be a .json list, not an .env file."
        )
    if target.is_symlink() or target.exists():
        raise _PreflightError(
            "Output already exists or is a symlink; choose a new file."
        )
    if any(
        parent.exists() and not parent.is_dir() for parent in target.parents
    ):
        raise _PreflightError("Output parent must be a directory.")
    return target


def _load_archive_config(
    credentials: Path | None, *, download: bool = False
) -> AutonomousConfig:
    """Load local credentials, using the saved key only for media downloads."""
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
        if download:
            config = replace(config, stream_key=saved.stream_key)
    if not config.auth_code.strip():
        raise _PreflightError(
            _setting_problem(
                loader,
                ConfigurationError.for_setting(
                    "AUTH_CODE", "Set AUTH_CODE, or pass --credentials FILE."
                ),
            )
        )
    if download and not config.stream_key:
        raise _PreflightError(
            _setting_problem(
                loader,
                ConfigurationError.for_setting(
                    "STREAM_KEY", "Set STREAM_KEY, or pass --credentials FILE."
                ),
            )
        )
    if download:
        try:
            validate_stream_credentials(config.stream_key, config.auth_code)
        except ConfigurationError as exc:
            raise _PreflightError(_setting_problem(loader, exc)) from None
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


def _save_archive_file(target: Path, data: bytes) -> None:
    """Publish a complete file without clobbering a racing writer."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=target.parent,
            prefix=".archive-",
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


def _cell(value: str | int | None) -> str:
    return (
        "?"
        if value is None
        else json.dumps(str(value), ensure_ascii=True)[1:-1]
    )


def _print_table(records: list[ArchiveRecord]) -> None:
    """Escape terminal controls while preserving snapshot row numbers."""
    headers = (
        "INDEX",
        "TYPE",
        "CHANNEL",
        "START",
        "END",
        "OCCURRENCE",
        "SIZE_KiB",
        "FILE",
    )
    rows = []
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
        rows.append([str(index), *(_cell(value) for value in values)])
    if not rich_table(headers, rows, file=sys.stdout):
        print("\t".join(headers))
        for row in rows:
            print("\t".join(row))
    print(f"Records: {len(records)} (complete search).")


def _search_archive(
    args: argparse.Namespace, config: AutonomousConfig
) -> tuple[int, list[DeviceRecordFileInfo]]:
    channel = args.channel if args.channel is not None else config.channel
    if not 1 <= channel <= 65535:
        raise _PreflightError(
            "CAMERA_CHANNEL (or its configured alias): Use an integer from 1 to 65535."
        )
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
    camera = Camera(
        config=config, connection_mode="lan", status=lambda _: None
    )
    try:
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
    except HTTPError as exc:
        raise _PreflightError(
            f"LAN archive search failed: HTTP {exc.code}. Check --scheme, --cgi-port and CGI authentication. Redirects are not followed."
        ) from None
    except Exception as exc:
        reason = exc.reason if isinstance(exc, URLError) else exc
        if isinstance(reason, ssl.SSLCertVerificationError):
            problem = "LAN archive search failed: TLS certificate verification failed. Check the camera certificate, address and trust settings. No insecure retry was attempted."
        else:
            problem = "LAN archive search failed. Check CGI connectivity, authentication and TLS settings."
        raise _PreflightError(problem) from None
    if result.error != 0 or not result.completed:
        raise _PreflightError(
            "Archive query failed or is incomplete; no list was emitted. Narrow the calendar-day range or check --max-pages and device support."
        )
    records: list[DeviceRecordFileInfo] = []
    seen: set[tuple[str, ...]] = set()
    for record in result.records:
        try:
            key = archive_record_key(record)
        except QuiiConnectionError:
            raise _PreflightError(
                "LAN archive search returned invalid record metadata."
            ) from None
        if key not in seen:
            if len(seen) >= MAX_RECORDS:
                raise _PreflightError(
                    "Archive exceeds the 10000-record limit; narrow --from/--to."
                )
            seen.add(key)
            records.append(record)
    return channel, records


def list_archive(args: argparse.Namespace) -> int:
    """Read complete native searches; emit/save no partial successful list."""
    try:
        target = _output_path(args.output) if args.output is not None else None
        config = _load_archive_config(args.credentials)
        channel, matches = _search_archive(args, config)
        records = [_metadata(record) for record in matches]
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
            _save_archive_file(target, data.encode("utf-8"))
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
    except _PreflightError as exc:
        print(f"Archive listing: FAIL. {exc}", file=sys.stderr)
        return 1
    except Exception:
        print(
            "Archive listing or output failed. Check LAN CGI/auth/TLS, storage, and output permissions; check any saved file before retrying. No insecure retry or cloud fallback was attempted.",
            file=sys.stderr,
        )
        return 1
