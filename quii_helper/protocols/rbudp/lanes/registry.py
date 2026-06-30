import random
from collections.abc import Sequence
from dataclasses import dataclass

from quii_helper.protocols.rbudp.core.models import ParsedRbUdpControlPacket

RbUdpLane = dict[str, int | bool]


def bootstrap_word8_values(count: int) -> list[int]:
    values = [0x01000000, 0x02000001]
    while len(values) < count:
        idx = len(values)
        values.append(((idx + 1) << 24) | idx)
    return values[:count]


def build_rbudp_lane_states(
    *,
    src_ids: Sequence[int],
    bootstrap_word4: int,
    bootstrap_remote_id: int,
    bootstrap_local_ids: Sequence[int],
) -> list[RbUdpLane]:
    word8_values = bootstrap_word8_values(len(src_ids))
    bootstrap_rand_seed = random.randrange(1, 0x10000)
    lanes: list[RbUdpLane] = []
    for idx, src_id in enumerate(src_ids):
        bootstrap_local_id = bootstrap_local_ids[
            min(idx, len(bootstrap_local_ids) - 1)
        ]
        lane_seed = (bootstrap_rand_seed - (idx * 0x0101)) & 0xFFFF
        if lane_seed == 0:
            lane_seed = 1
        lanes.append(
            {
                "src_id": src_id,
                "bootstrap_word4": bootstrap_word4,
                "bootstrap_word8": word8_values[idx],
                "bootstrap_local_id": bootstrap_local_id,
                "bootstrap_remote_id": bootstrap_remote_id,
                "word4": 0,
                "word8": 0,
                "peer_word4": 0,
                "peer_word8": 0,
                "local_id": 0,
                "remote_id": 0,
                "nonce": lane_seed,
                "connect_sent": False,
                "setup_probe_sent": False,
                "post_play_established_sent": False,
                "quii_play_end_local_id": 0,
                "quii_play_acked": False,
                "play_sync_active": False,
                "play_sync_local_id": 0,
                "play_sync_counter": 0,
                "play_sync_remaining": 0,
                "play_probe_stage": 0,
                "play_sync_sent_count": 0,
                "play_sync_remote_bias": 0,
                "play_word_refresh_sent": False,
                "play_transport_refresh_sent": False,
                "play_transport_refresh2_sent": False,
                "play_word_refresh2_sent": False,
                "progress_sent": False,
                "flow_sent": False,
                "established_sent": False,
                "syn_ack_received": False,
                "peer_logic_id": 0,
                "quii_setup_acked": False,
            }
        )
    return lanes


@dataclass
class RbUdpLaneRegistry:
    """Own lane state lookup while preserving native lane dictionaries."""

    lanes: list[RbUdpLane]

    @classmethod
    def create(
        cls,
        *,
        src_ids: Sequence[int],
        bootstrap_word4: int,
        bootstrap_remote_id: int,
        bootstrap_local_ids: Sequence[int],
    ) -> "RbUdpLaneRegistry":
        return cls(
            build_rbudp_lane_states(
                src_ids=src_ids,
                bootstrap_word4=bootstrap_word4,
                bootstrap_remote_id=bootstrap_remote_id,
                bootstrap_local_ids=bootstrap_local_ids,
            )
        )

    def for_packet_words(self, *, word4: int, word8: int) -> RbUdpLane | None:
        for lane in self.lanes:
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

    def active(self, src_id: int) -> RbUdpLane:
        for lane in self.lanes:
            if int(lane["src_id"]) == src_id:
                return lane
        return self.lanes[0]

    def for_syn_ack(
        self, control: ParsedRbUdpControlPacket
    ) -> RbUdpLane | None:
        for lane in self.lanes:
            if control.word4 == int(lane["bootstrap_word8"]):
                return lane
        return None

    def for_control(
        self, control: ParsedRbUdpControlPacket
    ) -> RbUdpLane | None:
        for lane in self.lanes:
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

    def for_src_id(self, src_id: int) -> RbUdpLane | None:
        for lane in self.lanes:
            if int(lane["src_id"]) == src_id:
                return lane
        return None
