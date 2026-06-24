import unittest

from quii_helper.protocols.rbudp.live.play_sync_state import (
    advance_play_sync_counter,
    decrement_play_sync_remaining,
    is_play_sync_exhausted,
    normalize_play_sync_iterations,
    should_log_play_sync_ack,
)


class RbUdpPlaySyncStateTests(unittest.TestCase):
    def test_normalize_play_sync_iterations_clamps_negative_values(
        self,
    ) -> None:
        self.assertEqual(0, normalize_play_sync_iterations(None))
        self.assertEqual(0, normalize_play_sync_iterations(-5))
        self.assertEqual(7, normalize_play_sync_iterations("7"))

    def test_is_play_sync_exhausted_requires_configured_iterations(
        self,
    ) -> None:
        self.assertFalse(
            is_play_sync_exhausted(
                configured_iterations=0,
                remaining=0,
            )
        )
        self.assertFalse(
            is_play_sync_exhausted(
                configured_iterations=10,
                remaining=1,
            )
        )
        self.assertTrue(
            is_play_sync_exhausted(
                configured_iterations=10,
                remaining=0,
            )
        )

    def test_should_log_play_sync_ack_keeps_native_stage_counts(self) -> None:
        self.assertTrue(should_log_play_sync_ack(0))
        self.assertTrue(should_log_play_sync_ack(7))
        self.assertFalse(should_log_play_sync_ack(8))
        self.assertTrue(should_log_play_sync_ack(37))
        self.assertTrue(should_log_play_sync_ack(68))
        self.assertTrue(should_log_play_sync_ack(200))
        self.assertFalse(should_log_play_sync_ack(201))

    def test_advance_play_sync_counter_wraps_at_uint32_boundary(self) -> None:
        self.assertEqual(3, advance_play_sync_counter(0xFFFFFFFE, 5))

    def test_decrement_play_sync_remaining_stops_at_zero(self) -> None:
        self.assertEqual(2, decrement_play_sync_remaining(3))
        self.assertEqual(0, decrement_play_sync_remaining(1))
        self.assertEqual(0, decrement_play_sync_remaining(0))


if __name__ == "__main__":
    unittest.main()
