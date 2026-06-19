from quii_helper.protocols.rbudp.lanes import RbUdpLane
from quii_helper.protocols.rbudp.play_probes import RbUdpPlayProbeMixin


class RbUdpPlayStageMixin(RbUdpPlayProbeMixin):
    _lane_states: list[RbUdpLane]
    _peer_addr: tuple[str, int]

    def _send_play_stage_ack(
        self,
        lane: RbUdpLane,
        *,
        status_word: int,
        local_id: int,
        remote_id: int,
        log_label: str,
    ) -> None:
        self._send_lane_control(
            lane,
            status_word=status_word,
            local_id=local_id,
            remote_id=remote_id,
            log_label=log_label,
            update_lane=False,
        )

    def _maybe_send_play_stage_controls(
        self, lane: RbUdpLane, *, remote_id: int
    ) -> None:
        sent_count = int(lane["play_sync_sent_count"])
        local_id = int(lane["play_sync_local_id"])
        effective_remote_id = self._effective_play_sync_remote_id(
            lane, remote_id
        )
        if sent_count == 37:
            self._send_play_stage_ack(
                lane,
                status_word=self.CONTROL_PLAY_SYNC_STAGE2_STATUS,
                local_id=local_id,
                remote_id=effective_remote_id,
                log_label="send_control_play_stage2_ack",
            )
            return
        if sent_count == 41:
            lane["play_sync_remote_bias"] = (
                self.CONTROL_PLAY_SYNC_STAGE3_REMOTE_BIAS
            )
            effective_remote_id = self._effective_play_sync_remote_id(
                lane, remote_id
            )
            self._send_play_stage_ack(
                lane,
                status_word=self.CONTROL_PLAY_SYNC_STAGE3_STATUS,
                local_id=local_id,
                remote_id=effective_remote_id,
                log_label="send_control_play_stage3_ack",
            )
            if int(lane["word4"]) not in (0x3D000022, 0x3E000023):
                self._refresh_lane_word4(lane)
            return
        if sent_count == 49:
            lane["play_sync_local_id"] = (
                local_id + self.CONTROL_PLAY_SYNC_STAGE4_LOCAL_DELTA
            ) & 0xFFFFFFFF
            lane["play_sync_remote_bias"] = (
                self.CONTROL_PLAY_SYNC_STAGE4_REMOTE_BIAS
            )
            local_id = int(lane["play_sync_local_id"])
            effective_remote_id = self._effective_play_sync_remote_id(
                lane, remote_id
            )
            self._send_play_stage_ack(
                lane,
                status_word=self.CONTROL_PLAY_SYNC_STAGE4_STATUS,
                local_id=local_id,
                remote_id=effective_remote_id,
                log_label="send_control_play_stage4_ack",
            )
            return
        if sent_count == 53:
            lane["play_sync_remote_bias"] = (
                self.CONTROL_PLAY_SYNC_STAGE5_REMOTE_BIAS
            )
            local_id = int(lane["play_sync_local_id"])
            effective_remote_id = self._effective_play_sync_remote_id(
                lane, remote_id
            )
            self._send_play_stage_ack(
                lane,
                status_word=self.CONTROL_PLAY_SYNC_STAGE5_STATUS,
                local_id=local_id,
                remote_id=effective_remote_id,
                log_label="send_control_play_stage5_ack",
            )
            return
        if sent_count == 60:
            lane["play_sync_remote_bias"] = (
                self.CONTROL_PLAY_SYNC_STAGE6_REMOTE_BIAS
            )
            local_id = int(lane["play_sync_local_id"])
            effective_remote_id = self._effective_play_sync_remote_id(
                lane, remote_id
            )
            self._send_play_stage_ack(
                lane,
                status_word=self.CONTROL_PLAY_SYNC_STAGE6_STATUS,
                local_id=local_id,
                remote_id=effective_remote_id,
                log_label="send_control_play_stage6_ack",
            )
            return
        if sent_count == 61 and not bool(lane["play_transport_refresh_sent"]):
            self._prime_lan_transport(seq_base=0x00018313)
            lane["play_transport_refresh_sent"] = True
            return
        if sent_count == 67 and not bool(lane["play_transport_refresh2_sent"]):
            self._prime_lan_transport(seq_base=0x00018AE4)
            lane["play_transport_refresh2_sent"] = True
            return
        if (
            sent_count >= 68
            and bool(lane["play_transport_refresh2_sent"])
            and not bool(lane["play_word_refresh2_sent"])
        ):
            for late_lane in self._lane_states:
                if (
                    int(late_lane["local_id"]) == 0
                    and int(late_lane["remote_id"]) == 0
                ):
                    continue
                self._refresh_lane_word4(
                    late_lane,
                    target_word4=self._late_family_target_word4(late_lane),
                )
            lane["play_word_refresh2_sent"] = True
