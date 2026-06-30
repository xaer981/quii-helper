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


class PreviewPacketFlowTests:
    def test_packet_payload_context_normalizes_defaults_and_copies_meta(
        self,
    ) -> None:
        original_meta = {"src_id": 1}

        blob, source, meta = packet_payload_context(
            {"payload": bytearray(b"abc"), "meta": original_meta}
        )

        assert b"abc" == blob
        assert "unknown" == source
        assert original_meta == meta
        assert original_meta is not meta

    def test_is_short_quii_blob_uses_header_size(self) -> None:
        assert is_short_quii_blob(b"x" * (QUII_HEADER_SIZE - 1))
        assert not is_short_quii_blob(b"x" * QUII_HEADER_SIZE)

    def test_fragment_key_prefers_rbudp_ids(self) -> None:
        assert ("rb_data", "src", "dst") == (
            fragment_key(
                source="wrapped_quii",
                meta={"src_id": "src", "dest_id": "dst"},
            )
        )

    def test_fragment_key_uses_remainder_source_when_available(self) -> None:
        assert ("remainder", 42) == (
            fragment_key(
                source="wrapped_quii",
                meta={"from_msg_index": 42},
            )
        )

    def test_fragment_key_falls_back_to_source(self) -> None:
        assert ("global", "direct_quii_blob") == (
            fragment_key(source="direct_quii_blob", meta={})
        )

    def test_decoded_needs_more_data_uses_declared_body_size(self) -> None:
        assert decoded_needs_more_data(
            {"read_size": "100", "body_available": "99"}
        )
        assert not decoded_needs_more_data(
            {"read_size": "100", "body_available": "100"}
        )
        assert not decoded_needs_more_data(
            {"read_size": object(), "body_available": "100"}
        )

    def test_decoded_remainder_returns_bytes_after_consumed_message(
        self,
    ) -> None:
        blob = b"x" * QUII_HEADER_SIZE + b"a" * 4 + b"tail"

        assert b"tail" == (
            decoded_remainder(
                {"plausible": True, "offset": 0, "read_size": 4},
                blob,
            )
        )

    def test_decoded_remainder_ignores_implausible_or_complete_blobs(
        self,
    ) -> None:
        blob = b"x" * QUII_HEADER_SIZE + b"a" * 4

        assert b"" == (
            decoded_remainder(
                {"plausible": False, "offset": 0, "read_size": 4},
                blob,
            )
        )
        assert b"" == (
            decoded_remainder(
                {"plausible": True, "offset": 0, "read_size": 4},
                blob,
            )
        )

    def test_chained_packet_summary_includes_buffer_state(self) -> None:
        summary = chained_packet_summary(
            {"split_remainders": 2},
            {("global", "a"): b"123", ("global", "b"): b"45"},
        )

        assert 2 == summary["split_remainders"]
        assert 2 == summary["buffered_streams"]
        assert 5 == summary["buffered_bytes"]

    def test_increment_packet_stat_accumulates_values(self) -> None:
        stats = {"packets": 2}

        increment_packet_stat(stats, "packets", 3)
        increment_packet_stat(stats, "other")

        assert 5 == stats["packets"]
        assert 1 == stats["other"]

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

        assert b"oldnew" == blob
        assert {} == buffers
        assert 1 == stats["buffered_prefixes"]
        assert 3 == stats["buffered_prefix_bytes"]

    def test_record_chained_remainder_split_updates_count_and_bytes(
        self,
    ) -> None:
        stats = {}

        record_chained_remainder_split(stats, remainder_len=9)

        assert 1 == stats["split_remainders"]
        assert 9 == stats["split_remainder_bytes"]

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

        assert {("global", "a"): b"123"} == buffers
        assert 1 == stats["buffered_packets"]
        assert 3 == stats["buffered_packet_bytes"]
        assert 1 == stats["buffered_short_header"]

    def test_chained_remainder_meta_preserves_original_values(self) -> None:
        meta = chained_remainder_meta(
            {"src_id": 1},
            message_index=10,
            chain_index=2,
            remainder_len=99,
        )

        assert 1 == meta["src_id"]
        assert 10 == meta["from_chained_msg_index"]
        assert 2 == meta["chained_packet"]
        assert 99 == meta["remainder_len"]

    def test_should_stop_packet_processing_only_stops_live_phase(self) -> None:
        assert should_stop_packet_processing(phase="live", stop_media=True)
        assert not should_stop_packet_processing(
            phase="flush", stop_media=True
        )
        assert not should_stop_packet_processing(
            phase="live", stop_media=False
        )

    def test_should_stop_media_collection_matches_existing_thresholds(
        self,
    ) -> None:
        assert should_stop_media_collection(
            media_message_count=10,
            min_media_messages=2,
            max_media_messages=10,
            decodable_h264_context=False,
        )
        assert not should_stop_media_collection(
            media_message_count=1,
            min_media_messages=2,
            max_media_messages=10,
            decodable_h264_context=True,
        )
        assert should_stop_media_collection(
            media_message_count=2,
            min_media_messages=2,
            max_media_messages=10,
            decodable_h264_context=True,
        )
        assert not should_stop_media_collection(
            media_message_count=2,
            min_media_messages=2,
            max_media_messages=10,
            decodable_h264_context=False,
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

        assert active == summary["active"]
        assert 1 == summary["started"]
        assert 6 == summary["active"][0]["missing_body_len"]
        assert "0xa0" == summary["active"][0]["packet_type"]
        assert "0xe1" == summary["active"][0]["frame_tag"]
