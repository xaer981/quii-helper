"""Pass-through G.711 RTP (RFC 3551): no audio decoding or resampling."""

from dataclasses import dataclass

from quii_helper.media.audio import CameraAudioFrame
from quii_helper.streaming.rtp.h264 import (
    DEFAULT_MAX_RTP_PAYLOAD_SIZE,
    RtpPacketizationResult,
    build_rtp_header,
)


@dataclass(frozen=True)
class G711Format:
    """The immutable audio profile advertised for an RTSP session."""

    codec: int

    @property
    def payload_type(self) -> int:
        return 8 if self.codec == 4 else 0

    @property
    def encoding(self) -> str:
        return "PCMA" if self.codec == 4 else "PCMU"

    @classmethod
    def from_frame(cls, frame: CameraAudioFrame) -> "G711Format":
        """Reject unsupported formats instead of publishing mislabeled audio."""
        if (
            frame.codec not in {4, 5}
            or frame.sample_rate != 8000
            or frame.channels != 1
        ):
            raise ValueError(
                "RTSP audio requires G.711 A-law or mu-law, 8000 Hz, mono"
            )
        return cls(frame.codec)


def packetize_g711(
    data: bytes,
    *,
    payload_type: int,
    sequence_number: int,
    timestamp: int,
    ssrc: int,
    max_payload_size: int = DEFAULT_MAX_RTP_PAYLOAD_SIZE,
) -> RtpPacketizationResult:
    """Split sample-aligned payloads; each G.711 octet advances the clock by one."""
    if payload_type not in {0, 8} or max_payload_size <= 0:
        raise ValueError("invalid G.711 RTP profile or payload size")
    packets: list[bytes] = []
    for offset in range(0, len(data), max_payload_size):
        packets.append(
            build_rtp_header(
                payload_type=payload_type,
                sequence_number=sequence_number + len(packets),
                timestamp=timestamp + offset,
                ssrc=ssrc,
                marker=False,
            )
            + data[offset : offset + max_payload_size]
        )
    return RtpPacketizationResult(packets, sequence_number + len(packets))
