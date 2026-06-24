import tempfile
import unittest
from pathlib import Path

from quii_helper.media.h264.io.writer_state import (
    empty_h264_stream_result,
    h264_output_paths,
    h264_stream_result_payload,
    input_fps_for_target_duration,
    should_remove_raw_h264,
)


class MediaWriterStateTests(unittest.TestCase):
    def test_h264_output_paths_preserve_suffixes_and_data_resolution(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stream_path, mp4_path, snapshot_path = h264_output_paths(
                "clip.raw",
                output_dir=Path(tmp),
            )

        self.assertEqual("clip.h264", stream_path.name)
        self.assertEqual("clip.mp4", mp4_path.name)
        self.assertEqual("clip.jpg", snapshot_path.name)

    def test_input_fps_for_target_duration_matches_existing_intervals(
        self,
    ) -> None:
        self.assertIsNone(
            input_fps_for_target_duration(
                frame_count=0,
                target_duration_seconds=10,
            )
        )
        self.assertIsNone(
            input_fps_for_target_duration(
                frame_count=3,
                target_duration_seconds=0,
            )
        )
        self.assertEqual(
            1 / 60,
            input_fps_for_target_duration(
                frame_count=1,
                target_duration_seconds=60,
            ),
        )
        self.assertEqual(
            0.5,
            input_fps_for_target_duration(
                frame_count=31,
                target_duration_seconds=60,
            ),
        )

    def test_should_remove_raw_h264_matches_cleanup_gate(self) -> None:
        self.assertFalse(
            should_remove_raw_h264(
                mp4_ok=False,
                snapshot_ok=False,
                keep_raw_h264=False,
            )
        )
        self.assertFalse(
            should_remove_raw_h264(
                mp4_ok=True,
                snapshot_ok=False,
                keep_raw_h264=True,
            )
        )
        self.assertTrue(
            should_remove_raw_h264(
                mp4_ok=True,
                snapshot_ok=False,
                keep_raw_h264=False,
            )
        )
        self.assertTrue(
            should_remove_raw_h264(
                mp4_ok=False,
                snapshot_ok=True,
                keep_raw_h264=False,
            )
        )

    def test_empty_h264_stream_result_preserves_existing_shape(self) -> None:
        result = empty_h264_stream_result(
            stream_path=Path("clip.h264"),
            mp4_path=Path("clip.mp4"),
            snapshot_path=Path("clip.jpg"),
            frames=[],
            summary={"assembled_units": 0},
            keep_raw_h264=False,
        )

        self.assertEqual("", result["stream_path"])
        self.assertEqual(str(Path("clip.mp4").resolve()), result["mp4_path"])
        self.assertEqual(
            str(Path("clip.jpg").resolve()),
            result["snapshot_path"],
        )
        self.assertEqual([], result["frames"])
        self.assertEqual({"assembled_units": 0}, result["summary"])
        self.assertFalse(result["written"])
        self.assertFalse(result["mp4"])
        self.assertFalse(result["snapshot"])

    def test_h264_stream_result_payload_preserves_existing_shape(self) -> None:
        result = h264_stream_result_payload(
            stream_path=Path("clip.h264"),
            mp4_path=Path("clip.mp4"),
            snapshot_path=Path("clip.jpg"),
            frames=[{"frame": 1}],
            summary={"assembled_units": 1},
            keep_raw_h264=True,
            mp4_ok=True,
            mp4_error="",
            snapshot_ok=False,
            snapshot_error="snapshot failed",
            ffmpeg_skipped_reason="",
        )

        self.assertEqual(
            str(Path("clip.h264").resolve()),
            result["stream_path"],
        )
        self.assertEqual(str(Path("clip.mp4").resolve()), result["mp4_path"])
        self.assertEqual(
            str(Path("clip.jpg").resolve()),
            result["snapshot_path"],
        )
        self.assertEqual([{"frame": 1}], result["frames"])
        self.assertEqual({"assembled_units": 1}, result["summary"])
        self.assertTrue(result["written"])
        self.assertTrue(result["mp4"])
        self.assertEqual("", result["mp4_error"])
        self.assertFalse(result["snapshot"])
        self.assertEqual("snapshot failed", result["snapshot_error"])
        self.assertEqual("", result["ffmpeg_skipped_reason"])


if __name__ == "__main__":
    unittest.main()
