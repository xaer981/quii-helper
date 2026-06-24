import unittest
from types import SimpleNamespace

from quii_helper.preview.outputs.writer.output_writer import CaptureArtifacts
from quii_helper.preview.pipeline.config import PreviewCaptureSettings
from quii_helper.preview.summaries.capture_summary import build_capture_summary


class PreviewCaptureSummaryTests(unittest.TestCase):
    def test_build_capture_summary_for_decoded_messages(self) -> None:
        settings = PreviewCaptureSettings(
            capture_seconds=10.0,
            stop_when_decodable=False,
            save_diagnostic_artifacts=True,
            pending_quii_drain_seconds=2.0,
        )
        summary = build_capture_summary(
            preview_settings=settings,
            capture_artifacts=CaptureArtifacts(
                media_result={"mp4": True},
                embedded_fallback=None,
                container_probe_summary={"containers": 1},
                cpacket_probe_summary={"cpackets": 1},
            ),
            decoded_messages=[{"id": 1}, {"id": 2}],
            media_messages=[{"id": "media"}],
            elapsed_seconds=1.23456,
            tunnel_config=SimpleNamespace(
                live_play_payload="path",
                stream=2,
                live_inner=False,
                live_newcn=True,
                play_sync_iterations=0,
            ),
            play_sync=[{"active": False}],
            rbudp_fragments={"started": 0},
            fragmented_media={"active": None},
            quii_packet_chaining={"buffered_streams": 0},
            implausible_direct_suppressed=3,
            stream_payload_count=4,
            stream_payload_filler_count=5,
            stream_payload_early_count=6,
            stream_payload_early_filler_count=7,
            pending_quii_drain_packets=8,
            pending_quii_drain_elapsed_seconds=1.98765,
        )

        self.assertEqual(2, summary["decoded_messages"])
        self.assertEqual(1, summary["media_messages"])
        self.assertEqual({"mp4": True}, summary["media_result"])
        self.assertNotIn("embedded_fallback", summary)
        self.assertEqual(1.235, summary["capture_settings"]["elapsed_seconds"])
        self.assertEqual(
            1.988,
            summary["capture_settings"]["pending_quii_drain_elapsed_seconds"],
        )
        self.assertTrue(summary["diagnostic_artifacts_saved"])
        self.assertEqual(3, summary["implausible_direct_suppressed"])

    def test_build_capture_summary_for_no_decoded_messages(self) -> None:
        summary = build_capture_summary(
            preview_settings=PreviewCaptureSettings(),
            capture_artifacts=CaptureArtifacts(
                media_result=None,
                embedded_fallback={"h264": True},
                container_probe_summary=None,
                cpacket_probe_summary=None,
            ),
            decoded_messages=[],
            media_messages=[],
            elapsed_seconds=0.0,
            tunnel_config=SimpleNamespace(),
            play_sync=[],
            rbudp_fragments={},
            fragmented_media={"active": None},
            quii_packet_chaining={"buffered_streams": 0},
            implausible_direct_suppressed=0,
            stream_payload_count=0,
            stream_payload_filler_count=1,
            stream_payload_early_count=2,
            stream_payload_early_filler_count=3,
            pending_quii_drain_packets=0,
            pending_quii_drain_elapsed_seconds=0.0,
        )

        self.assertEqual(0, summary["decoded_messages"])
        self.assertNotIn("media_messages", summary)
        self.assertEqual({"h264": True}, summary["embedded_fallback"])
        self.assertEqual(2, summary["stream_payload_early_count"])
        self.assertEqual(3, summary["stream_payload_early_filler_count"])


if __name__ == "__main__":
    unittest.main()
