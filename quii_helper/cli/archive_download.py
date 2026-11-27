"""Download one record chosen from a LAN search or a saved list."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import replace
from datetime import datetime
from ipaddress import ip_address
from pathlib import Path

from quii_helper import Camera, CameraDeviceRecordFileInfo
from quii_helper.cli.archive import (
    MAX_RECORDS,
    _cell,
    _load_archive_config,
    _output_path,
    _positive_int,
    _save_archive_file,
    _search_archive,
    add_archive_search_options,
    resolve_archive_search,
)
from quii_helper.cli.configuration import _PreflightError
from quii_helper.cli.presentation import display_path, print_status, rich_table
from quii_helper.support.errors import (
    ConfigurationError,
    MediaRenderError,
)

MAX_LIST_BYTES = 16 * 1024 * 1024
PAGE_SIZE = 12


class _SelectionCancelled(Exception):
    pass


def _timeout(value: str) -> float:
    try:
        seconds = float(value)
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError
    except ValueError:
        raise argparse.ArgumentTypeError(
            "Use a finite positive timeout in seconds."
        ) from None
    return seconds


def add_archive_download_parser(
    operations: argparse._SubParsersAction[argparse.ArgumentParser],
) -> argparse.ArgumentParser:
    """Register download without reading configuration or metadata."""
    parser = operations.add_parser(
        "download",
        help="download one saved JPEG or MP4 over LAN, without cloud",
        description="Select a record in the terminal, or download a row from a saved list.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  quii-helper archive download --date 2026-11-27 --type video\n"
            "  quii-helper archive download --from-list records.json --index 2 --output clip.mp4"
        ),
    )
    saved = parser.add_argument_group("Saved list (no prompts or CGI search)")
    saved.add_argument(
        "--from-list",
        type=Path,
        metavar="FILE",
        help="JSON exported by archive list --output",
    )
    saved.add_argument(
        "--index",
        type=_positive_int,
        help="one-based record index in this exact list",
    )
    parser.add_argument(
        "--output",
        type=Path,
        metavar="FILE",
        help="new .jpg/.jpeg or .mp4 destination; required with --from-list",
    )
    parser.add_argument(
        "--credentials",
        type=Path,
        metavar="FILE",
        help="explicit saved key/auth JSON; no automatic lookup",
    )
    parser.add_argument(
        "--timeout",
        type=_timeout,
        default=30.0,
        help="total download/remux deadline in seconds (default: 30)",
    )
    parser.add_argument(
        "--max-bytes",
        type=_positive_int,
        default=16 * 1024 * 1024,
        help="received and returned media byte cap (default: 16777216)",
    )
    add_archive_search_options(parser)
    return parser


def _read_record(
    path: Path, index: int
) -> tuple[CameraDeviceRecordFileInfo, str, str]:
    """Open a bounded v1 snapshot and take only fields needed by the API."""
    try:
        source = path.expanduser()
        if (
            source.suffix.lower() != ".json"
            or source.name.lower().startswith(".env.")
            or not source.is_file()
        ):
            raise ValueError
        with source.open("rb") as stream:
            data = stream.read(MAX_LIST_BYTES + 1)
        if len(data) > MAX_LIST_BYTES:
            raise _PreflightError(
                "Archive list exceeds the 16 MiB input limit."
            )
        snapshot = json.loads(data.decode("utf-8"))
    except _PreflightError:
        raise
    except (OSError, ValueError, RecursionError):
        raise _PreflightError(
            "Cannot read archive list; pass a regular UTF-8 JSON export."
        ) from None

    if (
        not isinstance(snapshot, dict)
        or type(snapshot.get("version")) is not int
        or snapshot["version"] != 1
        or not isinstance(snapshot.get("device"), dict)
        or not isinstance(snapshot.get("query"), dict)
        or not isinstance(snapshot.get("records"), list)
        or len(snapshot["records"]) > MAX_RECORDS
    ):
        raise _PreflightError("Expected a version-1 archive list export.")
    host = snapshot["device"].get("host")
    device_id = snapshot["device"].get("device_id")
    if not isinstance(host, str) or not host or not isinstance(device_id, str):
        raise _PreflightError("Archive list has invalid device metadata.")
    records = snapshot["records"]
    if not 1 <= index <= len(records):
        raise _PreflightError("Archive index is outside the saved list.")
    row = records[index - 1]
    if not isinstance(row, dict):
        raise _PreflightError("Selected archive entry is invalid.")
    name, kind, start, picture_index = (
        row.get(key)
        for key in ("file_name", "file_type", "start_time", "picture_index")
    )
    fps = row.get("frame_rate")
    if (
        not isinstance(name, str)
        or not name
        or kind not in ("picture", "video")
        or not isinstance(start, str)
        or not isinstance(picture_index, str)
        or (fps is not None and type(fps) is not int)
    ):
        raise _PreflightError(
            "Selected archive entry has invalid media metadata."
        )
    return (
        CameraDeviceRecordFileInfo(
            file_name=name,
            file_type=kind,
            start_time=start,
            picture_index=picture_index,
            frame_rate=fps,
        ),
        host,
        device_id,
    )


def _prompt(message: str) -> str:
    print_status(message, "bold cyan", file=sys.stderr)
    try:
        return input().strip()
    except EOFError:
        raise _SelectionCancelled from None


def _select_record(records: list[CameraDeviceRecordFileInfo]) -> int:
    if not records:
        raise _PreflightError(
            "No archive records found; try another date, channel or type."
        )
    offset = 0
    while True:
        end = min(offset + PAGE_SIZE, len(records))
        headers = (
            "#",
            "START (DEVICE TIME)",
            "CH",
            "TYPE",
            "OCCURRENCE",
            "KiB",
        )
        rows = [
            (
                str(index),
                _cell(record.start_time)
                .replace("t", " ", 1)
                .removesuffix("z"),
                _cell(record.channel_id),
                _cell(record.file_type),
                _cell(record.occur_type or "-"),
                _cell(record.file_size),
            )
            for index, record in enumerate(records[offset:end], offset + 1)
        ]
        print_status(
            f"LAN archive | Records {offset + 1}-{end} of {len(records)}",
            "bold cyan",
            file=sys.stderr,
        )
        if not rich_table(headers, rows, file=sys.stderr):
            widths = [max(map(len, col)) for col in zip(headers, *rows)]
            for row in (headers, *rows):
                print(
                    "  ".join(
                        cell.ljust(width) for cell, width in zip(row, widths)
                    ).rstrip(),
                    file=sys.stderr,
                )
        while True:
            controls = ["number to select"]
            if end < len(records):
                controls.append("n next")
            if offset:
                controls.append("p previous")
            controls.append("q cancel")
            choice = _prompt(
                "Choose a record [" + ", ".join(controls) + "]:"
            ).lower()
            if choice == "q":
                raise _SelectionCancelled
            if choice == "n" and end < len(records):
                offset += PAGE_SIZE
                break
            if choice == "p" and offset:
                offset -= PAGE_SIZE
                break
            try:
                index = int(choice)
            except ValueError:
                index = 0
            if offset < index <= end:
                return index
            print_status(
                "Enter a number shown on this page.", "yellow", file=sys.stderr
            )


def _media_extension(record: CameraDeviceRecordFileInfo) -> str:
    if record.file_type == "video":
        return ".mp4"
    if record.file_type == "picture":
        return ".jpg"
    raise _PreflightError(
        "The selected entry is not a supported picture or video."
    )


def _check_extension(target: Path, extension: str) -> None:
    allowed = {".jpg", ".jpeg"} if extension == ".jpg" else {extension}
    if target.suffix.lower() not in allowed:
        raise _PreflightError(
            "Output extension must match the selected media type."
        )


def _select_output(
    record: CameraDeviceRecordFileInfo, index: int, extension: str
) -> Path:
    try:
        stamp = datetime.strptime(
            record.start_time, "%Y-%m-%dt%H:%M:%Sz"
        ).strftime("%Y%m%d-%H%M%S")
        name = f"archive-{stamp}-{index}{extension}"
    except ValueError:
        name = f"archive-{index}{extension}"
    while True:
        entered = _prompt(f"Save as [{name}] (Enter to accept, q to cancel):")
        if entered.lower() == "q":
            raise _SelectionCancelled
        try:
            target = _output_path(Path(entered or name), media=True)
            _check_extension(target, extension)
            return target
        except _PreflightError as exc:
            print_status(str(exc), "yellow", file=sys.stderr)


def download_archive(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> int:
    """Reuse the LAN media API and publish only on successful completion."""
    saved = args.from_list is not None
    resolve_archive_search(parser, args, saved=saved)
    if saved and (args.index is None or args.output is None):
        parser.error("--from-list requires both --index and --output")
    if not saved:
        if args.index is not None:
            parser.error(
                "--index requires --from-list; search results can change"
            )
        if not (sys.stdin.isatty() and sys.stderr.isatty()):
            parser.error(
                "selection requires a terminal; use --from-list FILE --index N --output FILE without one"
            )
    try:
        target = (
            _output_path(args.output, media=True)
            if args.output is not None
            else None
        )
        if saved:
            record, host, device_id = _read_record(args.from_list, args.index)
            assert target is not None
            _check_extension(target, _media_extension(record))
        config = _load_archive_config(args.credentials, download=True)
        if saved:
            if config.device_host != host or (
                device_id and config.device_id != device_id
            ):
                raise _PreflightError(
                    "Archive list does not match the configured device; export a fresh list."
                )
        else:
            host = config.device_host
        # CGI can use bracketed IPv6; the existing TCP API takes a numeric IP.
        tcp_host = (
            host[1:-1] if host.startswith("[") and host.endswith("]") else host
        )
        try:
            ip_address(tcp_host)
        except ValueError:
            raise _PreflightError(
                "CAMERA_DEVICE_HOST must be a numeric IP for archive downloads."
            ) from None
        if not saved:
            _, records = _search_archive(args, config)
            index = _select_record(records)
            record = records[index - 1]
            extension = _media_extension(record)
            if target is None:
                target = _select_output(record, index, extension)
            else:
                _check_extension(target, extension)
            print_status(
                "Downloading one record over LAN...", "cyan", file=sys.stderr
            )
        assert target is not None
        camera = Camera(
            config=replace(config, device_host=tcp_host),
            connection_mode="lan",
            status=lambda _: None,
        )
        try:
            data = camera.download_record(
                record, timeout=args.timeout, max_bytes=args.max_bytes
            )
        except (ConfigurationError, MediaRenderError):
            raise
        except Exception:
            raise _PreflightError(
                "LAN archive transfer failed. Check the device, --timeout and --max-bytes."
            ) from None
        try:
            _save_archive_file(target, data)
        except FileExistsError:
            raise _PreflightError(
                "Output appeared during download and was not replaced; choose a new file."
            ) from None
        except OSError:
            raise _PreflightError(
                "Cannot save archive media. Check the destination, permissions and hard link support."
            ) from None
        summary = f"Archive download saved ({len(data)} bytes)."
        if saved:
            print(summary)
        else:
            print_status(summary, "bold green", file=sys.stderr)
            print_status(
                f"File: {display_path(target)}", "green", file=sys.stderr
            )
        return 0
    except _SelectionCancelled:
        print("Archive download cancelled; no file saved.", file=sys.stderr)
        return 130
    except KeyboardInterrupt:
        print("Archive download interrupted.", file=sys.stderr)
        return 130
    except _PreflightError as exc:
        message = str(exc)
    except ConfigurationError:
        message = (
            "Invalid LAN settings or unsupported archive selectors. Check the "
            "configured numeric IP, saved credentials and native record metadata."
        )
    except MediaRenderError:
        message = (
            "MP4 export failed. Check FFmpeg and the private data directory."
        )
    except (OSError, ValueError):
        message = "Cannot prepare archive download. Check the input and output paths and permissions."
    except Exception:
        message = "Archive download did not complete. Check whether the destination exists before retrying."
    print(message, file=sys.stderr)
    return 1
