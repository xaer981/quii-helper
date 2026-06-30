from typing import Protocol

from quii_helper.protocols.rbudp.control.packets import (
    build_rb_udp_control_packet,
)
from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane


class RbUdpControlFlowOwner(Protocol):
    CONTROL_BOOTSTRAP_STATUS: int
    CONTROL_ESTABLISHED_STATUS: int
    CONTROL_FRAGMENT_ACK_STATUS: int
    _bootstrap_sent_to: tuple[str, int] | None
    _forced_transition: bool
    _lane_states: list[RbUdpLane]
    _peer_addr: tuple[str, int]
    local_id: int
    remote_id: int
    src_ids: list[int]
    word4: int
    word8: int

    def _next_lane_nonce(self, lane: RbUdpLane) -> int: ...

    def _dbg(self, message: str, **kwargs: object) -> None: ...

    def _send_udp(self, packet: bytes) -> None: ...

    def _send_wrapped_connect(self, lane: RbUdpLane) -> None: ...

    def _send_lane_control(
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
    ) -> None: ...


class RbUdpControlFlow:
    """Send RBUDP control flow packets and transition lane state."""

    def __init__(self, owner: RbUdpControlFlowOwner) -> None:
        self._owner = owner

    def send_fragment_ack(
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
        owner = self._owner
        owner._send_lane_control(
            lane,
            status_word=(
                owner.CONTROL_FRAGMENT_ACK_STATUS
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

    def send_control_bootstrap(self) -> None:
        owner = self._owner
        for lane in owner._lane_states:
            local_id = int(lane["bootstrap_local_id"])
            remote_id = int(lane["bootstrap_remote_id"])
            rand16 = owner._next_lane_nonce(lane) & 0xFFFF
            packet = build_rb_udp_control_packet(
                word4=int(lane["bootstrap_word4"]),
                word8=int(lane["bootstrap_word8"]),
                local_id=local_id,
                remote_id=remote_id,
                status_word=owner.CONTROL_BOOTSTRAP_STATUS,
                nonce=rand16,
            )
            owner._dbg(
                "send_control_bootstrap",
                peer=owner._peer_addr,
                src_id=hex(int(lane["src_id"])),
                word4=hex(int(lane["bootstrap_word4"])),
                word8=hex(int(lane["bootstrap_word8"])),
                local_id=hex(local_id),
                remote_id=hex(remote_id),
                status=hex(owner.CONTROL_BOOTSTRAP_STATUS),
                rand16=hex(rand16),
                packet_len=28,
            )
            owner._send_udp(packet)
        owner._bootstrap_sent_to = owner._peer_addr

    def send_control_established(
        self, lane: RbUdpLane, *, status_word: int | None = None
    ) -> None:
        owner = self._owner
        current_status_word = (
            owner.CONTROL_ESTABLISHED_STATUS
            if status_word is None
            else status_word
        )
        rand16 = owner._next_lane_nonce(lane) & 0xFFFF
        packet = build_rb_udp_control_packet(
            word4=int(lane["word4"]),
            word8=int(lane["word8"]),
            local_id=int(lane["local_id"]),
            remote_id=int(lane["remote_id"]),
            status_word=current_status_word,
            nonce=rand16,
        )
        owner._dbg(
            "send_control_established",
            peer=owner._peer_addr,
            src_id=hex(int(lane["src_id"])),
            word4=hex(int(lane["word4"])),
            word8=hex(int(lane["word8"])),
            local_id=int(lane["local_id"]),
            remote_id=int(lane["remote_id"]),
            status=hex(current_status_word),
            rand16=hex(rand16),
            packet_len=28,
            hex=packet.hex(),
        )
        owner._send_udp(packet)
        if current_status_word == owner.CONTROL_ESTABLISHED_STATUS:
            lane["established_sent"] = True

    def send_pending_established(self) -> None:
        owner = self._owner
        pending = [
            lane
            for lane in owner._lane_states
            if bool(lane["syn_ack_received"])
            and not bool(lane["established_sent"])
        ]
        if not pending:
            return
        if not all(
            bool(lane["syn_ack_received"]) for lane in owner._lane_states
        ):
            return
        for lane in pending:
            self.send_control_established(lane)
            owner._send_wrapped_connect(lane)

    def force_initial_established_transition(self) -> None:
        owner = self._owner
        if owner._forced_transition:
            return
        owner.word4 = 0x5500002B
        owner.word8 = 0x01000000
        if owner.local_id == 0:
            owner.local_id = 1
        if owner.remote_id == 0:
            owner.remote_id = 1
        owner._forced_transition = True
        owner._dbg(
            "force_initial_established_transition",
            peer=owner._peer_addr,
            word4=hex(owner.word4),
            word8=hex(owner.word8),
            local_id=owner.local_id,
            remote_id=owner.remote_id,
        )
        lane = owner._lane_states[0]
        lane["word4"] = owner.word4
        lane["word8"] = owner.word8
        lane["local_id"] = owner.local_id
        lane["remote_id"] = owner.remote_id
        self.send_control_established(lane)
        owner._send_wrapped_connect(lane)
