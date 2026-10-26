"""Native CPacket audio metadata and encoded payloads."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CameraAudioFrame:
    """One complete encoded E3 audio frame, not necessarily PCM.

    Attributes:
        data: Audio payload without the 20-byte CPacket header.
        codec: Native codec id; unknown ids are preserved, not guessed.
        sample_rate: Sample rate in Hz reported by the camera.
        channels: Channel count reported by the camera.
        frame_stamp: Raw packed device-local calendar value, NOT Unix time.
        milliseconds: Millisecond component of the device timestamp.
    """

    data: bytes = field(repr=False)
    codec: int
    sample_rate: int
    channels: int
    frame_stamp: int
    milliseconds: int

    @property
    def codec_name(self) -> str:
        """Describe verified codec ids without decoding their payloads."""
        return {4: "g711_alaw", 5: "g711_mulaw", 9: "pcm"}.get(
            self.codec, f"codec_{self.codec}"
        )

    @classmethod
    def from_cpacket(cls, frame: dict[str, Any]) -> "CameraAudioFrame":
        """Convert a complete parsed E3 frame; reject unusable audio metadata.

        Args:
            frame: A complete frame returned by the shared CFrame assembler.

        Raises:
            ValueError: The frame is not E3 or has invalid audio metadata.
        """
        if frame["frame_tag"] != 0xE3:
            raise ValueError("expected an E3 audio frame")
        if frame["sample_rate"] <= 0 or frame["channels"] <= 0:
            raise ValueError("audio sample rate and channels must be positive")
        if not 0 <= frame["frame_ms"] < 1000:
            raise ValueError("audio milliseconds must be between 0 and 999")
        return cls(
            data=frame["bitstream"],
            codec=frame["codec"],
            sample_rate=frame["sample_rate"],
            channels=frame["channels"],
            frame_stamp=frame["frame_stamp"],
            milliseconds=frame["frame_ms"],
        )
