import time

from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane
from quii_helper.protocols.rbudp.live.play_stages import RbUdpPlayStageMixin
from quii_helper.protocols.rbudp.live.play_sync_state import (
    advance_play_sync_counter,
    decrement_play_sync_remaining,
    is_play_sync_exhausted,
    normalize_play_sync_iterations,
    should_log_play_sync_ack,
)


class RbUdpPlaySyncMixin(RbUdpPlayStageMixin):
    _lane_states: list[RbUdpLane]
    _quii_play_sent: object
    _stop: object

    def _send_play_sync_ack(
        self, lane: RbUdpLane, *, local_id: int, remote_id: int
    ) -> None:
        sent_count = int(lane["play_sync_sent_count"])
        self._send_lane_control(
            lane,
            status_word=self.CONTROL_PLAY_SYNC_ACK_STATUS,
            local_id=local_id,
            remote_id=remote_id,
            log_label=(
                "send_control_play_sync_ack"
                if should_log_play_sync_ack(sent_count)
                else None
            ),
            update_lane=False,
        )

    def _start_play_sync(
        self, lane: RbUdpLane, *, local_id: int, seed_remote_id: int
    ) -> None:
        configured_iterations = self._configured_play_sync_iterations()
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
            self._advance_play_sync_lane(
                lane, local_id=play_sync_local_id, remote_id=remote_id
            )

    def _play_sync_loop(self) -> None:
        while not self._stop.is_set():
            try:
                if self._quii_play_sent.is_set():
                    for lane in self._lane_states:
                        if not bool(lane["play_sync_active"]):
                            continue
                        if self._is_play_sync_exhausted(lane):
                            lane["play_sync_active"] = False
                            continue
                        local_id = int(lane["play_sync_local_id"])
                        remote_id = int(lane["play_sync_counter"])
                        if not local_id or not remote_id:
                            continue
                        self._advance_play_sync_lane(
                            lane, local_id=local_id, remote_id=remote_id
                        )
            except Exception:
                pass
            time.sleep(0.05)

    def _advance_play_sync_lane(
        self, lane: RbUdpLane, *, local_id: int, remote_id: int
    ) -> None:
        self._send_play_sync_ack(
            lane,
            local_id=local_id,
            remote_id=self._effective_play_sync_remote_id(lane, remote_id),
        )
        lane["play_sync_sent_count"] = int(lane["play_sync_sent_count"]) + 1
        self._maybe_send_play_probe(lane, remote_id=remote_id)
        self._maybe_send_play_stage_controls(lane, remote_id=remote_id)
        lane["play_sync_counter"] = advance_play_sync_counter(
            remote_id,
            self.CONTROL_PLAY_SYNC_STEP,
        )
        if int(lane["play_sync_remaining"]) > 0:
            lane["play_sync_remaining"] = decrement_play_sync_remaining(
                int(lane["play_sync_remaining"])
            )

    def _configured_play_sync_iterations(self) -> int:
        # Native RBUDP clears its send-list from ACK remote_id values;
        # synthetic play-sync ACKs are only safe
        # as an explicit diagnostic experiment.
        return normalize_play_sync_iterations(
            getattr(self.config, "play_sync_iterations", 0)
        )

    def _is_play_sync_exhausted(self, lane: RbUdpLane) -> bool:
        return is_play_sync_exhausted(
            configured_iterations=self._configured_play_sync_iterations(),
            remaining=int(lane["play_sync_remaining"]),
        )
