import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from quii_helper.preview.outputs.writer.output_writer import (
    PreviewOutputWriter,
)


class PreviewOutputWriterTests(unittest.TestCase):
    def test_write_capture_outputs_routes_diagnostic_probe_summaries(
        self,
    ) -> None:
        collector = SimpleNamespace(
            container_probe_candidates=[b"container"],
            cpacket_candidates=[b"cpacket"],
            embedded_h264_candidates=[],
        )

        with tempfile.TemporaryDirectory() as tmp:
            writer = PreviewOutputWriter(
                diagnostics_enabled=True,
                data_dir=tmp,
                output_base="clip",
                render_snapshot=False,
                render_video=False,
            )
            with (
                patch(
                    "quii_helper.preview.outputs.writer.output_writer."
                    "write_container_probe_summary",
                    return_value={"container": True},
                ) as container_probe,
                patch(
                    "quii_helper.preview.outputs.writer.output_writer."
                    "write_cpacket_probe_summary",
                    return_value={"cpacket": True},
                ) as cpacket_probe,
            ):
                artifacts = writer.write_capture_outputs(
                    decoded_messages=[],
                    fragment_partial_collector=collector,
                )

        self.assertIsNone(artifacts.media_result)
        self.assertIsNone(artifacts.embedded_fallback)
        self.assertEqual(
            {"container": True},
            artifacts.container_probe_summary,
        )
        self.assertEqual({"cpacket": True}, artifacts.cpacket_probe_summary)
        container_probe.assert_called_once()
        cpacket_probe.assert_called_once()

    def test_write_capture_outputs_skips_probe_summaries_without_diagnostics(
        self,
    ) -> None:
        collector = SimpleNamespace(
            container_probe_candidates=[b"container"],
            cpacket_candidates=[b"cpacket"],
            embedded_h264_candidates=[],
        )

        with tempfile.TemporaryDirectory() as tmp:
            writer = PreviewOutputWriter(
                diagnostics_enabled=False,
                data_dir=tmp,
                output_base="clip",
                render_snapshot=False,
                render_video=False,
            )
            with (
                patch(
                    "quii_helper.preview.outputs.writer.output_writer."
                    "write_container_probe_summary"
                ) as container_probe,
                patch(
                    "quii_helper.preview.outputs.writer.output_writer."
                    "write_cpacket_probe_summary"
                ) as cpacket_probe,
            ):
                artifacts = writer.write_capture_outputs(
                    decoded_messages=[],
                    fragment_partial_collector=collector,
                )

        self.assertIsNone(artifacts.container_probe_summary)
        self.assertIsNone(artifacts.cpacket_probe_summary)
        container_probe.assert_not_called()
        cpacket_probe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
