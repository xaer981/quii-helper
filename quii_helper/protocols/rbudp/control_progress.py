from quii_helper.protocols.rbudp.lanes import RbUdpLane
from quii_helper.protocols.rbudp.models import ParsedRbUdpControlPacket


class RbUdpControlProgressMixin:
    def _handle_flow_control(
        self,
        lane: RbUdpLane,
        control: ParsedRbUdpControlPacket,
        *,
        peer_logic_id: int,
    ) -> None:
        if (
            control.local_id == 1
            and peer_logic_id
            and not bool(lane["flow_sent"])
        ):
            self._send_lane_control(
                lane,
                status_word=self.CONTROL_FLOW_STATUS,
                local_id=peer_logic_id,
                remote_id=1,
                log_label="send_control_flow",
            )
            lane["flow_sent"] = True

    def _handle_established_control(
        self, lane: RbUdpLane, control: ParsedRbUdpControlPacket
    ) -> None:
        if (
            self._quii_play_sent.is_set()
            and control.local_id > 1
            and control.remote_id > 1
        ):
            self._send_lane_control(
                lane,
                status_word=self.CONTROL_PLAY_ESTABLISHED_ACK_STATUS,
                local_id=control.remote_id,
                remote_id=control.local_id,
                log_label="send_control_play_established_ack",
            )
            self._start_play_sync_from_control(
                lane, control, reason="established"
            )

    def _start_play_sync_from_control(
        self,
        lane: RbUdpLane,
        control: ParsedRbUdpControlPacket,
        *,
        reason: str,
    ) -> None:
        if (
            not self._quii_play_sent.is_set()
            or bool(lane["play_sync_active"])
            or control.local_id <= 1
        ):
            return
        local_id = (
            control.local_id + self.CONTROL_PLAY_SYNC_LOCAL_BIAS
        ) & 0xFFFFFFFF
        seed_remote_id = (
            control.local_id + self.CONTROL_PLAY_SYNC_STEP
        ) & 0xFFFFFFFF
        self._dbg(
            "play_sync_start",
            reason=reason,
            src_id=hex(int(lane["src_id"])),
            control_local_id=control.local_id,
            control_remote_id=control.remote_id,
            local_id=local_id,
            seed_remote_id=seed_remote_id,
        )
        self._start_play_sync(
            lane, local_id=local_id, seed_remote_id=seed_remote_id
        )

    def _handle_progress_control(
        self,
        lane: RbUdpLane,
        control: ParsedRbUdpControlPacket,
        *,
        peer_logic_id: int,
    ) -> None:
        if (
            peer_logic_id
            and control.remote_id == peer_logic_id
            and not bool(lane["progress_sent"])
            and not bool(lane.get("setup_probe_sent", False))
        ):
            self._dbg(
                "progress_reconnect_hint",
                src_id=hex(int(lane["src_id"])),
                control_local_id=control.local_id,
                control_remote_id=control.remote_id,
                peer_logic_id=peer_logic_id,
            )
            self._send_wrapped_connect(lane)
        if (
            control.local_id == peer_logic_id
            and peer_logic_id
            and control.remote_id == peer_logic_id
            and not bool(lane["progress_sent"])
        ):
            self._send_lane_control(
                lane,
                status_word=self.CONTROL_PROGRESS_STATUS,
                local_id=peer_logic_id,
                remote_id=peer_logic_id,
                log_label="send_control_progress",
            )
            lane["progress_sent"] = True
            self._send_wrapped_connect(lane)
