from quii_helper.protocols.rbudp.kcp_link_packets import build_rb_data_packet
from quii_helper.protocols.rbudp.lanes import RbUdpLane
from quii_helper.protocols.rbudp.wrapped_packets import (
    build_rb_udp_wrapped_packet,
)


class RbUdpPlayProbeMixin:
    _lane_states: list[RbUdpLane]
    _peer_addr: tuple[str, int]

    def _send_play_data_probe(
        self,
        lane: RbUdpLane,
        *,
        seq: int,
        local_id: int,
        remote_id: int,
        payload: bytes,
    ) -> None:
        inner = build_rb_data_packet(
            payload=payload,
            src_id=int(lane["src_id"]),
            dest_id=self.CONTROL_PLAY_PROBE_INNER_DEST,
            seq=seq,
        )
        rand16 = self._next_lane_nonce(lane) & 0xFFFF
        packet = build_rb_udp_wrapped_packet(
            inner,
            word4=int(lane["word4"]),
            word8=int(lane["word8"]),
            local_id=local_id,
            remote_id=remote_id,
            status_word=self.WRAPPED_STATUS,
            nonce=rand16,
            tag8=self.CONTROL_PLAY_PROBE_TAG,
        )
        self._dbg(
            "send_wrapped_play_probe",
            peer=self._peer_addr,
            src_id=hex(int(lane["src_id"])),
            word4=hex(int(lane["word4"])),
            word8=hex(int(lane["word8"])),
            local_id=local_id,
            remote_id=remote_id,
            seq=seq,
            inner_dest_id=hex(self.CONTROL_PLAY_PROBE_INNER_DEST),
            payload_len=len(payload),
        )
        self._send_udp(packet)
        # Same RBUDP data-send rule
        # as _send_wrapped(): conn+0x9c advances by payload length.
        lane["local_id"] = (local_id + len(inner)) & 0xFFFFFFFF

    def _maybe_send_play_probe(
        self, lane: RbUdpLane, *, remote_id: int
    ) -> None:
        if not bool(getattr(self.config, "enable_play_probes", False)):
            return
        probe_stage = int(lane["play_probe_stage"])
        sent_count = int(lane["play_sync_sent_count"])
        local_base = int(lane["play_sync_local_id"])
        if not local_base:
            return
        if probe_stage == 0 and sent_count >= 18:
            self._refresh_all_late_lanes_for_probe(lane)
            self._send_play_data_probe(
                lane,
                seq=2,
                local_id=(local_base - 0x88) & 0xFFFFFFFF,
                remote_id=(remote_id + 0x118) & 0xFFFFFFFF,
                payload=self.CONTROL_PLAY_PROBE2_PAYLOAD,
            )
            lane["play_probe_stage"] = 1
            return
        if probe_stage == 1 and sent_count >= 35:
            self._send_play_data_probe(
                lane,
                seq=3,
                local_id=local_base,
                remote_id=(remote_id - 0x12) & 0xFFFFFFFF,
                payload=self.CONTROL_PLAY_PROBE3_PAYLOAD,
            )
            lane["play_sync_local_id"] = (
                local_base + self.CONTROL_PLAY_SYNC_STAGE2_LOCAL_DELTA
            ) & 0xFFFFFFFF
            lane["play_sync_remote_bias"] = (
                self.CONTROL_PLAY_SYNC_STAGE2_REMOTE_BIAS
            )
            lane["play_probe_stage"] = 2
            return
        if probe_stage == 2 and sent_count >= 48:
            self._send_play_data_probe(
                lane,
                seq=4,
                local_id=local_base,
                remote_id=(remote_id - 0x152) & 0xFFFFFFFF,
                payload=self.CONTROL_PLAY_PROBE4_PAYLOAD,
            )
            lane["play_probe_stage"] = 3

    def _refresh_all_late_lanes_for_probe(self, lane: RbUdpLane) -> None:
        if bool(lane["play_word_refresh_sent"]):
            return
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
            late_lane["play_word_refresh_sent"] = True
            late_lane["play_word_refresh2_sent"] = True
