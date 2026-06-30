from typing import Protocol

from quii_helper.protocols.rbudp.control.dispatcher import EventLike
from quii_helper.protocols.rbudp.core.models import ParsedRbUdpControlPacket
from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane


class RbUdpControlProgressOwner(Protocol):
    CONTROL_FLOW_STATUS: int
    CONTROL_PLAY_ESTABLISHED_ACK_STATUS: int
    CONTROL_PLAY_SYNC_LOCAL_BIAS: int
    CONTROL_PLAY_SYNC_STEP: int
    CONTROL_PROGRESS_STATUS: int
    _quii_play_sent: EventLike

    def _dbg(self, message: str, **kwargs: object) -> None: ...

    def _send_lane_control(
        self,
        lane: RbUdpLane,
        *,
        status_word: int,
        local_id: int | None = None,
        remote_id: int | None = None,
        log_label: str | None = "send_control",
    ) -> None: ...

    def _send_wrapped_connect(self, lane: RbUdpLane) -> None: ...

    def _start_play_sync(
        self,
        lane: RbUdpLane,
        *,
        local_id: int,
        seed_remote_id: int,
    ) -> None: ...


class RbUdpControlProgress:
    """Handle flow, established, and progress control transitions."""

    def __init__(self, owner: RbUdpControlProgressOwner) -> None:
        self._owner = owner

    def handle_flow_control(
        self,
        lane: RbUdpLane,
        control: ParsedRbUdpControlPacket,
        *,
        peer_logic_id: int,
    ) -> None:
        owner = self._owner
        if (
            control.local_id == 1
            and peer_logic_id
            and not bool(lane["flow_sent"])
        ):
            owner._send_lane_control(
                lane,
                status_word=owner.CONTROL_FLOW_STATUS,
                local_id=peer_logic_id,
                remote_id=1,
                log_label="send_control_flow",
            )
            lane["flow_sent"] = True

    def handle_established_control(
        self, lane: RbUdpLane, control: ParsedRbUdpControlPacket
    ) -> None:
        owner = self._owner
        if (
            owner._quii_play_sent.is_set()
            and control.local_id > 1
            and control.remote_id > 1
        ):
            owner._send_lane_control(
                lane,
                status_word=owner.CONTROL_PLAY_ESTABLISHED_ACK_STATUS,
                local_id=control.remote_id,
                remote_id=control.local_id,
                log_label="send_control_play_established_ack",
            )
            self.start_play_sync_from_control(
                lane, control, reason="established"
            )

    def start_play_sync_from_control(
        self,
        lane: RbUdpLane,
        control: ParsedRbUdpControlPacket,
        *,
        reason: str,
    ) -> None:
        owner = self._owner
        if (
            not owner._quii_play_sent.is_set()
            or bool(lane["play_sync_active"])
            or control.local_id <= 1
        ):
            return
        local_id = (
            control.local_id + owner.CONTROL_PLAY_SYNC_LOCAL_BIAS
        ) & 0xFFFFFFFF
        seed_remote_id = (
            control.local_id + owner.CONTROL_PLAY_SYNC_STEP
        ) & 0xFFFFFFFF
        owner._dbg(
            "play_sync_start",
            reason=reason,
            src_id=hex(int(lane["src_id"])),
            control_local_id=control.local_id,
            control_remote_id=control.remote_id,
            local_id=local_id,
            seed_remote_id=seed_remote_id,
        )
        owner._start_play_sync(
            lane, local_id=local_id, seed_remote_id=seed_remote_id
        )

    def handle_progress_control(
        self,
        lane: RbUdpLane,
        control: ParsedRbUdpControlPacket,
        *,
        peer_logic_id: int,
    ) -> None:
        owner = self._owner
        if (
            peer_logic_id
            and control.remote_id == peer_logic_id
            and not bool(lane["progress_sent"])
            and not bool(lane.get("setup_probe_sent", False))
        ):
            owner._dbg(
                "progress_reconnect_hint",
                src_id=hex(int(lane["src_id"])),
                control_local_id=control.local_id,
                control_remote_id=control.remote_id,
                peer_logic_id=peer_logic_id,
            )
            owner._send_wrapped_connect(lane)
        if (
            control.local_id == peer_logic_id
            and peer_logic_id
            and control.remote_id == peer_logic_id
            and not bool(lane["progress_sent"])
        ):
            owner._send_lane_control(
                lane,
                status_word=owner.CONTROL_PROGRESS_STATUS,
                local_id=peer_logic_id,
                remote_id=peer_logic_id,
                log_label="send_control_progress",
            )
            lane["progress_sent"] = True
            owner._send_wrapped_connect(lane)
