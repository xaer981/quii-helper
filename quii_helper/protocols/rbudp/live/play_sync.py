import time
from typing import Protocol, cast

from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane
from quii_helper.protocols.rbudp.live.play_probes import (
    RbUdpPlayProbeOwner,
    RbUdpPlayProbeSender,
)
from quii_helper.protocols.rbudp.live.play_stages import (
    RbUdpPlayStageController,
    RbUdpPlayStageOwner,
)
from quii_helper.protocols.rbudp.live.play_sync_state import (
    advance_play_sync_counter,
    decrement_play_sync_remaining,
    is_play_sync_exhausted,
    normalize_play_sync_iterations,
    should_log_play_sync_ack,
)


class _EventLike(Protocol):
    def is_set(self) -> bool: ...


class _PlaySyncConfig(Protocol):
    play_sync_iterations: int


class RbUdpPlaySyncOwner(Protocol):
    CONTROL_PLAY_SYNC_ACK_STATUS: int
    CONTROL_PLAY_SYNC_STEP: int
    _lane_states: list[RbUdpLane]
    _quii_play_sent: _EventLike
    _stop: _EventLike
    config: _PlaySyncConfig

    def _effective_play_sync_remote_id(
        self, lane: RbUdpLane, remote_id: int
    ) -> int: ...

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


class RbUdpPlaySync:
    """Drive optional RBUDP play-sync ACK loop."""

    def __init__(self, owner: RbUdpPlaySyncOwner) -> None:
        self._owner = owner
        self._play_probe_sender = RbUdpPlayProbeSender(
            cast(RbUdpPlayProbeOwner, owner)
        )
        self._play_stage_controller = RbUdpPlayStageController(
            cast(RbUdpPlayStageOwner, owner)
        )

    def send_play_sync_ack(
        self, lane: RbUdpLane, *, local_id: int, remote_id: int
    ) -> None:
        owner = self._owner
        sent_count = int(lane["play_sync_sent_count"])
        owner._send_lane_control(
            lane,
            status_word=owner.CONTROL_PLAY_SYNC_ACK_STATUS,
            local_id=local_id,
            remote_id=remote_id,
            log_label=(
                "send_control_play_sync_ack"
                if should_log_play_sync_ack(sent_count)
                else None
            ),
            update_lane=False,
        )

    def start_play_sync(
        self, lane: RbUdpLane, *, local_id: int, seed_remote_id: int
    ) -> None:
        configured_iterations = self.configured_play_sync_iterations()
        if configured_iterations <= 0:
            return
        lane["play_sync_active"] = True
        lane["play_sync_local_id"] = local_id & 0xFFFFFFFF
        lane["play_sync_counter"] = seed_remote_id & 0xFFFFFFFF
        lane["play_sync_remaining"] = configured_iterations
        lane["play_sync_sent_count"] = 0
        lane["play_sync_remote_bias"] = 0
        lane["play_word_refresh_sent"] = False
        lane["play_transport_refresh_sent"] = False
        lane["play_transport_refresh2_sent"] = False
        lane["play_word_refresh2_sent"] = False
        play_sync_local_id = int(lane["play_sync_local_id"])
        remote_id = int(lane["play_sync_counter"])
        if play_sync_local_id and remote_id:
            self.advance_play_sync_lane(
                lane, local_id=play_sync_local_id, remote_id=remote_id
            )

    def run_loop(self) -> None:
        owner = self._owner
        while not owner._stop.is_set():
            try:
                if owner._quii_play_sent.is_set():
                    for lane in owner._lane_states:
                        if not bool(lane["play_sync_active"]):
                            continue
                        if self.is_play_sync_exhausted(lane):
                            lane["play_sync_active"] = False
                            continue
                        local_id = int(lane["play_sync_local_id"])
                        remote_id = int(lane["play_sync_counter"])
                        if not local_id or not remote_id:
                            continue
                        self.advance_play_sync_lane(
                            lane, local_id=local_id, remote_id=remote_id
                        )
            except Exception:
                pass
            time.sleep(0.05)

    def advance_play_sync_lane(
        self, lane: RbUdpLane, *, local_id: int, remote_id: int
    ) -> None:
        owner = self._owner
        self.send_play_sync_ack(
            lane,
            local_id=local_id,
            remote_id=owner._effective_play_sync_remote_id(lane, remote_id),
        )
        lane["play_sync_sent_count"] = int(lane["play_sync_sent_count"]) + 1
        self.maybe_send_play_probe(lane, remote_id=remote_id)
        self.maybe_send_play_stage_controls(lane, remote_id=remote_id)
        lane["play_sync_counter"] = advance_play_sync_counter(
            remote_id,
            owner.CONTROL_PLAY_SYNC_STEP,
        )
        if int(lane["play_sync_remaining"]) > 0:
            lane["play_sync_remaining"] = decrement_play_sync_remaining(
                int(lane["play_sync_remaining"])
            )

    def configured_play_sync_iterations(self) -> int:
        # Native RBUDP clears its send-list from ACK remote_id values;
        # synthetic play-sync ACKs are only safe
        # as an explicit diagnostic experiment.
        return normalize_play_sync_iterations(
            getattr(self._owner.config, "play_sync_iterations", 0)
        )

    def is_play_sync_exhausted(self, lane: RbUdpLane) -> bool:
        return is_play_sync_exhausted(
            configured_iterations=self.configured_play_sync_iterations(),
            remaining=int(lane["play_sync_remaining"]),
        )

    def send_play_data_probe(
        self,
        lane: RbUdpLane,
        *,
        seq: int,
        local_id: int,
        remote_id: int,
        payload: bytes,
    ) -> None:
        self._play_probe_sender.send_play_data_probe(
            lane,
            seq=seq,
            local_id=local_id,
            remote_id=remote_id,
            payload=payload,
        )

    def maybe_send_play_probe(
        self, lane: RbUdpLane, *, remote_id: int
    ) -> None:
        self._play_probe_sender.maybe_send_play_probe(
            lane, remote_id=remote_id
        )

    def refresh_all_late_lanes_for_probe(self, lane: RbUdpLane) -> None:
        self._play_probe_sender.refresh_all_late_lanes_for_probe(lane)

    def send_play_stage_ack(
        self,
        lane: RbUdpLane,
        *,
        status_word: int,
        local_id: int,
        remote_id: int,
        log_label: str,
    ) -> None:
        self._play_stage_controller.send_play_stage_ack(
            lane,
            status_word=status_word,
            local_id=local_id,
            remote_id=remote_id,
            log_label=log_label,
        )

    def maybe_send_play_stage_controls(
        self, lane: RbUdpLane, *, remote_id: int
    ) -> None:
        self._play_stage_controller.maybe_send_play_stage_controls(
            lane, remote_id=remote_id
        )
