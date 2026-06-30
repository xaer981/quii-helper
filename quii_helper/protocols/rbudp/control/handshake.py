from typing import Protocol

from quii_helper.protocols.rbudp.core.models import ParsedRbUdpControlPacket
from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane


class RbUdpControlHandshakeOwner(Protocol):
    CONTROL_SYN_ACK_STATUS: int

    def _lane_for_syn_ack(
        self, control: ParsedRbUdpControlPacket
    ) -> RbUdpLane | None: ...

    def _dbg(self, message: str, **kwargs: object) -> None: ...

    def _send_pending_established(self) -> None: ...


class RbUdpControlHandshake:
    """Handle RBUDP SYN/ACK control transitions."""

    def __init__(self, owner: RbUdpControlHandshakeOwner) -> None:
        self._owner = owner

    def handle_syn_ack_control(
        self, control: ParsedRbUdpControlPacket
    ) -> bool:
        owner = self._owner
        if (
            control.status_word != owner.CONTROL_SYN_ACK_STATUS
            or not control.remote_id
        ):
            return False
        lane = owner._lane_for_syn_ack(control)
        if lane is None:
            return True
        lane["peer_word4"] = control.word4
        lane["peer_word8"] = control.word8
        lane["word4"] = control.word8
        lane["word8"] = int(lane["bootstrap_word8"])
        lane["local_id"] = control.remote_id
        lane["remote_id"] = control.remote_id
        lane["progress_sent"] = False
        lane["flow_sent"] = False
        lane["established_sent"] = False
        lane["post_play_established_sent"] = False
        lane["play_probe_stage"] = 0
        lane["play_sync_active"] = False
        lane["play_sync_local_id"] = 0
        lane["play_sync_counter"] = 0
        lane["play_sync_remaining"] = 0
        lane["play_sync_sent_count"] = 0
        lane["play_sync_remote_bias"] = 0
        lane["play_word_refresh_sent"] = False
        lane["play_transport_refresh_sent"] = False
        lane["syn_ack_received"] = True
        lane["peer_logic_id"] = 0
        owner._dbg(
            "syn_ack_transition",
            src_id=hex(int(lane["src_id"])),
            peer_word4=hex(int(lane["peer_word4"])),
            peer_word8=hex(int(lane["peer_word8"])),
            word4=hex(int(lane["word4"])),
            word8=hex(int(lane["word8"])),
            local_id=int(lane["local_id"]),
            remote_id=int(lane["remote_id"]),
        )
        owner._send_pending_established()
        return True
