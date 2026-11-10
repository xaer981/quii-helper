"""Bounded synchronous polling over the existing local archive-list API."""

import math
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from http.client import HTTPException
from time import monotonic, sleep

from loguru import logger

from quii_helper.camera.events.models import CameraArchiveEvent
from quii_helper.device.cgi.models import (
    DeviceRecordFileInfo,
    DeviceRecordListInfo,
)
from quii_helper.support.errors import ConfigurationError, QuiiConnectionError


def watch_archive_events(
    read_records: Callable[[], DeviceRecordListInfo],
    *,
    start_time: str,
    end_time: str,
    interval_seconds: float,
    duration_seconds: float,
    max_seen_records: int,
    max_pages: int,
) -> Iterator[CameraArchiveEvent]:
    """Validate bounds now; start network reads only when iterated."""
    interval = _positive_seconds(interval_seconds, "interval_seconds")
    duration = _positive_seconds(duration_seconds, "duration_seconds")
    for name, value in (
        ("max_seen_records", max_seen_records),
        ("max_pages", max_pages),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ConfigurationError(f"{name} must be a positive integer")
    try:
        start = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        end = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        raise ConfigurationError(
            "archive times must use device-local YYYY-MM-DD HH:MM:SS"
        ) from None
    if start >= end:
        raise ConfigurationError("start_time must be before end_time")
    return _observe(read_records, interval, duration, max_seen_records)


def _positive_seconds(value: float, name: str) -> float:
    try:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError
        seconds = float(value)
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError
    except (ValueError, OverflowError):
        raise ConfigurationError(
            f"{name} must be finite and positive"
        ) from None
    return seconds


def _record_key(record: DeviceRecordFileInfo) -> tuple[str, ...]:
    key = (
        record.file_type,
        record.channel_id,
        record.file_name,
        record.picture_index,
        record.start_time,
    )
    if any(not isinstance(value, str) for value in key) or not (
        record.file_name.strip()
    ):
        raise QuiiConnectionError(
            "archive entry has no usable filename or identity fields"
        )
    return key


def _observe(
    read_records: Callable[[], DeviceRecordListInfo],
    interval: float,
    duration: float,
    max_seen_records: int,
) -> Iterator[CameraArchiveEvent]:
    deadline = monotonic() + duration
    seen: set[tuple[str, ...]] = set()
    initialized = False
    while monotonic() < deadline:
        started = monotonic()
        try:
            result = read_records()
        except (ConfigurationError, QuiiConnectionError):
            raise
        except (
            OSError,
            ET.ParseError,
            HTTPException,
            ValueError,
            RuntimeError,
        ) as exc:
            raise QuiiConnectionError(
                "could not read local archive; watcher stopped"
            ) from exc
        if result.error != 0:
            raise QuiiConnectionError(
                f"archive query failed: error={result.error}; watcher stopped"
            )
        if not result.completed:
            raise QuiiConnectionError(
                "archive query incomplete; narrow the time range or "
                "increase max_pages"
            )
        observed_at = datetime.now(timezone.utc)
        pending: dict[tuple[str, ...], DeviceRecordFileInfo] = {}
        for record in result.records:
            key = _record_key(record)
            if key not in seen:
                pending.setdefault(key, record)
                if len(seen) + len(pending) > max_seen_records:
                    raise QuiiConnectionError(
                        "archive watcher reached max_seen_records; "
                        "narrow the time range or increase the limit"
                    )
        seen.update(pending)
        if initialized:
            for record in pending.values():
                yield CameraArchiveEvent(
                    record=record, observed_at=observed_at
                )
        else:
            logger.info("Archive baseline ready. Watching for new entries")
        initialized = True
        now = monotonic()
        next_poll = started + interval
        if next_poll < now:
            next_poll = now + interval
        delay = min(next_poll, deadline) - now
        if delay > 0:
            sleep(delay)
