from quii_helper.protocols.rbudp.control_packets import (
    build_rb_udp_control_packet,
)
from quii_helper.protocols.rbudp.lane_control import RbUdpLaneControlMixin
from quii_helper.protocols.rbudp.lanes import RbUdpLane


class RbUdpControlFlowMixin(RbUdpLaneControlMixin):
    _lane_states: list[RbUdpLane]
    _peer_addr: tuple[str, int]
    _bootstrap_sent_to: tuple[str, int] | None
    _forced_transition: bool
    _quii_play_sent: object
    _stop: object
    local_id: int
    remote_id: int
    word4: int
    word8: int
    src_ids: list[int]

    def _send_fragment_ack(
        self,
        lane: RbUdpLane,
        local_id: int,
        remote_id: int,
        *,
        word4: int | None = None,
        word8: int | None = None,
        status_word: int | None = None,
        log_label: str = "send_control_fragment_ack",
    ) -> None:
        self._send_lane_control(
            lane,
            status_word=(
                self.CONTROL_FRAGMENT_ACK_STATUS
                if status_word is None
                else status_word
            ),
            local_id=local_id,
            remote_id=remote_id,
            word4=word4,
            word8=word8,
            log_label=log_label,
            update_lane=False,
            advertise_window=True,
        )

    def _send_control_bootstrap(self) -> None:
        for lane in self._lane_states:
            local_id = int(lane["bootstrap_local_id"])
            remote_id = int(lane["bootstrap_remote_id"])
            rand16 = self._next_lane_nonce(lane) & 0xFFFF
            packet = build_rb_udp_control_packet(
                word4=int(lane["bootstrap_word4"]),
                word8=int(lane["bootstrap_word8"]),
                local_id=local_id,
                remote_id=remote_id,
                status_word=self.CONTROL_BOOTSTRAP_STATUS,
                nonce=rand16,
            )
            self._dbg(
                "send_control_bootstrap",
                peer=self._peer_addr,
                src_id=hex(int(lane["src_id"])),
                word4=hex(int(lane["bootstrap_word4"])),
                word8=hex(int(lane["bootstrap_word8"])),
                local_id=hex(local_id),
                remote_id=hex(remote_id),
                status=hex(self.CONTROL_BOOTSTRAP_STATUS),
                rand16=hex(rand16),
                packet_len=28,
            )
            self._send_udp(packet)
        self._bootstrap_sent_to = self._peer_addr

    def _send_control_established(
        self, lane: RbUdpLane, *, status_word: int | None = None
    ) -> None:
        status_word = (
            self.CONTROL_ESTABLISHED_STATUS
            if status_word is None
            else status_word
        )
        rand16 = self._next_lane_nonce(lane) & 0xFFFF
        packet = build_rb_udp_control_packet(
            word4=int(lane["word4"]),
            word8=int(lane["word8"]),
            local_id=int(lane["local_id"]),
            remote_id=int(lane["remote_id"]),
            status_word=status_word,
            nonce=rand16,
        )
        self._dbg(
            "send_control_established",
            peer=self._peer_addr,
            src_id=hex(int(lane["src_id"])),
            word4=hex(int(lane["word4"])),
            word8=hex(int(lane["word8"])),
            local_id=int(lane["local_id"]),
            remote_id=int(lane["remote_id"]),
            status=hex(status_word),
            rand16=hex(rand16),
            packet_len=28,
            hex=packet.hex(),
        )
        self._send_udp(packet)
        if status_word == self.CONTROL_ESTABLISHED_STATUS:
            lane["established_sent"] = True

    def _send_pending_established(self) -> None:
        pending = [
            lane
            for lane in self._lane_states
            if bool(lane["syn_ack_received"])
            and not bool(lane["established_sent"])
        ]
        if not pending:
            return
        if not all(
            bool(lane["syn_ack_received"]) for lane in self._lane_states
        ):
            return
        for lane in pending:
            self._send_control_established(lane)
            self._send_wrapped_connect(lane)

    def _force_initial_established_transition(self) -> None:
        if self._forced_transition:
            return
        self.word4 = 0x5500002B
        self.word8 = 0x01000000
        if self.local_id == 0:
            self.local_id = 1
        if self.remote_id == 0:
            self.remote_id = 1
        self._forced_transition = True
        self._dbg(
            "force_initial_established_transition",
            peer=self._peer_addr,
            word4=hex(self.word4),
            word8=hex(self.word8),
            local_id=self.local_id,
            remote_id=self.remote_id,
        )
        lane = self._lane_states[0]
        lane["word4"] = self.word4
        lane["word8"] = self.word8
        lane["local_id"] = self.local_id
        lane["remote_id"] = self.remote_id
        self._send_control_established(lane)
        self._send_wrapped_connect(lane)
