from quii_helper.protocols.rbudp.live.play_sync_state import (
    advance_play_sync_counter,
    decrement_play_sync_remaining,
    is_play_sync_exhausted,
    normalize_play_sync_iterations,
    should_log_play_sync_ack,
)


class RbUdpPlaySyncStateTests:
    def test_normalize_play_sync_iterations_clamps_negative_values(
        self,
    ) -> None:
        assert 0 == normalize_play_sync_iterations(None)
        assert 0 == normalize_play_sync_iterations(-5)
        assert 7 == normalize_play_sync_iterations("7")

    def test_is_play_sync_exhausted_requires_configured_iterations(
        self,
    ) -> None:
        assert not is_play_sync_exhausted(
            configured_iterations=0,
            remaining=0,
        )
        assert not is_play_sync_exhausted(
            configured_iterations=10,
            remaining=1,
        )
        assert is_play_sync_exhausted(
            configured_iterations=10,
            remaining=0,
        )

    def test_should_log_play_sync_ack_keeps_native_stage_counts(self) -> None:
        assert should_log_play_sync_ack(0)
        assert should_log_play_sync_ack(7)
        assert not should_log_play_sync_ack(8)
        assert should_log_play_sync_ack(37)
        assert should_log_play_sync_ack(68)
        assert should_log_play_sync_ack(200)
        assert not should_log_play_sync_ack(201)

    def test_advance_play_sync_counter_wraps_at_uint32_boundary(self) -> None:
        assert 3 == advance_play_sync_counter(0xFFFFFFFE, 5)

    def test_decrement_play_sync_remaining_stops_at_zero(self) -> None:
        assert 2 == decrement_play_sync_remaining(3)
        assert 0 == decrement_play_sync_remaining(1)
        assert 0 == decrement_play_sync_remaining(0)
