"""Typed observations from the device-local archive."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from quii_helper.device.cgi.models import DeviceRecordFileInfo


@dataclass(frozen=True)
class CameraArchiveEvent:
    """An archive entry first observed after this watcher's baseline.

    Attributes:
        record: Original picture/video metadata, not a confirmed call. Hidden
            from repr because archive URLs and raw metadata may be private.
        observed_at: Aware UTC time when the query returned this entry. Device
            timestamps remain unchanged inside ``record``.
        kind: Observation type; never implies that a doorbell rang.
    """

    record: DeviceRecordFileInfo = field(repr=False)
    observed_at: datetime
    kind: Literal["archive_record_added"] = field(
        default="archive_record_added", init=False
    )
