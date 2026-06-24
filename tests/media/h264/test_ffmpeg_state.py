import tempfile
import unittest
from pathlib import Path

from quii_helper.media.h264.io.ffmpeg_state import (
    FALSE_POSITIVE_SPS_SKIP_REASON,
    MISSING_H264_CONTEXT_SKIP_REASON,
    decodable_mp4_skip_reason,
    ffmpeg_input_rate_args,
    h264_mp4_command,
    h264_snapshot_command,
    mp4_skip_reason,
    path_written,
    raw_h264_input_args,
    snapshot_input_args,
)


class H264FfmpegStateTests(unittest.TestCase):
    def test_mp4_skip_reason_preserves_false_positive_sps_gate(self) -> None:
        self.assertEqual(
            FALSE_POSITIVE_SPS_SKIP_REASON,
            mp4_skip_reason({"false_positive_sps_only": True}),
        )
        self.assertEqual("", mp4_skip_reason({}))

    def test_decodable_mp4_skip_reason_preserves_context_gate(self) -> None:
        self.assertEqual(
            MISSING_H264_CONTEXT_SKIP_REASON,
            decodable_mp4_skip_reason({}),
        )
        self.assertEqual(
            "",
            decodable_mp4_skip_reason({"decodable_h264_context": True}),
        )

    def test_ffmpeg_input_rate_args_preserves_fps_format(self) -> None:
        self.assertEqual([], ffmpeg_input_rate_args(None))
        self.assertEqual([], ffmpeg_input_rate_args(0))
        self.assertEqual(
            ["-r", "12.345679"],
            ffmpeg_input_rate_args(12.3456789),
        )

    def test_h264_mp4_command_preserves_existing_arg_order(self) -> None:
        command = h264_mp4_command(
            Path("stream.h264"),
            Path("video.mp4"),
            input_rate_args=["-r", "1.000000"],
        )

        self.assertEqual(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-r",
                "1.000000",
                "-f",
                "h264",
                "-i",
                "stream.h264",
                "-c:v",
                "copy",
                "video.mp4",
            ],
            command,
        )

    def test_snapshot_input_args_selects_mp4_only_when_available(self) -> None:
        self.assertEqual(
            ["-f", "h264", "-i", "stream.h264"],
            raw_h264_input_args(Path("stream.h264")),
        )
        self.assertEqual(
            ["-i", "video.mp4"],
            snapshot_input_args(
                Path("stream.h264"),
                Path("video.mp4"),
                mp4_ok=True,
            ),
        )
        self.assertEqual(
            ["-f", "h264", "-i", "stream.h264"],
            snapshot_input_args(
                Path("stream.h264"),
                Path("video.mp4"),
                mp4_ok=False,
            ),
        )

    def test_h264_snapshot_command_preserves_existing_arg_order(self) -> None:
        self.assertEqual(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                "video.mp4",
                "-frames:v",
                "1",
                "snapshot.jpg",
            ],
            h264_snapshot_command(
                Path("snapshot.jpg"),
                input_args=["-i", "video.mp4"],
            ),
        )

    def test_path_written_matches_existing_file_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.bin"

            self.assertFalse(path_written(path))
            path.write_bytes(b"")
            self.assertTrue(path_written(path))
            self.assertFalse(path_written(path, require_non_empty=True))
            path.write_bytes(b"x")
            self.assertTrue(path_written(path, require_non_empty=True))


if __name__ == "__main__":
    unittest.main()
