from quii_helper.protocols.quii.live_packets import build_live_setup_packet
from quii_helper.protocols.rbudp.kcp.link_packets import (
    build_kcp_connect_packet,
    build_rb_data_ack_packet,
    build_rb_data_packet,
)
from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane
from quii_helper.protocols.rbudp.wrapped.packets import (
    build_rb_udp_wrapped_packet,
)


class RbUdpWrappedSenderMixin:
    _lane_states: list[RbUdpLane]
    _peer_addr: tuple[str, int]
    dest_id: int | None
    dest_ids: dict[int, int]

    def _send_wrapped(
        self,
        inner_packet: bytes,
        *,
        tag8: bytes,
        lane: RbUdpLane | None = None,
        word4: int | None = None,
        word8: int | None = None,
    ) -> None:
        lane = self._active_lane() if lane is None else lane
        local_id = int(lane["local_id"])
        rand16 = self._next_lane_nonce(lane) & 0xFFFF
        packet = build_rb_udp_wrapped_packet(
            inner_packet,
            word4=int(lane["word4"] if word4 is None else word4),
            word8=int(lane["word8"] if word8 is None else word8),
            local_id=local_id,
            remote_id=int(lane["remote_id"]),
            status_word=self.WRAPPED_STATUS,
            nonce=rand16,
            tag8=tag8,
        )
        self._send_udp(packet)
        # Native RBUDP advances conn+0x9c
        # by the payload length after data sends.
        lane["local_id"] = (local_id + len(inner_packet)) & 0xFFFFFFFF

    def _connected_lane_destinations(self) -> list[tuple[RbUdpLane, int]]:
        pairs: list[tuple[RbUdpLane, int]] = []
        for lane in self._lane_states:
            src_id = int(lane["src_id"])
            dest_id = self.dest_ids.get(src_id)
            if dest_id is not None:
                pairs.append((lane, dest_id))
        return pairs

    def _send_wrapped_connect(self, lane: RbUdpLane) -> None:
        if bool(lane["connect_sent"]):
            return
        src_id = int(lane["src_id"])
        inner = build_kcp_connect_packet(
            src_id=src_id,
            channel=int(self.config.logical_channel),
            conn_type=int(self.config.logical_conn_type),
        )
        self._dbg(
            "send_wrapped_connect",
            peer=self._peer_addr,
            src_id=hex(src_id),
            channel=self.config.logical_channel,
            conn_type=self.config.logical_conn_type,
            local_id=int(lane["local_id"]),
            remote_id=int(lane["remote_id"]),
            word4=hex(int(lane["word4"])),
            word8=hex(int(lane["word8"])),
        )
        self._send_wrapped(inner, tag8=self.CONNECT_TAG, lane=lane)
        lane["connect_sent"] = True

    def _send_wrapped_setup_probe(
        self, lane: RbUdpLane, *, connect_id: int, dest_id: int
    ) -> None:
        if bool(lane["setup_probe_sent"]):
            return
        inner = build_rb_data_packet(
            payload=build_live_setup_packet(),
            src_id=connect_id,
            dest_id=dest_id,
            seq=0,
        )
        self._dbg(
            "send_wrapped_setup_probe",
            peer=self._peer_addr,
            src_id=hex(connect_id),
            dest_id=hex(dest_id),
            word4=hex(int(lane["word4"])),
            word8=hex(int(lane["word8"])),
            local_id=int(lane["local_id"]),
            remote_id=int(lane["remote_id"]),
            inner_hex=inner.hex(),
        )
        self._send_wrapped(inner, tag8=self.DATA_TAG, lane=lane)
        lane["setup_probe_sent"] = True

    def _send_wrapped_data_ack(
        self,
        lane: RbUdpLane,
        *,
        seq: int,
        src_id: int,
        dest_id: int,
        payload_length: int,
        word4: int | None = None,
        word8: int | None = None,
    ) -> None:
        inner = build_rb_data_ack_packet(
            payload_length=payload_length,
            seq=seq,
            src_id=src_id,
            dest_id=dest_id,
        )
        ack_word4 = int(lane["word4"] if word4 is None else word4)
        ack_word8 = int(lane["word8"] if word8 is None else word8)
        self._dbg(
            "send_quii_data_ack",
            peer=self._peer_addr,
            src_id=hex(src_id),
            dest_id=hex(dest_id),
            seq=hex(seq),
            payload_length=payload_length,
            word4=hex(ack_word4),
            word8=hex(ack_word8),
            lane_word4=hex(int(lane["word4"])),
            lane_word8=hex(int(lane["word8"])),
            local_id=int(lane["local_id"]),
            remote_id=int(lane["remote_id"]),
            inner_hex=inner.hex(),
        )
        self._send_wrapped(
            inner,
            tag8=self.DATA_TAG,
            lane=lane,
            word4=ack_word4,
            word8=ack_word8,
        )
