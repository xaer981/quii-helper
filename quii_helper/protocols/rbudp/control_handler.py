from quii_helper.protocols.rbudp.control_status import RbUdpControlStatusMixin
from quii_helper.protocols.rbudp.models import ParsedRbUdpControlPacket


class RbUdpControlHandlerMixin(RbUdpControlStatusMixin):
    _last_control: ParsedRbUdpControlPacket | None
    _peer_addr: tuple[str, int]
    _quii_ready: object

    def _handle_control(self, control: ParsedRbUdpControlPacket) -> None:
        self._last_control = control
        status16 = control.status_word & 0xFFFF
        self._dbg(
            "recv_control",
            peer=self._peer_addr,
            word4=hex(control.word4),
            word8=hex(control.word8),
            local_id=control.local_id,
            remote_id=control.remote_id,
            status=hex(control.status_word),
            status16=hex(status16),
        )

        if self._handle_syn_ack_control(control):
            return

        lane = self._lane_for_control(control)
        if lane is None:
            return

        peer_logic_id = self._apply_control_lane_ids(lane, control)

        if status16 == (self.CONTROL_HEARTBEAT_RESPONSE_STATUS & 0xFFFF):
            if control.local_id > 1 and control.remote_id > 1:
                self._send_fragment_ack(
                    lane,
                    control.remote_id,
                    control.local_id,
                    word4=control.word8,
                    word8=control.word4,
                    log_label="send_control_heartbeat_response_ack",
                )
            else:
                self._handle_flow_control(
                    lane, control, peer_logic_id=peer_logic_id
                )
            return

        if control.status_word == self.CONTROL_ESTABLISHED_STATUS:
            self._handle_established_control(lane, control)
            return

        if control.status_word == self.CONTROL_PROGRESS_STATUS:
            self._handle_progress_control(
                lane, control, peer_logic_id=peer_logic_id
            )
            return

        if control.status_word == self.CONTROL_POST_CONNECT_STATUS:
            self._send_offset_ack(
                lane,
                control,
                status_word=self.CONTROL_POST_CONNECT_ACK_STATUS,
                remote_delta=0x38,
                log_label="send_control_post_connect_ack",
            )
            return

        if self._is_quii_play_ack_control(lane, control, status16=status16):
            lane["quii_play_acked"] = True
            self._send_offset_ack(
                lane,
                control,
                status_word=self.CONTROL_POST_SETUP_ACK_STATUS,
                remote_delta=0x60,
                log_label="send_control_post_setup_ack",
            )
            self._start_play_sync_from_control(
                lane, control, reason="quii_play_ack"
            )
            return

        if control.status_word == self.CONTROL_POST_SETUP_STATUS:
            self._send_offset_ack(
                lane,
                control,
                status_word=self.CONTROL_POST_SETUP_ACK_STATUS,
                remote_delta=0x60,
                log_label="send_control_post_setup_ack",
            )
            self._start_play_sync_from_control(
                lane, control, reason="post_setup"
            )
            return

        if control.status_word == self.CONTROL_POST_PLAY_STATUS:
            self._send_offset_ack(
                lane,
                control,
                status_word=self.CONTROL_POST_PLAY_ACK_STATUS,
                remote_delta=0x60,
                log_label="send_control_post_play_ack",
            )
            self._start_play_sync_from_control(
                lane, control, reason="post_play"
            )
            return

        if control.status_word == self.CONTROL_STREAM_READY_STATUS:
            self._send_offset_ack(
                lane,
                control,
                status_word=self.CONTROL_STREAM_READY_ACK_STATUS,
                remote_delta=-0x08,
                log_label="send_control_stream_ready_ack",
            )
            self._start_play_sync_from_control(
                lane, control, reason="stream_ready"
            )
            self._quii_ready.set()
            return

        if status16 == (self.CONTROL_HEARTBEAT_REQUEST_STATUS & 0xFFFF):
            self._send_fragment_ack(
                lane,
                control.remote_id,
                control.local_id,
                word4=control.word8,
                word8=control.word4,
                status_word=self.CONTROL_HEARTBEAT_RESPONSE_STATUS,
                log_label="send_control_heartbeat_response",
            )
            return

        if control.status_word == self.CONTROL_PLAY_LATE_STATUS:
            self._handle_play_late_status(lane, control)
            return

        if control.status_word == self.CONTROL_PLAY_SYNC_STATUS:
            self._handle_play_sync_status(lane, control)

    def _is_quii_play_ack_control(
        self,
        lane,
        control: ParsedRbUdpControlPacket,
        *,
        status16: int,
    ) -> bool:
        if status16 != (self.CONTROL_ESTABLISHED_STATUS & 0xFFFF):
            return False
        if not self._quii_play_sent.is_set() or bool(lane["quii_play_acked"]):
            return False
        play_end_local_id = int(lane.get("quii_play_end_local_id", 0))
        return (
            play_end_local_id > 0
            and control.remote_id == play_end_local_id
            and control.local_id > 1
        )
