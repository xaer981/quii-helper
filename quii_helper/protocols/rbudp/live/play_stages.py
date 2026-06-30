from typing import Protocol

from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane


class RbUdpPlayStageOwner(Protocol):
    CONTROL_PLAY_SYNC_STAGE2_STATUS: int
    CONTROL_PLAY_SYNC_STAGE3_REMOTE_BIAS: int
    CONTROL_PLAY_SYNC_STAGE3_STATUS: int
    CONTROL_PLAY_SYNC_STAGE4_LOCAL_DELTA: int
    CONTROL_PLAY_SYNC_STAGE4_REMOTE_BIAS: int
    CONTROL_PLAY_SYNC_STAGE4_STATUS: int
    CONTROL_PLAY_SYNC_STAGE5_REMOTE_BIAS: int
    CONTROL_PLAY_SYNC_STAGE5_STATUS: int
    CONTROL_PLAY_SYNC_STAGE6_REMOTE_BIAS: int
    CONTROL_PLAY_SYNC_STAGE6_STATUS: int
    _lane_states: list[RbUdpLane]
    _peer_addr: tuple[str, int]

    def _effective_play_sync_remote_id(
        self, lane: RbUdpLane, remote_id: int
    ) -> int: ...

    def _late_family_target_word4(self, lane: RbUdpLane) -> int: ...

    def _prime_lan_transport(self, *, seq_base: int | None = None) -> None: ...

    def _refresh_lane_word4(
        self, lane: RbUdpLane, *, target_word4: int | None = None
    ) -> None: ...

    def _send_lane_control(
        self,
        lane: RbUdpLane,
        *,
        status_word: int,
        local_id: int | None = None,
        remote_id: int | None = None,
        log_label: str | None = "send_control",
        update_lane: bool = True,
    ) -> None: ...


class RbUdpPlayStageController:
    """Send native-like play-sync stage control packets."""

    def __init__(self, owner: RbUdpPlayStageOwner) -> None:
        self._owner = owner

    def send_play_stage_ack(
        self,
        lane: RbUdpLane,
        *,
        status_word: int,
        local_id: int,
        remote_id: int,
        log_label: str,
    ) -> None:
        self._owner._send_lane_control(
            lane,
            status_word=status_word,
            local_id=local_id,
            remote_id=remote_id,
            log_label=log_label,
            update_lane=False,
        )

    def maybe_send_play_stage_controls(
        self, lane: RbUdpLane, *, remote_id: int
    ) -> None:
        owner = self._owner
        sent_count = int(lane["play_sync_sent_count"])
        local_id = int(lane["play_sync_local_id"])
        effective_remote_id = owner._effective_play_sync_remote_id(
            lane, remote_id
        )
        if sent_count == 37:
            self.send_play_stage_ack(
                lane,
                status_word=owner.CONTROL_PLAY_SYNC_STAGE2_STATUS,
                local_id=local_id,
                remote_id=effective_remote_id,
                log_label="send_control_play_stage2_ack",
            )
            return
        if sent_count == 41:
            lane["play_sync_remote_bias"] = (
                owner.CONTROL_PLAY_SYNC_STAGE3_REMOTE_BIAS
            )
            effective_remote_id = owner._effective_play_sync_remote_id(
                lane, remote_id
            )
            self.send_play_stage_ack(
                lane,
                status_word=owner.CONTROL_PLAY_SYNC_STAGE3_STATUS,
                local_id=local_id,
                remote_id=effective_remote_id,
                log_label="send_control_play_stage3_ack",
            )
            if int(lane["word4"]) not in (0x3D000022, 0x3E000023):
                owner._refresh_lane_word4(lane)
            return
        if sent_count == 49:
            lane["play_sync_local_id"] = (
                local_id + owner.CONTROL_PLAY_SYNC_STAGE4_LOCAL_DELTA
            ) & 0xFFFFFFFF
            lane["play_sync_remote_bias"] = (
                owner.CONTROL_PLAY_SYNC_STAGE4_REMOTE_BIAS
            )
            local_id = int(lane["play_sync_local_id"])
            effective_remote_id = owner._effective_play_sync_remote_id(
                lane, remote_id
            )
            self.send_play_stage_ack(
                lane,
                status_word=owner.CONTROL_PLAY_SYNC_STAGE4_STATUS,
                local_id=local_id,
                remote_id=effective_remote_id,
                log_label="send_control_play_stage4_ack",
            )
            return
        if sent_count == 53:
            lane["play_sync_remote_bias"] = (
                owner.CONTROL_PLAY_SYNC_STAGE5_REMOTE_BIAS
            )
            local_id = int(lane["play_sync_local_id"])
            effective_remote_id = owner._effective_play_sync_remote_id(
                lane, remote_id
            )
            self.send_play_stage_ack(
                lane,
                status_word=owner.CONTROL_PLAY_SYNC_STAGE5_STATUS,
                local_id=local_id,
                remote_id=effective_remote_id,
                log_label="send_control_play_stage5_ack",
            )
            return
        if sent_count == 60:
            lane["play_sync_remote_bias"] = (
                owner.CONTROL_PLAY_SYNC_STAGE6_REMOTE_BIAS
            )
            local_id = int(lane["play_sync_local_id"])
            effective_remote_id = owner._effective_play_sync_remote_id(
                lane, remote_id
            )
            self.send_play_stage_ack(
                lane,
                status_word=owner.CONTROL_PLAY_SYNC_STAGE6_STATUS,
                local_id=local_id,
                remote_id=effective_remote_id,
                log_label="send_control_play_stage6_ack",
            )
            return
        if sent_count == 61 and not bool(lane["play_transport_refresh_sent"]):
            owner._prime_lan_transport(seq_base=0x00018313)
            lane["play_transport_refresh_sent"] = True
            return
        if sent_count == 67 and not bool(lane["play_transport_refresh2_sent"]):
            owner._prime_lan_transport(seq_base=0x00018AE4)
            lane["play_transport_refresh2_sent"] = True
            return
        if (
            sent_count >= 68
            and bool(lane["play_transport_refresh2_sent"])
            and not bool(lane["play_word_refresh2_sent"])
        ):
            for late_lane in owner._lane_states:
                if (
                    int(late_lane["local_id"]) == 0
                    and int(late_lane["remote_id"]) == 0
                ):
                    continue
                owner._refresh_lane_word4(
                    late_lane,
                    target_word4=owner._late_family_target_word4(late_lane),
                )
            lane["play_word_refresh2_sent"] = True
