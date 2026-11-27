"""Device-local archive intervals independent of firmware time-of-day filters."""

import re
from dataclasses import replace
from datetime import datetime

from quii_helper.device.cgi.models import (
    DeviceRecordFileInfo,
    DeviceRecordListInfo,
)
from quii_helper.support.errors import ConfigurationError, QuiiConnectionError


def archive_record_key(record: DeviceRecordFileInfo) -> tuple[str, ...]:
    """Identify one archive entry without conflating photo indexes or channels."""
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


def combine_archive_searches(
    searches: dict[str, DeviceRecordListInfo],
) -> DeviceRecordListInfo:
    """Combine complete video/picture searches; retain per-search diagnostics."""
    completed = set(searches) == {"video", "picture"} and all(
        result.error == 0 and result.completed for result in searches.values()
    )
    records: dict[tuple[str, ...], DeviceRecordFileInfo] = {}
    if completed:
        for result in searches.values():
            for record in result.records:
                records.setdefault(archive_record_key(record), record)
    return DeviceRecordListInfo(
        error=next(
            (result.error for result in searches.values() if result.error), 0
        ),
        records=list(records.values()),
        pages=[page for result in searches.values() for page in result.pages],
        completed=completed,
        searches=searches,
    )


def _parse_time(value: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}[ Tt][0-9]{2}:[0-9]{2}:[0-9]{2}[Zz]?",
        value,
    ):
        raise ValueError("invalid device-local timestamp")
    return datetime.strptime(
        value[:10] + " " + value[11:19], "%Y-%m-%d %H:%M:%S"
    )


def parse_archive_interval(
    start_time: str, end_time: str
) -> tuple[datetime, datetime]:
    """Validate a continuous, inclusive device-local interval without UTC shifts."""
    try:
        start, end = _parse_time(start_time), _parse_time(end_time)
    except ValueError:
        raise ConfigurationError(
            "archive times must use device-local YYYY-MM-DD HH:MM:SS or "
            "YYYY-MM-DDtHH:MM:SSz; legacy T-separated timestamps are accepted"
        ) from None
    if start >= end:
        raise ConfigurationError("start_time must be before end_time")
    return start, end


def filter_archive_interval(
    result: DeviceRecordListInfo, start: datetime, end: datetime
) -> DeviceRecordListInfo:
    """Filter returned records; retain native pages and completion/error status."""
    if result.error != 0:
        return result
    records = []
    for record in result.records:
        try:
            first = _parse_time(record.start_time)
            if record.file_type == "picture":
                last = first
            elif record.end_time:
                last = _parse_time(record.end_time)
                if last < first:
                    raise ValueError("reversed record timestamps")
            elif first < start:
                raise ValueError("unknown end of an earlier recording")
            else:
                # A known start inside the interval proves overlap without an end.
                last = first
        except ValueError:
            raise QuiiConnectionError(
                "archive entry has missing, invalid, or ambiguous timestamps; "
                "cannot filter the requested interval reliably"
            ) from None
        if first <= end and last >= start:
            records.append(record)
    return (
        result
        if records == result.records
        else replace(result, records=records)
    )
