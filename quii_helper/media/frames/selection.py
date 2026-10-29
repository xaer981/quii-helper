"""Wall-clock snapshot warmup without discarding H.264 reference frames."""

from dataclasses import dataclass


@dataclass
class SnapshotWarmup:
    """Wait for a new decodable video frame after an optional warmup."""

    seconds: float = 0.0
    ready: bool = False
    _first_frame_at: float | None = None
    _last_count: int = 0
    deadline: float | None = None

    def observe(self, count: int, *, decodable: bool, now: float) -> bool:
        """Advance on new video only; idle time and audio cannot finish warmup."""
        if (
            not decodable
            or count <= self._last_count
            or (
                self.seconds > 0
                and self.deadline is not None
                and now > self.deadline
            )
        ):
            return self.ready
        self._last_count = count
        if self._first_frame_at is None:
            self._first_frame_at = now
        self.ready = now - self._first_frame_at >= self.seconds
        return self.ready
