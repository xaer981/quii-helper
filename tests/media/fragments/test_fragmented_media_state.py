from types import SimpleNamespace

from quii_helper.media.fragments.state import (
    append_fragmented_media_body,
    build_fragmented_media_state,
    complete_fragmented_blob,
    fragmented_media_append_summary,
    fragmented_media_decode_meta,
    fragmented_media_lengths,
)


class MediaFragmentedMediaStateTests:
    def test_fragmented_media_lengths_derive_body_and_media_lengths(
        self,
    ) -> None:
        decoded = {
            "read_size": "20",
            "media_payload_offset": "8",
            "payload_raw": b"12345",
        }

        assert (20, 12, 5) == fragmented_media_lengths(decoded)

    def test_build_fragmented_media_state_preserves_decoded_fields(
        self,
    ) -> None:
        decoded = {
            "header": SimpleNamespace(
                packet_type=0xA0,
                payload_size=30,
                raw_size=40,
                flag15=1,
            ),
            "header_raw": b"head",
            "payload_raw": b"payload",
            "payload": b"\x00\x00\x00\xe1\x10\x00\x00\x00",
            "read_size": 20,
            "media_payload_offset": 8,
        }

        state = build_fragmented_media_state(
            decoded,
            source="wrapped_quii",
            meta={"lane": 1},
            message_index=7,
        )

        assert b"head" == state["header_raw"]
        assert bytearray(b"payload") == state["body"]
        assert 20 == state["expected_body_len"]
        assert 7 == state["start_msg_index"]
        assert "wrapped_quii" == state["source"]
        assert {"lane": 1} == state["meta"]
        assert 0xA0 == state["packet_type"]
        assert 30 == state["payload_size"]
        assert 40 == state["raw_size"]
        assert 1 == state["flag15"]
        assert 8 == state["media_payload_offset"]
        assert 0xE1 == state["frame_tag"]
        assert 16 == state["frame_len"]
        assert 1 == state["fragments"]

    def test_append_fragmented_media_body_updates_state_until_complete(
        self,
    ) -> None:
        state = {
            "body": bytearray(b"1234"),
            "expected_body_len": 8,
            "fragments": 1,
        }

        take, complete, expected_body_len = append_fragmented_media_body(
            state, b"567890"
        )

        assert 4 == take
        assert complete
        assert 8 == expected_body_len
        assert bytearray(b"12345678") == state["body"]
        assert 2 == state["fragments"]

    def test_fragmented_media_append_summary_shape(self) -> None:
        state = {
            "body": bytearray(b"123456"),
            "start_msg_index": 2,
            "fragments": 3,
            "packet_type": 0xA0,
            "raw_size": 80,
            "frame_tag": 0xE1,
            "frame_len": 64,
        }

        summary = fragmented_media_append_summary(
            state,
            b"abcdef",
            source="wrapped_quii",
            meta={"src": "0x1"},
            message_index=9,
            take=4,
            complete=False,
            expected_body_len=10,
        )

        assert 9 == summary["msg_index"]
        assert "wrapped_quii" == summary["source"]
        assert 6 == summary["blob_len"]
        assert "append" == summary["fragmented_media"]
        assert 2 == summary["start_msg_index"]
        assert 3 == summary["fragments"]
        assert 10 == summary["expected_body_len"]
        assert 6 == summary["have_body_len"]
        assert 4 == summary["taken_len"]
        assert 2 == summary["remainder_len"]
        assert "0xa0" == summary["packet_type"]
        assert 80 == summary["raw_size"]
        assert "0xe1" == summary["frame_tag"]
        assert 64 == summary["frame_len"]
        assert {"src": "0x1"} == summary["meta"]

    def test_complete_blob_and_decode_meta_shapes(self) -> None:
        state = {
            "header_raw": b"head",
            "body": bytearray(b"123456"),
            "start_msg_index": 3,
            "fragments": 2,
        }

        assert b"head1234" == complete_fragmented_blob(state, 4)
        assert {
            "start_msg_index": 3,
            "end_msg_index": 8,
            "fragments": 2,
            "expected_body_len": 4,
        } == (
            fragmented_media_decode_meta(
                state, message_index=8, expected_body_len=4
            )
        )
