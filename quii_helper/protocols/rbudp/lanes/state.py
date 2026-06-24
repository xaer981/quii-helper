from quii_helper.protocols.rbudp.core.models import ParsedRbUdpControlPacket
from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane


class RbUdpLaneStateMixin:
    _lane_states: list[RbUdpLane]
    src_id: int
    src_ids: list[int]

    def _dbg(self, message: str, **kwargs) -> None:
        raise NotImplementedError

    def _lane_for_packet_words(
        self, *, word4: int, word8: int
    ) -> RbUdpLane | None:
        for lane in self._lane_states:
            if (
                int(lane["peer_word4"]) == word4
                and int(lane["peer_word8"]) == word8
            ):
                return lane
            if int(lane["word4"]) == word8 and int(lane["word8"]) == word4:
                return lane
            if (
                int(lane["word8"]) == word4
                or int(lane["bootstrap_word8"]) == word4
            ):
                return lane
        return None

    def _next_lane_nonce(self, lane: RbUdpLane) -> int:
        nonce = int(lane["nonce"]) & 0xFFFFFFFF
        lane["nonce"] = (nonce + 1) & 0xFFFFFFFF
        return nonce

    def _effective_play_sync_remote_id(
        self, lane: RbUdpLane, remote_id: int
    ) -> int:
        bias = int(lane["play_sync_remote_bias"])
        return (remote_id + bias) & 0xFFFFFFFF

    def _refresh_lane_word4(
        self,
        lane: RbUdpLane,
        *,
        target_word4: int | None = None,
        high_delta: int = 0x12,
        low_delta: int = 0x0A,
    ) -> None:
        current_word4 = int(lane["word4"])
        if target_word4 is not None:
            refreshed_word4 = target_word4 & 0xFFFFFFFF
        else:
            high = (current_word4 >> 24) & 0xFF
            low = current_word4 & 0xFF
            if high < high_delta or low < low_delta:
                return
            refreshed_word4 = (
                ((high - high_delta) << 24)
                | ((current_word4 & 0x00FFFF00))
                | ((low - low_delta) & 0xFF)
            )
        lane["word4"] = refreshed_word4
        lane["peer_word8"] = refreshed_word4
        self._dbg(
            "refresh_lane_word4",
            src_id=hex(int(lane["src_id"])),
            word4=hex(refreshed_word4),
            word8=hex(int(lane["word8"])),
            peer_word4=hex(int(lane["peer_word4"])),
            peer_word8=hex(int(lane["peer_word8"])),
        )

    def _late_family_target_word4(self, lane: RbUdpLane) -> int:
        lane_offset = int(lane["src_id"]) - int(self.src_ids[0])
        return (0x3D000022 + (lane_offset * 0x01000001)) & 0xFFFFFFFF

    def _active_lane(self) -> RbUdpLane:
        for lane in self._lane_states:
            if int(lane["src_id"]) == self.src_id:
                return lane
        return self._lane_states[0]

    def _lane_for_syn_ack(
        self, control: ParsedRbUdpControlPacket
    ) -> RbUdpLane | None:
        for lane in self._lane_states:
            bootstrap_word8 = int(lane["bootstrap_word8"])
            if control.word4 == bootstrap_word8:
                return lane
        return None

    def _lane_for_control(
        self, control: ParsedRbUdpControlPacket
    ) -> RbUdpLane | None:
        for lane in self._lane_states:
            if (
                int(lane["peer_word4"]) == control.word4
                and int(lane["peer_word8"]) == control.word8
            ):
                return lane
            if (
                int(lane["word8"]) == control.word4
                or int(lane["bootstrap_word8"]) == control.word4
            ):
                return lane
        return None

    def _lane_for_src_id(self, src_id: int) -> RbUdpLane | None:
        for lane in self._lane_states:
            if int(lane["src_id"]) == src_id:
                return lane
        return None
