from types import SimpleNamespace

from quii_helper.preview.fragments.fragment_flow_state import (
    drop_active_fragment_summary,
    fragment_remainder_meta,
    fragment_start_summary,
    has_decoded_media_frames,
    record_fragmented_media_decoded,
    short_fragment_remainder_summary,
)


class _FakeEmitter:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def emit_packet_summary(
        self, summary: dict, *, source: str, decoded: dict
    ) -> None:
        self.calls.append(
            {"summary": summary, "source": source, "decoded": decoded}
        )


def _decoded(*, plausible: bool = True, media_frame: dict | None = None):
    decoded = {
        "header": SimpleNamespace(
            packet_type=0xA0,
            payload_size=3,
            raw_size=3,
            flag15=0,
            flag16=0,
            flag17=0,
        ),
        "is_media": media_frame is not None,
        "plausible": plausible,
        "offset": 0,
        "payload": b"abc",
        "text_preview": "",
        "fragmented_media": {"fragments": 2},
    }
    if media_frame is not None:
        decoded["media_frame"] = media_frame
    return decoded


class PreviewFragmentFlowStateTests:
    def test_has_decoded_media_frames_accepts_list_or_single_frame(
        self,
    ) -> None:
        assert has_decoded_media_frames({"media_frames": [{}]})
        assert has_decoded_media_frames({"media_frame": {}})
        assert not has_decoded_media_frames({"media_frames": []})
        assert not has_decoded_media_frames({"media_frame": None})

    def test_fragment_remainder_meta_keeps_source_context(self) -> None:
        meta = fragment_remainder_meta(
            {"src_id": 1},
            message_index=20,
            remainder_len=33,
        )

        assert 1 == meta["src_id"]
        assert 20 == meta["from_msg_index"]
        assert 33 == meta["remainder_len"]

    def test_short_fragment_remainder_summary_shape(self) -> None:
        assert {
            "msg_index": 3,
            "source": "wrapped_quii_fragmented_remainder",
            "fragmented_media": "drop_short_remainder",
            "blob_len": 12,
        } == (
            short_fragment_remainder_summary(
                message_index=3,
                source="wrapped_quii_fragmented_remainder",
                blob_len=12,
            )
        )

    def test_fragment_start_summary_shape(self) -> None:
        state = {
            "expected_body_len": 100,
            "body": bytearray(b"123"),
            "packet_type": 0xA0,
            "raw_size": 80,
            "frame_tag": 0xE1,
            "frame_len": 60,
        }

        summary = fragment_start_summary(
            message_index=7,
            source="wrapped_quii",
            blob_len=44,
            fragment_key=("rb_data", 1, 2),
            state=state,
            meta={"src_id": 1},
        )

        assert 7 == summary["msg_index"]
        assert "wrapped_quii" == summary["source"]
        assert 44 == summary["blob_len"]
        assert "start" == summary["fragmented_media"]
        assert ("rb_data", 1, 2) == summary["fragment_key"]
        assert 100 == summary["expected_body_len"]
        assert 3 == summary["have_body_len"]
        assert "0xa0" == summary["packet_type"]
        assert 80 == summary["raw_size"]
        assert "0xe1" == summary["frame_tag"]
        assert 60 == summary["frame_len"]
        assert {"src_id": 1} == summary["meta"]

    def test_drop_active_fragment_summary_reports_missing_bytes(self) -> None:
        state = {
            "expected_body_len": 10,
            "body": bytearray(b"1234"),
            "start_msg_index": 1,
            "source": "wrapped_quii",
            "fragments": 2,
        }

        summary = drop_active_fragment_summary(
            message_index=5,
            source="wrapped_quii",
            blob_len=20,
            reason="interleaved_media_header",
            fragment_key=("rb_data", 1, 2),
            state=state,
            meta={"lane": 1},
        )

        assert "drop_active" == summary["fragmented_media"]
        assert "interleaved_media_header" == summary["reason"]
        assert 1 == summary["start_msg_index"]
        assert "wrapped_quii" == summary["state_source"]
        assert 2 == summary["fragments"]
        assert 10 == summary["expected_body_len"]
        assert 4 == summary["have_body_len"]
        assert 6 == summary["missing_body_len"]
        assert {"lane": 1} == summary["meta"]

    def test_record_fragmented_media_decoded_records_summary_and_media(
        self,
    ) -> None:
        decoded_messages = []
        media_messages = []
        emitter = _FakeEmitter()
        decoded = _decoded(
            media_frame={
                "frame_tag": 0xE1,
                "frame_len": 42,
                "frame_stamp": 123,
                "width": 960,
                "height": 576,
            }
        )

        record_fragmented_media_decoded(
            decoded_messages=decoded_messages,
            media_messages=media_messages,
            summary_emitter=emitter,
            decoded=decoded,
            message_index=9,
            blob_len=64,
            source="wrapped_quii_fragmented_media",
            meta={"src_id": "0x1"},
        )

        assert [decoded] == decoded_messages
        assert [decoded] == media_messages
        assert 1 == len(emitter.calls)
        summary = emitter.calls[0]["summary"]
        assert 9 == summary["msg_index"]
        assert "wrapped_quii_fragmented_media" == summary["source"]
        assert 64 == summary["blob_len"]
        assert {"src_id": "0x1"} == summary["meta"]
        assert {"fragments": 2} == summary["fragmented_media"]
        assert "0xe1" == summary["frame_tag"]
        assert 42 == summary["frame_len"]

    def test_record_fragmented_media_decoded_can_stream_without_storing(
        self,
    ) -> None:
        decoded_messages = []
        media_messages = []
        streamed = []
        emitter = _FakeEmitter()
        decoded = _decoded(
            media_frame={
                "frame_tag": 0xE1,
                "frame_len": 42,
                "frame_stamp": 123,
                "width": 960,
                "height": 576,
            }
        )

        record_fragmented_media_decoded(
            decoded_messages=decoded_messages,
            media_messages=media_messages,
            summary_emitter=emitter,
            decoded=decoded,
            message_index=9,
            blob_len=64,
            source="wrapped_quii_fragmented_media",
            meta={"src_id": "0x1"},
            media_message_sink=streamed.append,
            store_media_messages=False,
        )

        assert [decoded] == decoded_messages
        assert [] == media_messages
        assert [decoded] == streamed

    def test_record_fragmented_media_decoded_suppresses_implausible_append(
        self,
    ) -> None:
        decoded_messages = []
        media_messages = []
        emitter = _FakeEmitter()
        decoded = _decoded(plausible=False)

        record_fragmented_media_decoded(
            decoded_messages=decoded_messages,
            media_messages=media_messages,
            summary_emitter=emitter,
            decoded=decoded,
            message_index=9,
            blob_len=64,
            source="wrapped_quii_fragmented_media",
            meta={},
        )

        assert [] == decoded_messages
        assert [] == media_messages
        assert 1 == len(emitter.calls)
