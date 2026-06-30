from collections.abc import Callable
from dataclasses import dataclass, field

from quii_helper.models.packets import DecodedQuiiMessage, QuiiPacketSummary
from quii_helper.preview.processing.packets.summary import (
    attach_media_frame_summary,
)

MediaMessageSink = Callable[[DecodedQuiiMessage], None]


@dataclass
class CaptureStats:
    """Production packet state collected while decoding preview traffic."""

    decoded_messages: list[DecodedQuiiMessage] = field(default_factory=list)
    media_messages: list[DecodedQuiiMessage] = field(default_factory=list)
    media_message_sink: MediaMessageSink | None = None
    store_media_messages: bool = True

    def record_decoded(self, decoded: DecodedQuiiMessage) -> None:
        if decoded["plausible"]:
            self.decoded_messages.append(decoded)

    def record_live_media(
        self,
        *,
        summary: QuiiPacketSummary,
        decoded: DecodedQuiiMessage,
        phase: str,
    ) -> None:
        if phase != "live" or not attach_media_frame_summary(summary, decoded):
            return

        if self.store_media_messages:
            self.media_messages.append(decoded)
        if self.media_message_sink is not None:
            self.media_message_sink(decoded)

    def record_processed_packet(
        self,
        *,
        summary: QuiiPacketSummary,
        decoded: DecodedQuiiMessage,
        phase: str,
    ) -> None:
        self.record_decoded(decoded)
        self.record_live_media(summary=summary, decoded=decoded, phase=phase)
