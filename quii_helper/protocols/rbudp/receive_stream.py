from collections.abc import Callable
from dataclasses import dataclass, field

from quii_helper.protocols.rbudp.kcp_frame_dispatch import (
    pop_complete_kcp_packet_frames,
)
from quii_helper.protocols.rbudp.lanes import RbUdpLane
from quii_helper.protocols.rbudp.models import ParsedRbUdpWrappedPacket

DebugCallback = Callable[..., None]
LaneLookupCallback = Callable[..., RbUdpLane | None]
FragmentAckCallback = Callable[..., None]
WrappedCallback = Callable[[ParsedRbUdpWrappedPacket], None]

NATIVE_RECEIVE_WINDOW_BYTES = 0x10000


@dataclass
class RbUdpReceiveStreamState:
    word4: int
    word8: int
    next_local_id: int | None = None
    buffer: bytearray = field(default_factory=bytearray)
    cache: dict[int, bytes] = field(default_factory=dict)


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
        if len(data) < 0x1C:
            return False

        word4 = int.from_bytes(data[0x04:0x08], "little")
        word8 = int.from_bytes(data[0x08:0x0C], "little")
        local_id = int.from_bytes(data[0x0C:0x10], "little")
        remote_id = int.from_bytes(data[0x10:0x14], "little")
        status_word = int.from_bytes(data[0x14:0x18], "little")
        rand16 = int.from_bytes(data[0x18:0x1A], "little")
        packet_len16 = int.from_bytes(data[0x1A:0x1C], "little")
        payload = data[0x1C:]
        key = (word4, word8)
        state = self.streams.get(key)
        if state is None:
            state = RbUdpReceiveStreamState(word4=word4, word8=word8)
            self.streams[key] = state

        if state.next_local_id is None:
            state.next_local_id = local_id
            self.stats["initialized"] += 1
            self.debug(
                "rbudp_receive_stream_init",
                word4=hex(word4),
                word8=hex(word8),
                next_local_id=state.next_local_id,
            )

        if local_id == state.next_local_id:
            self._append_payload(state, local_id=local_id, payload=payload)
            self._drain_cache(state)
            # Native DoRecvData queues data for the upper layer and immediately
            # emits SendLogicProPacket. KCP frame handling happens after that
            # through RecvData, so ACK must observe pre-dispatch lane state.
            self._ack(state, remote_id=remote_id)
            self._dispatch_frames(
                state,
                local_id=local_id,
                remote_id=remote_id,
                status_word=status_word,
                rand16=rand16,
                packet_len16=packet_len16,
            )
            return True

        if local_id < state.next_local_id:
            self.stats["replayed"] += 1
            self.debug(
                "rbudp_receive_stream_replay",
                word4=hex(word4),
                word8=hex(word8),
                got_local_id=local_id,
                want_local_id=state.next_local_id,
            )
            self._ack(state, remote_id=remote_id)
            return True

        if local_id in state.cache:
            self.stats["cache_duplicates"] += 1
        else:
            state.cache[local_id] = payload
            self.stats["cached"] += 1
            self.debug(
                "rbudp_receive_stream_cache",
                word4=hex(word4),
                word8=hex(word8),
                got_local_id=local_id,
                want_local_id=state.next_local_id,
                payload_len=len(payload),
            )
        self._ack(state, remote_id=remote_id)
        return True

    def _append_payload(
        self,
        state: RbUdpReceiveStreamState,
        *,
        local_id: int,
        payload: bytes,
        from_cache: bool = False,
    ) -> None:
        state.buffer.extend(payload)
        state.next_local_id = (local_id + len(payload)) & 0xFFFFFFFF
        self.stats["cache_drained" if from_cache else "in_order"] += 1
        self.debug(
            "rbudp_receive_stream_append",
            word4=hex(state.word4),
            word8=hex(state.word8),
            local_id=local_id,
            payload_len=len(payload),
            buffered=len(state.buffer),
            next_local_id=state.next_local_id,
            from_cache=from_cache,
        )

    def _drain_cache(self, state: RbUdpReceiveStreamState) -> None:
        while state.next_local_id in state.cache:
            cached_local_id = int(state.next_local_id)
            payload = state.cache.pop(cached_local_id)
            self._append_payload(
                state,
                local_id=cached_local_id,
                payload=payload,
                from_cache=True,
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
            status_word=self._ack_status_word(state),
            log_label="send_control_rbudp_receive_stream_ack",
        )

    def _ack_status_word(self, state: RbUdpReceiveStreamState) -> int:
        # Native SendLogicProPacket advertises
        # min(recv_window - buffered, 0xffff).
        remaining = max(0, NATIVE_RECEIVE_WINDOW_BYTES - len(state.buffer))
        advertised_window = min(remaining, 0xFFFF)
        return (advertised_window << 16) | 0x0900

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
        return {
            **self.stats,
            "active": sum(
                1
                for stream in self.streams.values()
                if stream.buffer or stream.cache
            ),
            "streams": [
                {
                    "word4": hex(stream.word4),
                    "word8": hex(stream.word8),
                    "next_local_id": stream.next_local_id,
                    "buffered": len(stream.buffer),
                    "cached": len(stream.cache),
                }
                for stream in self.streams.values()
                if stream.buffer or stream.cache
            ],
        }

    def has_pending(self) -> bool:
        return any(
            stream.buffer or stream.cache for stream in self.streams.values()
        )
