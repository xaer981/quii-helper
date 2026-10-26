"""Collect one supported audio track alongside the existing video capture."""

import warnings
from dataclasses import dataclass, field
from typing import Any

from quii_helper.media.audio.frames import CameraAudioFrame
from quii_helper.media.cpacket.header import cpacket_timestamp_ms


@dataclass
class AudioRecording:
    """Bounded by the caller's capture budget; never opens another connection.

    The first audio timestamp aligns the track to video. Subsequent G.711
    samples use a continuous clock, as in RTSP, not jittery device timestamps.
    Unsupported metadata disables the whole audio track, not the video.
    """

    data: bytearray = field(default_factory=bytearray, repr=False)
    codec: int | None = None
    offset_seconds: float = 0.0
    skipped_reason: str = ""
    _video_origin: tuple[int, int] | None = field(default=None, repr=False)
    _trim_samples: int = field(default=0, repr=False)

    def start_video(self, frame: dict[str, Any]) -> None:
        """Anchor audio to the first video access unit actually retained."""
        if self._video_origin is None:
            self._video_origin = frame["frame_stamp"], frame.get("frame_ms", 0)

    def feed(self, frame: dict[str, Any]) -> None:
        """Append G.711 after video starts; warn once on an unusable format."""
        if self.skipped_reason or self._video_origin is None:
            return
        try:
            audio = CameraAudioFrame.from_cpacket(frame)
            if (
                audio.codec not in {4, 5}
                or audio.sample_rate != 8000
                or audio.channels != 1
            ):
                raise ValueError("requires G.711 A-law/mu-law, 8000 Hz mono")
            if self.codec is not None and audio.codec != self.codec:
                raise ValueError("audio format changed during recording")
            if not audio.data:
                return
            if self.codec is None:
                offset_ms = cpacket_timestamp_ms(
                    audio.frame_stamp, audio.milliseconds
                ) - cpacket_timestamp_ms(*self._video_origin)
                self.offset_seconds = max(0, offset_ms) / 1000
                self._trim_samples = max(0, -offset_ms * 8)
                self.codec = audio.codec
            trim = min(self._trim_samples, len(audio.data))
            self._trim_samples -= trim
            self.data.extend(audio.data[trim:])
        except ValueError as exc:
            self.data.clear()
            self.skipped_reason = str(exc)
            warnings.warn(
                f"MP4 audio unavailable; writing video-only: {exc}",
                UserWarning,
                stacklevel=2,
            )
