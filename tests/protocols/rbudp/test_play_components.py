from types import SimpleNamespace

from quii_helper.protocols.rbudp.lanes.registry import (
    RbUdpLane,
    build_rbudp_lane_states,
)
from quii_helper.protocols.rbudp.live.play_probes import RbUdpPlayProbeSender
from quii_helper.protocols.rbudp.live.play_stages import (
    RbUdpPlayStageController,
)


def _lanes() -> list[RbUdpLane]:
    lanes = build_rbudp_lane_states(
        src_ids=[0x04000006, 0x04000007],
        bootstrap_word4=0,
        bootstrap_remote_id=1,
        bootstrap_local_ids=[0, 1],
    )
    for index, lane in enumerate(lanes):
        lane["word4"] = 0x3D000022 + index
        lane["word8"] = 0x01000000 + index
        lane["local_id"] = 405
        lane["remote_id"] = 26061
    return lanes


class _LiveOwner:
    CONTROL_PLAY_PROBE_INNER_DEST = 0x0B030000
    CONTROL_PLAY_PROBE_TAG = b"\x00" * 8
    CONTROL_PLAY_PROBE2_PAYLOAD = b"probe2"
    CONTROL_PLAY_PROBE3_PAYLOAD = b"probe3"
    CONTROL_PLAY_PROBE4_PAYLOAD = b"probe4"
    CONTROL_PLAY_SYNC_STAGE2_LOCAL_DELTA = 0x88
    CONTROL_PLAY_SYNC_STAGE2_REMOTE_BIAS = -0x12
    CONTROL_PLAY_SYNC_STAGE2_STATUS = 0xFB540900
    CONTROL_PLAY_SYNC_STAGE3_REMOTE_BIAS = -0x60
    CONTROL_PLAY_SYNC_STAGE3_STATUS = 0xFAD40900
    CONTROL_PLAY_SYNC_STAGE4_LOCAL_DELTA = 0x88
    CONTROL_PLAY_SYNC_STAGE4_REMOTE_BIAS = 0x1F3
    CONTROL_PLAY_SYNC_STAGE4_STATUS = 0xFE0D0900
    CONTROL_PLAY_SYNC_STAGE5_REMOTE_BIAS = -0x198
    CONTROL_PLAY_SYNC_STAGE5_STATUS = 0xFC0C0900
    CONTROL_PLAY_SYNC_STAGE6_REMOTE_BIAS = -0x10B
    CONTROL_PLAY_SYNC_STAGE6_STATUS = 0xFB7F0900
    WRAPPED_STATUS = 0x1900

    def __init__(self) -> None:
        self._lane_states = _lanes()
        self._peer_addr = ("192.168.1.176", 59318)
        self.config = SimpleNamespace(enable_play_probes=True)
        self.src_ids = [0x04000006, 0x04000007]
        self.control: list[tuple[RbUdpLane, dict[str, object]]] = []
        self.debug: list[tuple[str, dict[str, object]]] = []
        self.refreshed: list[RbUdpLane] = []
        self.sent_udp: list[bytes] = []

    def _dbg(self, message: str, **kwargs: object) -> None:
        self.debug.append((message, kwargs))

    def _effective_play_sync_remote_id(
        self, lane: RbUdpLane, remote_id: int
    ) -> int:
        return (remote_id + int(lane["play_sync_remote_bias"])) & 0xFFFFFFFF

    def _late_family_target_word4(self, lane: RbUdpLane) -> int:
        return int(lane["word4"]) + 0x100

    def _next_lane_nonce(self, lane: RbUdpLane) -> int:
        return 0xCAFE

    def _prime_lan_transport(self, *, seq_base: int | None = None) -> None:
        self.debug.append(("prime_lan_transport", {"seq_base": seq_base}))

    def _refresh_lane_word4(
        self, lane: RbUdpLane, *, target_word4: int | None = None
    ) -> None:
        if target_word4 is not None:
            lane["word4"] = target_word4
        self.refreshed.append(lane)

    def _send_lane_control(
        self,
        lane: RbUdpLane,
        *,
        status_word: int,
        local_id: int | None = None,
        remote_id: int | None = None,
        log_label: str | None = "send_control",
        update_lane: bool = True,
    ) -> None:
        self.control.append(
            (
                lane,
                {
                    "status_word": status_word,
                    "local_id": local_id,
                    "remote_id": remote_id,
                    "log_label": log_label,
                    "update_lane": update_lane,
                },
            )
        )

    def _send_udp(self, packet: bytes) -> None:
        self.sent_udp.append(packet)


class RbUdpPlayComponentTests:
    def test_stage_controller_sends_stage2_ack(self) -> None:
        owner = _LiveOwner()
        lane = owner._lane_states[0]
        lane["play_sync_sent_count"] = 37
        lane["play_sync_local_id"] = 541

        RbUdpPlayStageController(owner).maybe_send_play_stage_controls(
            lane, remote_id=52519
        )

        _lane, meta = owner.control[0]
        assert meta["status_word"] == owner.CONTROL_PLAY_SYNC_STAGE2_STATUS
        assert meta["local_id"] == 541
        assert meta["remote_id"] == 52519
        assert meta["log_label"] == "send_control_play_stage2_ack"
        assert not meta["update_lane"]

    def test_probe_sender_builds_first_play_probe_and_advances_stage(
        self,
    ) -> None:
        owner = _LiveOwner()
        lane = owner._lane_states[0]
        lane["play_sync_sent_count"] = 18
        lane["play_sync_local_id"] = 541
        original_word4 = int(lane["word4"])

        RbUdpPlayProbeSender(owner).maybe_send_play_probe(
            lane, remote_id=26061
        )

        assert lane["play_probe_stage"] == 1
        assert len(owner.sent_udp) == 1
        assert len(owner.refreshed) == 2
        assert original_word4 != int(lane["word4"])
        assert owner.debug[0][0] == "send_wrapped_play_probe"
