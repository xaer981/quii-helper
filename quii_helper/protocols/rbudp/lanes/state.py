from collections.abc import Callable

from quii_helper.protocols.rbudp.core.models import ParsedRbUdpControlPacket
from quii_helper.protocols.rbudp.lanes.registry import (
    RbUdpLane,
    RbUdpLaneRegistry,
)


class RbUdpLaneState:
    """Provide lane lookup and mutation helpers for an RBUDP tunnel."""

    def __init__(
        self,
        *,
        lane_registry: RbUdpLaneRegistry,
        src_id: int,
        src_ids: list[int],
        debug: Callable[..., None],
    ) -> None:
        self._lane_registry = lane_registry
        self._src_id = src_id
        self._src_ids = src_ids
        self._debug = debug

    def lane_for_packet_words(
        self, *, word4: int, word8: int
    ) -> RbUdpLane | None:
        return self._lane_registry.for_packet_words(word4=word4, word8=word8)

    def next_lane_nonce(self, lane: RbUdpLane) -> int:
        nonce = int(lane["nonce"]) & 0xFFFFFFFF
        lane["nonce"] = (nonce + 1) & 0xFFFFFFFF
        return nonce

    @staticmethod
    def effective_play_sync_remote_id(lane: RbUdpLane, remote_id: int) -> int:
        bias = int(lane["play_sync_remote_bias"])
        return (remote_id + bias) & 0xFFFFFFFF

    def refresh_lane_word4(
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
        self._debug(
            "refresh_lane_word4",
            src_id=hex(int(lane["src_id"])),
            word4=hex(refreshed_word4),
            word8=hex(int(lane["word8"])),
            peer_word4=hex(int(lane["peer_word4"])),
            peer_word8=hex(int(lane["peer_word8"])),
        )

    def late_family_target_word4(self, lane: RbUdpLane) -> int:
        lane_offset = int(lane["src_id"]) - int(self._src_ids[0])
        return (0x3D000022 + (lane_offset * 0x01000001)) & 0xFFFFFFFF

    def active_lane(self) -> RbUdpLane:
        return self._lane_registry.active(self._src_id)

    def lane_for_syn_ack(
        self, control: ParsedRbUdpControlPacket
    ) -> RbUdpLane | None:
        return self._lane_registry.for_syn_ack(control)

    def lane_for_control(
        self, control: ParsedRbUdpControlPacket
    ) -> RbUdpLane | None:
        return self._lane_registry.for_control(control)

    def lane_for_src_id(self, src_id: int) -> RbUdpLane | None:
        return self._lane_registry.for_src_id(src_id)
