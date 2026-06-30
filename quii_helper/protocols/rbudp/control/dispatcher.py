from dataclasses import dataclass
from typing import Protocol

from quii_helper.protocols.rbudp.core.models import ParsedRbUdpControlPacket
from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane


class EventLike(Protocol):
    def is_set(self) -> bool: ...

    def set(self) -> None: ...


class RbUdpControlDispatcherOwner(Protocol):
    CONTROL_ESTABLISHED_STATUS: int
    CONTROL_FRAGMENT_FLOW_STATUS: int
    CONTROL_HEARTBEAT_REQUEST_STATUS: int
    CONTROL_HEARTBEAT_RESPONSE_STATUS: int
    CONTROL_PLAY_LATE_STATUS: int
    CONTROL_PLAY_SYNC_STATUS: int
    CONTROL_POST_CONNECT_ACK_STATUS: int
    CONTROL_POST_CONNECT_STATUS: int
    CONTROL_POST_PLAY_ACK_STATUS: int
    CONTROL_POST_PLAY_STATUS: int
    CONTROL_POST_SETUP_ACK_STATUS: int
    CONTROL_POST_SETUP_STATUS: int
    CONTROL_PROGRESS_STATUS: int
    CONTROL_STREAM_READY_ACK_STATUS: int
    CONTROL_STREAM_READY_STATUS: int

    _last_control: ParsedRbUdpControlPacket | None
    _peer_addr: tuple[str, int]
    _quii_play_sent: EventLike
    _quii_ready: EventLike

    def _dbg(self, message: str, **kwargs: object) -> None: ...

    def _handle_syn_ack_control(
        self, control: ParsedRbUdpControlPacket
    ) -> bool: ...

    def _lane_for_control(
        self, control: ParsedRbUdpControlPacket
    ) -> RbUdpLane | None: ...

    def _apply_control_lane_ids(
        self,
        lane: RbUdpLane,
        control: ParsedRbUdpControlPacket,
    ) -> int: ...

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
    ) -> None: ...

    def _handle_flow_control(
        self,
        lane: RbUdpLane,
        control: ParsedRbUdpControlPacket,
        *,
        peer_logic_id: int,
    ) -> None: ...

    def _handle_established_control(
        self,
        lane: RbUdpLane,
        control: ParsedRbUdpControlPacket,
    ) -> None: ...

    def _handle_progress_control(
        self,
        lane: RbUdpLane,
        control: ParsedRbUdpControlPacket,
        *,
        peer_logic_id: int,
    ) -> None: ...

    def _send_offset_ack(
        self,
        lane: RbUdpLane,
        control: ParsedRbUdpControlPacket,
        *,
        status_word: int,
        remote_delta: int,
        log_label: str,
    ) -> tuple[int, int]: ...

    def _is_quii_play_ack_control(
        self,
        lane: RbUdpLane,
        control: ParsedRbUdpControlPacket,
        *,
        status16: int,
    ) -> bool: ...

    def _start_play_sync_from_control(
        self,
        lane: RbUdpLane,
        control: ParsedRbUdpControlPacket,
        *,
        reason: str,
    ) -> None: ...

    def _handle_play_late_status(
        self,
        lane: RbUdpLane,
        control: ParsedRbUdpControlPacket,
    ) -> None: ...

    def _handle_play_sync_status(
        self,
        lane: RbUdpLane,
        control: ParsedRbUdpControlPacket,
    ) -> None: ...


@dataclass(frozen=True)
class RbUdpControlDispatcher:
    """Route parsed RBUDP control packets to tunnel actions."""

    owner: RbUdpControlDispatcherOwner

    def handle(self, control: ParsedRbUdpControlPacket) -> None:
        owner = self.owner
        owner._last_control = control
        status16 = control.status_word & 0xFFFF
        owner._dbg(
            "recv_control",
            peer=owner._peer_addr,
            word4=hex(control.word4),
            word8=hex(control.word8),
            local_id=control.local_id,
            remote_id=control.remote_id,
            status=hex(control.status_word),
            status16=hex(status16),
        )

        if owner._handle_syn_ack_control(control):
            return

        lane = owner._lane_for_control(control)
        if lane is None:
            return

        peer_logic_id = owner._apply_control_lane_ids(lane, control)

        if status16 == (owner.CONTROL_HEARTBEAT_RESPONSE_STATUS & 0xFFFF):
            if control.local_id > 1 and control.remote_id > 1:
                owner._send_fragment_ack(
                    lane,
                    control.remote_id,
                    control.local_id,
                    word4=control.word8,
                    word8=control.word4,
                    log_label="send_control_heartbeat_response_ack",
                )
            else:
                owner._handle_flow_control(
                    lane, control, peer_logic_id=peer_logic_id
                )
            return

        if control.status_word == owner.CONTROL_ESTABLISHED_STATUS:
            owner._handle_established_control(lane, control)
            return

        if control.status_word == owner.CONTROL_PROGRESS_STATUS:
            owner._handle_progress_control(
                lane, control, peer_logic_id=peer_logic_id
            )
            return

        if control.status_word == owner.CONTROL_POST_CONNECT_STATUS:
            owner._send_offset_ack(
                lane,
                control,
                status_word=owner.CONTROL_POST_CONNECT_ACK_STATUS,
                remote_delta=0x38,
                log_label="send_control_post_connect_ack",
            )
            return

        if owner._is_quii_play_ack_control(
            lane,
            control,
            status16=status16,
        ):
            lane["quii_play_acked"] = True
            owner._send_offset_ack(
                lane,
                control,
                status_word=owner.CONTROL_POST_SETUP_ACK_STATUS,
                remote_delta=0x60,
                log_label="send_control_post_setup_ack",
            )
            owner._start_play_sync_from_control(
                lane, control, reason="quii_play_ack"
            )
            return

        if control.status_word == owner.CONTROL_POST_SETUP_STATUS:
            owner._send_offset_ack(
                lane,
                control,
                status_word=owner.CONTROL_POST_SETUP_ACK_STATUS,
                remote_delta=0x60,
                log_label="send_control_post_setup_ack",
            )
            owner._start_play_sync_from_control(
                lane, control, reason="post_setup"
            )
            return

        if control.status_word == owner.CONTROL_POST_PLAY_STATUS:
            owner._send_offset_ack(
                lane,
                control,
                status_word=owner.CONTROL_POST_PLAY_ACK_STATUS,
                remote_delta=0x60,
                log_label="send_control_post_play_ack",
            )
            owner._start_play_sync_from_control(
                lane, control, reason="post_play"
            )
            return

        if control.status_word == owner.CONTROL_STREAM_READY_STATUS:
            owner._send_offset_ack(
                lane,
                control,
                status_word=owner.CONTROL_STREAM_READY_ACK_STATUS,
                remote_delta=-0x08,
                log_label="send_control_stream_ready_ack",
            )
            owner._start_play_sync_from_control(
                lane, control, reason="stream_ready"
            )
            owner._quii_ready.set()
            return

        if status16 == (owner.CONTROL_HEARTBEAT_REQUEST_STATUS & 0xFFFF):
            owner._send_fragment_ack(
                lane,
                control.remote_id,
                control.local_id,
                word4=control.word8,
                word8=control.word4,
                status_word=owner.CONTROL_HEARTBEAT_RESPONSE_STATUS,
                log_label="send_control_heartbeat_response",
            )
            return

        if control.status_word == owner.CONTROL_PLAY_LATE_STATUS:
            owner._handle_play_late_status(lane, control)
            return

        if control.status_word == owner.CONTROL_PLAY_SYNC_STATUS:
            owner._handle_play_sync_status(lane, control)
