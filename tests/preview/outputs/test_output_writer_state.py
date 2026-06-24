import tempfile
import unittest
from pathlib import Path

from quii_helper.io.paths import resolve_data_dir
from quii_helper.preview.outputs.writer.output_writer import CaptureArtifacts
from quii_helper.preview.outputs.writer.state import (
    capture_artifacts,
    media_result_has_assembled_units,
    resolve_preview_output_base,
    should_write_diagnostic_candidates,
    should_write_embedded_fallback,
)


class PreviewOutputWriterStateTests(unittest.TestCase):
    def test_capture_artifacts_preserves_result_fields(self) -> None:
        artifacts = capture_artifacts(
            media_result={"mp4": True},
            embedded_fallback={"h264": True},
            container_probe_summary={"container": True},
            cpacket_probe_summary={"cpacket": True},
            artifacts_cls=CaptureArtifacts,
        )

        self.assertEqual({"mp4": True}, artifacts.media_result)
        self.assertEqual({"h264": True}, artifacts.embedded_fallback)
        self.assertEqual(
            {"container": True},
            artifacts.container_probe_summary,
        )
        self.assertEqual({"cpacket": True}, artifacts.cpacket_probe_summary)

    def test_resolve_preview_output_base_allocates_timestamp_when_missing(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = resolve_preview_output_base(None, tmp)

            self.assertEqual(resolve_data_dir(tmp), base.parent)
            self.assertFalse(base.suffix)

    def test_resolve_preview_output_base_strips_suffix_and_keeps_data_dir(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = resolve_preview_output_base("clip.mp4", tmp)

            self.assertEqual(Path("clip"), Path(base.name))
            self.assertFalse(base.suffix)

    def test_resolve_preview_output_base_normalizes_nested_relative_path(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = resolve_preview_output_base("nested/clip.jpg", tmp)

            self.assertEqual("clip", base.name)
            self.assertEqual("nested", base.parent.name)

    def test_should_write_diagnostic_candidates_requires_flag_and_candidates(
        self,
    ) -> None:
        self.assertFalse(
            should_write_diagnostic_candidates(
                diagnostics_enabled=False,
                candidates=[b"probe"],
            )
        )
        self.assertFalse(
            should_write_diagnostic_candidates(
                diagnostics_enabled=True,
                candidates=[],
            )
        )
        self.assertTrue(
            should_write_diagnostic_candidates(
                diagnostics_enabled=True,
                candidates=[b"probe"],
            )
        )

    def test_media_result_has_assembled_units_matches_existing_semantics(
        self,
    ) -> None:
        self.assertFalse(media_result_has_assembled_units(None))
        self.assertFalse(media_result_has_assembled_units({}))
        self.assertFalse(
            media_result_has_assembled_units(
                {"summary": {"assembled_units": 0}}
            )
        )
        self.assertTrue(
            media_result_has_assembled_units(
                {"summary": {"assembled_units": 1}}
            )
        )

    def test_embedded_fallback_is_skipped_for_existing_assembled_media(
        self,
    ) -> None:
        self.assertFalse(
            should_write_embedded_fallback(
                diagnostics_enabled=False,
                embedded_h264_candidates=[b"h264"],
                media_result=None,
            )
        )
        self.assertFalse(
            should_write_embedded_fallback(
                diagnostics_enabled=True,
                embedded_h264_candidates=[],
                media_result=None,
            )
        )
        self.assertFalse(
            should_write_embedded_fallback(
                diagnostics_enabled=True,
                embedded_h264_candidates=[b"h264"],
                media_result={"summary": {"assembled_units": 1}},
            )
        )
        self.assertTrue(
            should_write_embedded_fallback(
                diagnostics_enabled=True,
                embedded_h264_candidates=[b"h264"],
                media_result={"summary": {"assembled_units": 0}},
            )
        )


if __name__ == "__main__":
    unittest.main()
