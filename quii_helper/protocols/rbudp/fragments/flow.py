from collections.abc import Callable

from quii_helper.protocols.rbudp.core.models import ParsedRbUdpWrappedPacket
from quii_helper.protocols.rbudp.fragments.ack import (
    RbUdpFragmentAckCoordinator,
)
from quii_helper.protocols.rbudp.fragments.packet import RbUdpFragmentPacket
from quii_helper.protocols.rbudp.fragments.partial import (
    RbUdpFragmentPartialEmitter,
)
from quii_helper.protocols.rbudp.fragments.remainder import (
    RbUdpFragmentRemainderCoordinator,
)
from quii_helper.protocols.rbudp.fragments.state import (
    classify_fragment_append,
    initial_fragment_stats,
    is_duplicate_fragment_restart,
    wrapped_fragment_summary,
)
from quii_helper.protocols.rbudp.fragments.stream import (
    RbUdpWrappedFragmentStream,
    stream_key_for_packet_words,
)
from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane

DebugCallback = Callable[..., None]
LaneLookupCallback = Callable[..., RbUdpLane | None]
FragmentAckCallback = Callable[..., None]
WrappedCallback = Callable[[ParsedRbUdpWrappedPacket], None]
PayloadCallback = Callable[..., None]


class RbUdpWrappedFragmentAssembler:
    def __init__(
        self,
        *,
        debug: DebugCallback,
        lane_for_packet_words: LaneLookupCallback,
        send_fragment_ack: FragmentAckCallback,
        handle_wrapped: WrappedCallback,
        queue_payload: PayloadCallback,
    ) -> None:
        self.debug = debug
        self.lane_for_packet_words = lane_for_packet_words
        self.send_fragment_ack = send_fragment_ack
        self.handle_wrapped = handle_wrapped
        self.queue_payload = queue_payload
        self.streams: dict[tuple[int, int], RbUdpWrappedFragmentStream] = {}
        self.acks = RbUdpFragmentAckCoordinator(
            debug=debug,
            lane_for_packet_words=lane_for_packet_words,
            send_fragment_ack=send_fragment_ack,
        )
        self.partial_emitter = RbUdpFragmentPartialEmitter(
            debug=debug,
            queue_payload=queue_payload,
        )
        self.remainders = RbUdpFragmentRemainderCoordinator(
            debug=debug,
            streams=self.streams,
        )
        self.stats: dict[str, int] = initial_fragment_stats()

    @staticmethod
    def stream_key(*, word4: int, word8: int) -> tuple[int, int]:
        return stream_key_for_packet_words(word4=word4, word8=word8)

    def start(self, data: bytes) -> bool:
        packet = RbUdpFragmentPacket.parse(data) if len(data) >= 0x24 else None
        if packet is None:
            return False
        if packet.inner_total_length < 0x10:
            return False

        stream = RbUdpWrappedFragmentStream.from_start_packet(
            data,
            inner_total_length=packet.inner_total_length,
        )
        existing = self.streams.get(stream.key)
        if is_duplicate_fragment_restart(
            existing,
            inner_total_length=packet.inner_total_length,
            incoming_payload_len=len(packet.payload),
        ):
            self.debug(
                "ignore_wrapped_fragment_stream_restart",
                word4=hex(stream.word4),
                word8=hex(stream.word8),
                local_id=stream.start_local_id,
                remote_id=stream.remote_id,
                existing_have=existing.have,
                incoming_have=len(packet.payload),
            )
            self.stats["restart_acked"] += 1
            self.acks.ack_stream(
                existing,
                reason="restart",
                force=True,
                log_label="send_control_fragment_restart_ack",
            )
            return True

        self.streams[stream.key] = stream
        self.stats["started"] += 1
        self.debug(
            "start_wrapped_fragment_stream",
            word4=hex(stream.word4),
            word8=hex(stream.word8),
            local_id=stream.start_local_id,
            remote_id=stream.remote_id,
            inner_total_length=stream.inner_total_length,
            have=stream.have,
            next_local_id=stream.next_local_id,
        )
        self.acks.ack_stream(stream, reason="start")
        return True

    def append(self, data: bytes) -> bool:
        try:
            packet = RbUdpFragmentPacket.parse(data)
        except ValueError:
            return False
        stream = self.streams.get(packet.stream_key)
        if stream is None:
            return False

        append_class = classify_fragment_append(
            local_id=packet.local_id,
            next_local_id=stream.next_local_id,
        )
        if append_class != "in_order":
            if append_class == "replay":
                self.stats["replayed"] += 1
                self.debug(
                    "ignore_wrapped_fragment_stream_replay",
                    word4=hex(packet.word4),
                    word8=hex(packet.word8),
                    got_local_id=packet.local_id,
                    want_local_id=stream.next_local_id,
                    start_local_id=stream.start_local_id,
                )
                self.stats["replay_acked"] += 1
                self.acks.ack_stream(
                    stream,
                    reason="replay",
                    force=True,
                    log_label="send_control_fragment_replay_ack",
                )
                return True
            self.stats["gaps"] += 1
            return self.remainders.resync_gap(
                stream,
                data=data,
                got_local_id=packet.local_id,
                want_local_id=stream.next_local_id,
            )

        stream.append_payload(local_id=packet.local_id, payload=packet.payload)
        self.stats["appended"] += 1
        self.debug(
            "append_wrapped_fragment_stream",
            word4=hex(packet.word4),
            word8=hex(packet.word8),
            local_id=packet.local_id,
            remote_id=packet.remote_id,
            have=stream.have,
            need=stream.inner_total_length,
            next_local_id=stream.next_local_id,
        )
        self.acks.ack_stream(stream, reason="append")
        if stream.have < stream.inner_total_length:
            return True

        inner_packet, remainder = stream.split_complete_payload()
        del self.streams[stream.key]
        self.stats["completed"] += 1
        self.debug(
            "complete_wrapped_fragment_stream",
            word4=hex(packet.word4),
            word8=hex(packet.word8),
            inner_total_length=stream.inner_total_length,
            remainder_len=len(remainder),
        )
        self.handle_wrapped(
            stream.to_wrapped_packet(
                local_id=packet.local_id,
                remote_id=packet.remote_id,
                inner_packet=inner_packet,
            )
        )
        self.remainders.carry_remainder(
            stream,
            remainder=remainder,
            previous_total_length=stream.inner_total_length,
        )
        return True

    def emit_active(self) -> None:
        self.stats["partials"] += len(self.streams)
        self.partial_emitter.emit_active(self.streams)

    def summary(self) -> dict[str, object]:
        return wrapped_fragment_summary(self.stats, self.streams)
