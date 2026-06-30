from types import SimpleNamespace

from quii_helper.preview.pipeline.config import PreviewCaptureSettings
from quii_helper.preview.summaries.capture_summary_state import (
    capture_settings_summary,
    common_capture_summary_fields,
)


class PreviewCaptureSummaryStateTests:
    def test_capture_settings_summary_preserves_existing_fields(self) -> None:
        settings = PreviewCaptureSettings(
            capture_seconds=10.0,
            stop_when_decodable=True,
            pending_quii_drain_seconds=2.0,
        )
        tunnel_config = SimpleNamespace(
            live_play_payload="path",
            stream=2,
            live_inner=True,
            live_newcn=False,
            play_sync_iterations=4,
        )

        assert {
            "capture_seconds": 10.0,
            "stop_when_decodable": True,
            "elapsed_seconds": 1.235,
            "live_play_payload": "path",
            "stream": 2,
            "live_inner": True,
            "live_newcn": False,
            "play_sync_iterations": 4,
            "pending_quii_drain_seconds": 2.0,
            "pending_quii_drain_packets": 7,
            "pending_quii_drain_elapsed_seconds": 8.988,
        } == (
            capture_settings_summary(
                preview_settings=settings,
                elapsed_seconds=1.23456,
                tunnel_config=tunnel_config,
                pending_quii_drain_packets=7,
                pending_quii_drain_elapsed_seconds=8.98765,
            )
        )

    def test_capture_settings_summary_uses_tunnel_defaults(self) -> None:
        settings = PreviewCaptureSettings()

        summary = capture_settings_summary(
            preview_settings=settings,
            elapsed_seconds=0.0,
            tunnel_config=SimpleNamespace(),
            pending_quii_drain_packets=0,
            pending_quii_drain_elapsed_seconds=0.0,
        )

        assert "" == summary["live_play_payload"]
        assert 0 == summary["stream"]
        assert not summary["live_inner"]
        assert not summary["live_newcn"]
        assert 0 == summary["play_sync_iterations"]

    def test_common_capture_summary_fields_preserves_existing_shape(
        self,
    ) -> None:
        fields = common_capture_summary_fields(
            capture_settings={"capture_seconds": 1.0},
            play_sync=[{"active": False}],
            rbudp_fragments={"started": 0},
            fragmented_media={"active": None},
            quii_packet_chaining={"buffered_streams": 0},
            media_collection={"media_messages": 1},
            implausible_direct_suppressed=2,
            stream_payload_count=3,
            stream_payload_filler_count=4,
            diagnostic_artifacts_saved=True,
            container_probe_summary={"containers": 1},
            cpacket_probe_summary={"cpackets": 1},
        )

        assert {"capture_seconds": 1.0} == fields["capture_settings"]
        assert [{"active": False}] == fields["play_sync"]
        assert {"media_messages": 1} == fields["media_collection"]
        assert 2 == fields["implausible_direct_suppressed"]
        assert fields["diagnostic_artifacts_saved"]
        assert {"containers": 1} == fields["container_probe_summary"]
