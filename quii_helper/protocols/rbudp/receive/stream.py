from collections.abc import Callable

from quii_helper.protocols.rbudp.core.models import ParsedRbUdpWrappedPacket
from quii_helper.protocols.rbudp.kcp.frame_dispatch import (
    pop_complete_kcp_packet_frames,
)
from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane
from quii_helper.protocols.rbudp.receive.stream_packet import (
    parse_receive_stream_packet,
)
from quii_helper.protocols.rbudp.receive.stream_state import (
    RbUdpReceiveStreamAppendEvent,
    RbUdpReceiveStreamState,
    append_receive_stream_payload,
    drain_receive_stream_cache,
    has_pending_receive_streams,
    receive_ack_status_word,
    receive_stream_summary,
)

DebugCallback = Callable[..., None]
LaneLookupCallback = Callable[..., RbUdpLane | None]
FragmentAckCallback = Callable[..., None]
WrappedCallback = Callable[[ParsedRbUdpWrappedPacket], None]


class RbUdpReceiveStreamAssembler:
    """
    Native-aligned RBUDP receive path.

    libqv-p2p-v2.so appends data packets (offset 0x1c onward) into an ordered
    receive buffer, ACKs the cumulative next sequence and lets KcpLinkClient
    pop complete 0xffffffff-prefixed frames from that byte stream.
    """

    def __init__(
        self,
        *,
        debug: DebugCallback,
        lane_for_packet_words: LaneLookupCallback,
        send_fragment_ack: FragmentAckCallback,
        handle_wrapped: WrappedCallback,
    ) -> None:
        self.debug = debug
        self.lane_for_packet_words = lane_for_packet_words
        self.send_fragment_ack = send_fragment_ack
        self.handle_wrapped = handle_wrapped
        self.streams: dict[tuple[int, int], RbUdpReceiveStreamState] = {}
        self.stats: dict[str, int] = {
            "initialized": 0,
            "in_order": 0,
            "cached": 0,
            "cache_duplicates": 0,
            "cache_drained": 0,
            "replayed": 0,
            "acked": 0,
            "frames": 0,
            "invalid": 0,
        }

    def feed(self, data: bytes) -> bool:
        packet = parse_receive_stream_packet(data)
        if packet is None:
            return False

        state = self.streams.get(packet.stream_key)
        if state is None:
            state = RbUdpReceiveStreamState(
                word4=packet.word4,
                word8=packet.word8,
            )
            self.streams[packet.stream_key] = state

        if state.next_local_id is None:
            state.next_local_id = packet.local_id
            self.stats["initialized"] += 1
            self.debug(
                "rbudp_receive_stream_init",
                word4=hex(packet.word4),
                word8=hex(packet.word8),
                next_local_id=state.next_local_id,
            )

        if packet.local_id == state.next_local_id:
            self._record_append_event(
                state,
                append_receive_stream_payload(
                    state,
                    local_id=packet.local_id,
                    payload=packet.payload,
                ),
            )
            for event in drain_receive_stream_cache(state):
                self._record_append_event(state, event)
            # Native DoRecvData queues data for the upper layer and immediately
            # emits SendLogicProPacket. KCP frame handling happens after that
            # through RecvData, so ACK must observe pre-dispatch lane state.
            self._ack(state, remote_id=packet.remote_id)
            self._dispatch_frames(
                state,
                local_id=packet.local_id,
                remote_id=packet.remote_id,
                status_word=packet.status_word,
                rand16=packet.rand16,
                packet_len16=packet.packet_len16,
            )
            return True

        if packet.local_id < state.next_local_id:
            self.stats["replayed"] += 1
            self.debug(
                "rbudp_receive_stream_replay",
                word4=hex(packet.word4),
                word8=hex(packet.word8),
                got_local_id=packet.local_id,
                want_local_id=state.next_local_id,
            )
            self._ack(state, remote_id=packet.remote_id)
            return True

        if packet.local_id in state.cache:
            self.stats["cache_duplicates"] += 1
        else:
            state.cache[packet.local_id] = packet.payload
            self.stats["cached"] += 1
            self.debug(
                "rbudp_receive_stream_cache",
                word4=hex(packet.word4),
                word8=hex(packet.word8),
                got_local_id=packet.local_id,
                want_local_id=state.next_local_id,
                payload_len=len(packet.payload),
            )
        self._ack(state, remote_id=packet.remote_id)
        return True

    def _record_append_event(
        self,
        state: RbUdpReceiveStreamState,
        event: RbUdpReceiveStreamAppendEvent,
    ) -> None:
        self.stats["cache_drained" if event.from_cache else "in_order"] += 1
        self.debug(
            "rbudp_receive_stream_append",
            word4=hex(state.word4),
            word8=hex(state.word8),
            local_id=event.local_id,
            payload_len=event.payload_len,
            buffered=event.buffered_len,
            next_local_id=event.next_local_id,
            from_cache=event.from_cache,
        )

    def _ack(self, state: RbUdpReceiveStreamState, *, remote_id: int) -> None:
        if state.next_local_id is None:
            return
        lane = self.lane_for_packet_words(word4=state.word4, word8=state.word8)
        if lane is None:
            self.debug(
                "skip_rbudp_receive_stream_ack_no_lane",
                word4=hex(state.word4),
                word8=hex(state.word8),
                next_local_id=state.next_local_id,
            )
            return
        lane["remote_id"] = state.next_local_id
        self.stats["acked"] += 1
        self.send_fragment_ack(
            lane,
            int(lane["local_id"]),
            state.next_local_id,
            word4=state.word8,
            word8=state.word4,
            # Native SendLogicProPacket advertises
            # min(recv_window - buffered, 0xffff).
            status_word=receive_ack_status_word(len(state.buffer)),
            log_label="send_control_rbudp_receive_stream_ack",
        )

    def _dispatch_frames(
        self,
        state: RbUdpReceiveStreamState,
        *,
        local_id: int,
        remote_id: int,
        status_word: int,
        rand16: int,
        packet_len16: int,
    ) -> None:
        try:
            frames = pop_complete_kcp_packet_frames(state.buffer)
        except Exception as exc:
            self.stats["invalid"] += 1
            self.debug(
                "rbudp_receive_stream_invalid",
                word4=hex(state.word4),
                word8=hex(state.word8),
                error=repr(exc),
                buffered=len(state.buffer),
                prefix=bytes(state.buffer[:32]).hex(),
            )
            state.buffer.clear()
            return

        for frame in frames:
            self.stats["frames"] += 1
            self.debug(
                "rbudp_receive_stream_frame",
                word4=hex(state.word4),
                word8=hex(state.word8),
                frame_len=len(frame.raw),
                command=hex(frame.command),
                remaining=len(state.buffer),
            )
            self.handle_wrapped(
                ParsedRbUdpWrappedPacket(
                    marker=0xFFABEFC1,
                    word4=state.word4,
                    word8=state.word8,
                    local_id=local_id,
                    remote_id=remote_id,
                    status_word=status_word,
                    rand16=rand16,
                    packet_len16=packet_len16,
                    inner_total_length=len(frame.raw),
                    tag8=b"",
                    inner_packet=frame.raw,
                )
            )

    def summary(self) -> dict[str, object]:
        return receive_stream_summary(self.stats, self.streams)

    def has_pending(self) -> bool:
        return has_pending_receive_streams(self.streams)
