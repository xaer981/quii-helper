"""Map packed device-local CPacket times to one relative A/V RTP timeline."""

import time

from quii_helper.media.cpacket.header import cpacket_timestamp_ms


class RtpMediaClock:
    """Use device deltas, not TCP arrival bursts; never guess the device timezone."""

    # shortcut: no RTCP sender reports; add them before promising cross-player lip-sync.

    def __init__(self) -> None:
        self.started_at = time.monotonic()
        self._origin: int | None = None
        self._offset_ms = 0

    def timestamp(self, stamp: int, milliseconds: int, rate: int) -> int:
        """Convert native year/month/day/hour/minute/second bits plus milliseconds."""
        device_ms = cpacket_timestamp_ms(stamp, milliseconds)
        if self._origin is None:
            self._origin = device_ms
            self._offset_ms = int((time.monotonic() - self.started_at) * 1000)
        return (
            (device_ms - self._origin + self._offset_ms) * rate // 1000
        ) & 0xFFFFFFFF
