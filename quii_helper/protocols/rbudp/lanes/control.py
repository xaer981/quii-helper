from typing import Any, Protocol

from quii_helper.protocols.rbudp.control.packets import (
    build_rb_udp_control_packet,
)
from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane

NATIVE_RECEIVE_WINDOW_BYTES = 0x10000


class RbUdpLaneControlOwner(Protocol):
    _peer_addr: tuple[str, int]
    _receive_streams: Any

    def _next_lane_nonce(self, lane: RbUdpLane) -> int: ...

    def _dbg(self, message: str, **kwargs: object) -> None: ...

    def _send_udp(self, packet: bytes) -> None: ...


class RbUdpLaneControl:
    """Build and send RBUDP lane control packets."""

    def __init__(self, owner: RbUdpLaneControlOwner) -> None:
        self._owner = owner

    def send_lane_control(
        self,
        lane: RbUdpLane,
        *,
        status_word: int,
        local_id: int | None = None,
        remote_id: int | None = None,
        word4: int | None = None,
        word8: int | None = None,
        log_label: str | None = "send_control",
        update_lane: bool = True,
        advertise_window: bool = False,
    ) -> None:
        owner = self._owner
        current_word4 = int(lane["word4"] if word4 is None else word4)
        current_word8 = int(lane["word8"] if word8 is None else word8)
        current_local_id = int(
            lane["local_id"] if local_id is None else local_id
        )
        current_remote_id = int(
            lane["remote_id"] if remote_id is None else remote_id
        )
        buffered = self.lane_receive_buffered_bytes(
            lane,
            word4=current_word4,
            word8=current_word8,
        )
        if advertise_window:
            current_status_word = self.native_control_status_word(
                lane,
                status_word,
                buffered=buffered,
            )
        else:
            current_status_word = status_word & 0xFFFFFFFF
        if update_lane:
            lane["word4"] = current_word4
            lane["word8"] = current_word8
            lane["local_id"] = current_local_id
            lane["remote_id"] = current_remote_id
        rand16 = owner._next_lane_nonce(lane) & 0xFFFF
        packet = build_rb_udp_control_packet(
            word4=current_word4,
            word8=current_word8,
            local_id=current_local_id,
            remote_id=current_remote_id,
            status_word=current_status_word,
            nonce=rand16,
        )
        if log_label:
            owner._dbg(
                log_label,
                peer=owner._peer_addr,
                src_id=hex(int(lane["src_id"])),
                word4=hex(current_word4),
                word8=hex(current_word8),
                local_id=current_local_id,
                remote_id=current_remote_id,
                status_input=hex(status_word),
                status_low=hex(status_word & 0xFFFF),
                window16=hex((current_status_word >> 16) & 0xFFFF),
                buffered=buffered,
                status=hex(current_status_word),
                rand16=hex(rand16),
                packet_len=28,
                hex=packet.hex(),
            )
        owner._send_udp(packet)

    def native_control_status_word(
        self,
        lane: RbUdpLane,
        status_word: int,
        *,
        buffered: int | None = None,
    ) -> int:
        # Native SendLogicProPacket preserves low status flags and advertises
        # min(recv_window - buffered, 0xffff) in the high 16 bits. This is only
        # safe for ACK paths where our buffered byte count models native state.
        if buffered is None:
            buffered = self.lane_receive_buffered_bytes(lane)
        remaining = max(0, NATIVE_RECEIVE_WINDOW_BYTES - buffered)
        advertised_window = min(remaining, 0xFFFF)
        return (advertised_window << 16) | (status_word & 0xFFFF)

    def lane_receive_buffered_bytes(
        self,
        lane: RbUdpLane,
        *,
        word4: int | None = None,
        word8: int | None = None,
    ) -> int:
        receive_streams = getattr(self._owner, "_receive_streams", None)
        streams = getattr(receive_streams, "streams", None)
        if not streams:
            return 0

        candidate_keys = {
            (int(lane["peer_word4"]), int(lane["peer_word8"])),
            (int(lane["word8"]), int(lane["word4"])),
            (int(lane["bootstrap_word8"]), int(lane["word4"])),
        }
        if word4 is not None and word8 is not None:
            # ACK/control packets use
            # the reverse word order of inbound RBUDP data.
            candidate_keys.add((int(word8), int(word4)))
        return sum(
            len(stream.buffer)
            for key, stream in streams.items()
            if key in candidate_keys
        )
