import unittest

from quii_helper.preview.fragments.fragment_summary_state import (
    active_fragmented_media_entry,
    active_fragmented_media_summary,
    fragmented_media_summary,
)
from quii_helper.preview.processing.packets.flow import (
    active_fragmented_media_summary as facade_active_summary,
)
from quii_helper.preview.processing.packets.flow import (
    fragmented_media_summary as facade_fragmented_summary,
)


class PreviewFragmentSummaryStateTests(unittest.TestCase):
    def test_active_fragmented_media_entry_shape(self) -> None:
        state = {
            "start_msg_index": 10,
            "source": "wrapped_quii",
            "fragments": 2,
            "expected_body_len": 10,
            "body": b"1234",
            "packet_type": 0xA0,
            "frame_tag": 0xE1,
            "frame_len": 99,
        }

        self.assertEqual(
            {
                "fragment_key": ("rb_data", 1, 2),
                "start_msg_index": 10,
                "source": "wrapped_quii",
                "fragments": 2,
                "expected_body_len": 10,
                "have_body_len": 4,
                "missing_body_len": 6,
                "packet_type": "0xa0",
                "frame_tag": "0xe1",
                "frame_len": 99,
            },
            active_fragmented_media_entry(("rb_data", 1, 2), state),
        )

    def test_active_fragmented_media_summary_returns_none_when_empty(
        self,
    ) -> None:
        self.assertIsNone(active_fragmented_media_summary({}))

    def test_fragmented_media_summary_combines_stats_and_active_state(
        self,
    ) -> None:
        states = {
            ("rb_data", 1, 2): {
                "expected_body_len": 5,
                "body": b"12",
            }
        }

        summary = fragmented_media_summary({"started": 1}, states)

        self.assertEqual(1, summary["started"])
        self.assertEqual(3, summary["active"][0]["missing_body_len"])

    def test_packet_flow_keeps_fragment_summary_compatibility_exports(
        self,
    ) -> None:
        self.assertIs(facade_active_summary, active_fragmented_media_summary)
        self.assertIs(facade_fragmented_summary, fragmented_media_summary)


if __name__ == "__main__":
    unittest.main()
