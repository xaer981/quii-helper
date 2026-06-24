import hashlib
import unittest
from pathlib import Path

from quii_helper.preview.fragments.embedded_h264_state import (
    embedded_h264_paths,
    embedded_h264_result_payload,
    empty_embedded_h264_result,
    should_write_persistent_embedded,
)


class PreviewEmbeddedH264StateTests(unittest.TestCase):
    def test_embedded_h264_paths_preserve_filename_shape(self) -> None:
        paths = embedded_h264_paths("sample")

        self.assertEqual("sample_embedded.h264", paths["stream_path"].name)
        self.assertEqual("sample_embedded.mp4", paths["mp4_path"].name)
        self.assertEqual("sample_embedded.jpg", paths["snapshot_path"].name)
        self.assertEqual(
            "sample_embedded_best.h264",
            paths["persistent_path"].name,
        )

    def test_should_write_persistent_embedded_skips_false_positive_sps(
        self,
    ) -> None:
        self.assertFalse(
            should_write_persistent_embedded({"false_positive_sps_only": True})
        )
        self.assertTrue(should_write_persistent_embedded({}))

    def test_empty_embedded_h264_result_preserves_existing_shape(self) -> None:
        paths = {
            "stream_path": Path("stream.h264"),
            "mp4_path": Path("video.mp4"),
            "snapshot_path": Path("image.jpg"),
            "persistent_path": Path("best.h264"),
        }

        result = empty_embedded_h264_result(
            paths=paths,
            persistent_before=b"previous",
        )

        self.assertEqual(0, result["candidate_count"])
        self.assertEqual("none", result["merge_strategy"])
        self.assertEqual("none", result["persistent_merge_strategy"])
        self.assertEqual([], result["candidate_lens"])
        self.assertEqual(8, result["persistent_previous_len"])
        self.assertEqual(0, result["selected_len"])
        self.assertFalse(result["written"])
        self.assertFalse(result["mp4"])
        self.assertFalse(result["snapshot"])
        self.assertEqual(
            str(paths["stream_path"].resolve()),
            result["stream_path"],
        )

    def test_embedded_h264_result_payload_preserves_shape(self) -> None:
        paths = {
            "stream_path": Path("stream.h264"),
            "mp4_path": Path("video.mp4"),
            "snapshot_path": Path("image.jpg"),
            "persistent_path": Path("best.h264"),
        }

        result = embedded_h264_result_payload(
            unique=[b"a", b"bb"],
            selected=b"bb",
            merge_strategy="longest",
            persistent_strategy="right_extends_left",
            persistent_before=b"a",
            nal_analysis={"has_sps": True},
            persistent_written=True,
            mp4_ok=True,
            mp4_error="",
            snapshot_ok=False,
            snapshot_error="snapshot failed",
            ffmpeg_skipped_reason="",
            paths=paths,
        )

        self.assertEqual(2, result["candidate_count"])
        self.assertEqual("longest", result["merge_strategy"])
        self.assertEqual(
            "right_extends_left",
            result["persistent_merge_strategy"],
        )
        self.assertEqual([1, 2], result["candidate_lens"])
        self.assertEqual(1, result["persistent_previous_len"])
        self.assertEqual(2, result["selected_len"])
        self.assertEqual(
            hashlib.sha1(b"bb").hexdigest(),
            result["selected_sha1"],
        )
        self.assertEqual({"has_sps": True}, result["nal_analysis"])
        self.assertTrue(result["written"])
        self.assertTrue(result["persistent_written"])
        self.assertTrue(result["mp4"])
        self.assertEqual("", result["mp4_error"])
        self.assertFalse(result["snapshot"])
        self.assertEqual("snapshot failed", result["snapshot_error"])
        self.assertEqual("", result["ffmpeg_skipped_reason"])


if __name__ == "__main__":
    unittest.main()
