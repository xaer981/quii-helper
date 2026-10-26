"""Map packed device-local CPacket times to one relative A/V RTP timeline."""

import time
from datetime import datetime


class RtpMediaClock:
    """Use device deltas, not TCP arrival bursts; never guess the device timezone."""

    # shortcut: no RTCP sender reports; add them before promising cross-player lip-sync.

    def __init__(self) -> None:
        self.started_at = time.monotonic()
        self._origin: int | None = None
        self._offset_ms = 0

    def timestamp(self, stamp: int, milliseconds: int, rate: int) -> int:
        """Convert native year/month/day/hour/minute/second bits plus milliseconds."""
        value = datetime(
            2000 + (stamp >> 26),
            (stamp >> 22) & 15,
            (stamp >> 17) & 31,
            (stamp >> 12) & 31,
            (stamp >> 6) & 63,
            stamp & 63,
        )
        if not 0 <= milliseconds < 1000:
            raise ValueError("invalid CPacket milliseconds")
        device_ms = (
            value.toordinal() * 86400
            + value.hour * 3600
            + value.minute * 60
            + value.second
        ) * 1000 + milliseconds
        if self._origin is None:
            self._origin = device_ms
            self._offset_ms = int((time.monotonic() - self.started_at) * 1000)
        return (
            (device_ms - self._origin + self._offset_ms) * rate // 1000
        ) & 0xFFFFFFFF
