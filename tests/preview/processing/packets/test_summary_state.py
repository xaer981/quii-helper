from quii_helper.preview.processing.packets.summary_state import (
    media_frame_summary_fields,
)


def frame(tag: int) -> dict:
    return {
        "frame_tag": tag,
        "frame_len": 42,
        "frame_stamp": 123,
        "width": 960,
        "height": 576,
    }


class PreviewPacketSummaryStateTests:
    def test_media_frame_summary_fields_returns_none_without_frames(
        self,
    ) -> None:
        assert media_frame_summary_fields({}) is None
        assert media_frame_summary_fields({"media_frames": "bad"}) is None

    def test_media_frame_summary_fields_preserves_single_frame_shape(
        self,
    ) -> None:
        assert {
            "media_frame_count": 1,
            "frame_tag": "0xe1",
            "frame_len": 42,
            "frame_stamp": 123,
            "width": 960,
            "height": 576,
        } == (media_frame_summary_fields({"media_frame": frame(0xE1)}))

    def test_media_frame_summary_fields_uses_first_valid_media_frame(
        self,
    ) -> None:
        assert "0xe0" == (
            media_frame_summary_fields({"media_frames": ["bad", frame(0xE0)]})[
                "frame_tag"
            ]
        )

    def test_media_frame_summary_fields_preserves_multi_frame_tags(
        self,
    ) -> None:
        fields = media_frame_summary_fields(
            {"media_frames": [frame(0xE1), frame(0xE0)]}
        )

        assert fields is not None
        assert 2 == fields["media_frame_count"]
        assert "0xe1" == fields["frame_tag"]
        assert ["0xe1", "0xe0"] == fields["frame_tags"]
