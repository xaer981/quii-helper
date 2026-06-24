import unittest

from quii_helper.preview.processing.packets.flow import (
    QUII_HEADER_SIZE,
    active_fragmented_media_summary,
    buffer_chained_packet,
    chained_packet_summary,
    chained_remainder_meta,
    decoded_needs_more_data,
    decoded_remainder,
    fragment_key,
    fragmented_media_summary,
    increment_packet_stat,
    is_short_quii_blob,
    packet_payload_context,
    prepend_buffered_packet_prefix,
    record_chained_remainder_split,
    should_stop_media_collection,
    should_stop_packet_processing,
)


class PreviewPacketFlowTests(unittest.TestCase):
    def test_packet_payload_context_normalizes_defaults_and_copies_meta(
        self,
    ) -> None:
        original_meta = {"src_id": 1}

        blob, source, meta = packet_payload_context(
            {"payload": bytearray(b"abc"), "meta": original_meta}
        )

        self.assertEqual(b"abc", blob)
        self.assertEqual("unknown", source)
        self.assertEqual(original_meta, meta)
        self.assertIsNot(original_meta, meta)

    def test_is_short_quii_blob_uses_header_size(self) -> None:
        self.assertTrue(is_short_quii_blob(b"x" * (QUII_HEADER_SIZE - 1)))
        self.assertFalse(is_short_quii_blob(b"x" * QUII_HEADER_SIZE))

    def test_fragment_key_prefers_rbudp_ids(self) -> None:
        self.assertEqual(
            ("rb_data", "src", "dst"),
            fragment_key(
                source="wrapped_quii",
                meta={"src_id": "src", "dest_id": "dst"},
            ),
        )

    def test_fragment_key_uses_remainder_source_when_available(self) -> None:
        self.assertEqual(
            ("remainder", 42),
            fragment_key(
                source="wrapped_quii",
                meta={"from_msg_index": 42},
            ),
        )

    def test_fragment_key_falls_back_to_source(self) -> None:
        self.assertEqual(
            ("global", "direct_quii_blob"),
            fragment_key(source="direct_quii_blob", meta={}),
        )

    def test_decoded_needs_more_data_uses_declared_body_size(self) -> None:
        self.assertTrue(
            decoded_needs_more_data(
                {"read_size": "100", "body_available": "99"}
            )
        )
        self.assertFalse(
            decoded_needs_more_data(
                {"read_size": "100", "body_available": "100"}
            )
        )
        self.assertFalse(
            decoded_needs_more_data(
                {"read_size": object(), "body_available": "100"}
            )
        )

    def test_decoded_remainder_returns_bytes_after_consumed_message(
        self,
    ) -> None:
        blob = b"x" * QUII_HEADER_SIZE + b"a" * 4 + b"tail"

        self.assertEqual(
            b"tail",
            decoded_remainder(
                {"plausible": True, "offset": 0, "read_size": 4},
                blob,
            ),
        )

    def test_decoded_remainder_ignores_implausible_or_complete_blobs(
        self,
    ) -> None:
        blob = b"x" * QUII_HEADER_SIZE + b"a" * 4

        self.assertEqual(
            b"",
            decoded_remainder(
                {"plausible": False, "offset": 0, "read_size": 4},
                blob,
            ),
        )
        self.assertEqual(
            b"",
            decoded_remainder(
                {"plausible": True, "offset": 0, "read_size": 4},
                blob,
            ),
        )

    def test_chained_packet_summary_includes_buffer_state(self) -> None:
        summary = chained_packet_summary(
            {"split_remainders": 2},
            {("global", "a"): b"123", ("global", "b"): b"45"},
        )

        self.assertEqual(2, summary["split_remainders"])
        self.assertEqual(2, summary["buffered_streams"])
        self.assertEqual(5, summary["buffered_bytes"])

    def test_increment_packet_stat_accumulates_values(self) -> None:
        stats = {"packets": 2}

        increment_packet_stat(stats, "packets", 3)
        increment_packet_stat(stats, "other")

        self.assertEqual(5, stats["packets"])
        self.assertEqual(1, stats["other"])

    def test_prepend_buffered_packet_prefix_consumes_pending_buffer(
        self,
    ) -> None:
        buffers = {("global", "a"): b"old"}
        stats = {}

        blob = prepend_buffered_packet_prefix(
            buffers,
            stats,
            ("global", "a"),
            b"new",
        )

        self.assertEqual(b"oldnew", blob)
        self.assertEqual({}, buffers)
        self.assertEqual(1, stats["buffered_prefixes"])
        self.assertEqual(3, stats["buffered_prefix_bytes"])

    def test_record_chained_remainder_split_updates_count_and_bytes(
        self,
    ) -> None:
        stats = {}

        record_chained_remainder_split(stats, remainder_len=9)

        self.assertEqual(1, stats["split_remainders"])
        self.assertEqual(9, stats["split_remainder_bytes"])

    def test_buffer_chained_packet_records_reason_stats(self) -> None:
        buffers = {}
        stats = {}

        buffer_chained_packet(
            buffers,
            stats,
            ("global", "a"),
            b"123",
            reason="short_header",
        )

        self.assertEqual({("global", "a"): b"123"}, buffers)
        self.assertEqual(1, stats["buffered_packets"])
        self.assertEqual(3, stats["buffered_packet_bytes"])
        self.assertEqual(1, stats["buffered_short_header"])

    def test_chained_remainder_meta_preserves_original_values(self) -> None:
        meta = chained_remainder_meta(
            {"src_id": 1},
            message_index=10,
            chain_index=2,
            remainder_len=99,
        )

        self.assertEqual(1, meta["src_id"])
        self.assertEqual(10, meta["from_chained_msg_index"])
        self.assertEqual(2, meta["chained_packet"])
        self.assertEqual(99, meta["remainder_len"])

    def test_should_stop_packet_processing_only_stops_live_phase(self) -> None:
        self.assertTrue(
            should_stop_packet_processing(phase="live", stop_media=True)
        )
        self.assertFalse(
            should_stop_packet_processing(phase="flush", stop_media=True)
        )
        self.assertFalse(
            should_stop_packet_processing(phase="live", stop_media=False)
        )

    def test_should_stop_media_collection_matches_existing_thresholds(
        self,
    ) -> None:
        self.assertTrue(
            should_stop_media_collection(
                media_message_count=10,
                min_media_messages=2,
                max_media_messages=10,
                decodable_h264_context=False,
            )
        )
        self.assertFalse(
            should_stop_media_collection(
                media_message_count=1,
                min_media_messages=2,
                max_media_messages=10,
                decodable_h264_context=True,
            )
        )
        self.assertTrue(
            should_stop_media_collection(
                media_message_count=2,
                min_media_messages=2,
                max_media_messages=10,
                decodable_h264_context=True,
            )
        )
        self.assertFalse(
            should_stop_media_collection(
                media_message_count=2,
                min_media_messages=2,
                max_media_messages=10,
                decodable_h264_context=False,
            )
        )

    def test_fragmented_media_summary_describes_active_states(self) -> None:
        states = {
            ("rb_data", 1, 2): {
                "start_msg_index": 10,
                "source": "wrapped_quii",
                "fragments": 2,
                "expected_body_len": 10,
                "body": b"1234",
                "packet_type": 0xA0,
                "frame_tag": 0xE1,
                "frame_len": 99,
            }
        }

        active = active_fragmented_media_summary(states)
        summary = fragmented_media_summary({"started": 1}, states)

        self.assertEqual(active, summary["active"])
        self.assertEqual(1, summary["started"])
        self.assertEqual(6, summary["active"][0]["missing_body_len"])
        self.assertEqual("0xa0", summary["active"][0]["packet_type"])
        self.assertEqual("0xe1", summary["active"][0]["frame_tag"])


if __name__ == "__main__":
    unittest.main()
