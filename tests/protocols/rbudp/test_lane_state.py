from quii_helper.protocols.rbudp.lanes.registry import RbUdpLaneRegistry
from quii_helper.protocols.rbudp.lanes.state import RbUdpLaneState


class RbUdpLaneStateTests:
    def _state(self) -> tuple[RbUdpLaneState, list[tuple[str, dict]]]:
        debug: list[tuple[str, dict]] = []
        registry = RbUdpLaneRegistry.create(
            src_ids=[0x4000006, 0x4000007],
            bootstrap_word4=0,
            bootstrap_remote_id=1,
            bootstrap_local_ids=[0, 1],
        )
        state = RbUdpLaneState(
            lane_registry=registry,
            src_id=0x4000006,
            src_ids=[0x4000006, 0x4000007],
            debug=lambda message, **kwargs: debug.append((message, kwargs)),
        )
        return state, debug

    def test_next_lane_nonce_returns_current_and_increments(self) -> None:
        state, _debug = self._state()
        lane = state.active_lane()
        lane["nonce"] = 0xFFFF

        assert 0xFFFF == state.next_lane_nonce(lane)
        assert 0x10000 == lane["nonce"]

    def test_refresh_lane_word4_updates_peer_word8_and_logs(self) -> None:
        state, debug = self._state()
        lane = state.active_lane()

        state.refresh_lane_word4(lane, target_word4=0x3D000022)

        assert 0x3D000022 == lane["word4"]
        assert 0x3D000022 == lane["peer_word8"]
        assert "refresh_lane_word4" == debug[0][0]

    def test_late_family_target_word4_uses_src_id_offset(self) -> None:
        state, _debug = self._state()
        second = state.lane_for_src_id(0x4000007)
        assert second is not None

        assert 0x3E000023 == state.late_family_target_word4(second)
