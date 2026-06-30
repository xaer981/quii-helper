from quii_helper.preview.processing.packets.capture_stats import CaptureStats


def _decoded(*, plausible: bool = True, media_frame: dict | None = None):
    decoded = {"plausible": plausible}
    if media_frame is not None:
        decoded["media_frame"] = media_frame
    return decoded


class CaptureStatsTests:
    def test_record_processed_packet_appends_plausible_messages(self) -> None:
        stats = CaptureStats()
        decoded = _decoded(plausible=True)

        stats.record_processed_packet(
            summary={},
            decoded=decoded,
            phase="live",
        )

        assert [decoded] == stats.decoded_messages
        assert [] == stats.media_messages

    def test_record_processed_packet_suppresses_implausible_messages(
        self,
    ) -> None:
        stats = CaptureStats()

        stats.record_processed_packet(
            summary={},
            decoded=_decoded(plausible=False),
            phase="live",
        )

        assert [] == stats.decoded_messages
        assert [] == stats.media_messages

    def test_record_processed_packet_appends_live_media_and_summary_fields(
        self,
    ) -> None:
        stats = CaptureStats()
        decoded = _decoded(
            media_frame={
                "frame_tag": 0xE1,
                "frame_len": 42,
                "frame_stamp": 123,
                "width": 960,
                "height": 576,
            }
        )
        summary = {}

        stats.record_processed_packet(
            summary=summary,
            decoded=decoded,
            phase="live",
        )

        assert [decoded] == stats.decoded_messages
        assert [decoded] == stats.media_messages
        assert "0xe1" == summary["frame_tag"]
        assert 42 == summary["frame_len"]

    def test_record_processed_packet_can_stream_without_storing_media(
        self,
    ) -> None:
        streamed = []
        stats = CaptureStats(
            media_message_sink=streamed.append,
            store_media_messages=False,
        )
        decoded = _decoded(
            media_frame={
                "frame_tag": 0xE1,
                "frame_len": 42,
                "frame_stamp": 123,
                "width": 960,
                "height": 576,
            }
        )

        stats.record_processed_packet(
            summary={},
            decoded=decoded,
            phase="live",
        )

        assert [decoded] == stats.decoded_messages
        assert [] == stats.media_messages
        assert [decoded] == streamed

    def test_record_processed_packet_does_not_append_flush_media(self) -> None:
        stats = CaptureStats()
        decoded = _decoded(
            media_frame={
                "frame_tag": 0xE1,
                "frame_len": 42,
                "frame_stamp": 123,
                "width": 960,
                "height": 576,
            }
        )
        summary = {}

        stats.record_processed_packet(
            summary=summary,
            decoded=decoded,
            phase="flush",
        )

        assert [decoded] == stats.decoded_messages
        assert [] == stats.media_messages
        assert "frame_tag" not in summary
