import tempfile
from pathlib import Path

from quii_helper.media.h264.io.writer_state import (
    empty_h264_stream_result,
    h264_output_paths,
    h264_stream_result_payload,
    input_fps_for_target_duration,
    should_remove_raw_h264,
)


class MediaWriterStateTests:
    def test_h264_output_paths_preserve_suffixes_and_data_resolution(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stream_path, mp4_path, snapshot_path = h264_output_paths(
                "clip.raw",
                output_dir=Path(tmp),
            )

        assert "clip.h264" == stream_path.name
        assert "clip.mp4" == mp4_path.name
        assert "clip.jpg" == snapshot_path.name

    def test_input_fps_for_target_duration_matches_existing_intervals(
        self,
    ) -> None:
        assert (
            input_fps_for_target_duration(
                frame_count=0,
                target_duration_seconds=10,
            )
            is None
        )
        assert (
            input_fps_for_target_duration(
                frame_count=3,
                target_duration_seconds=0,
            )
            is None
        )
        assert 1 / 60 == (
            input_fps_for_target_duration(
                frame_count=1,
                target_duration_seconds=60,
            )
        )
        assert 0.5 == (
            input_fps_for_target_duration(
                frame_count=31,
                target_duration_seconds=60,
            )
        )

    def test_should_remove_raw_h264_matches_cleanup_gate(self) -> None:
        assert not should_remove_raw_h264(
            mp4_ok=False,
            snapshot_ok=False,
            keep_raw_h264=False,
        )
        assert not should_remove_raw_h264(
            mp4_ok=True,
            snapshot_ok=False,
            keep_raw_h264=True,
        )
        assert should_remove_raw_h264(
            mp4_ok=True,
            snapshot_ok=False,
            keep_raw_h264=False,
        )
        assert should_remove_raw_h264(
            mp4_ok=False,
            snapshot_ok=True,
            keep_raw_h264=False,
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

        assert "" == result["stream_path"]
        assert str(Path("clip.mp4").resolve()) == result["mp4_path"]
        assert str(Path("clip.jpg").resolve()) == (result["snapshot_path"])
        assert [] == result["frames"]
        assert {"assembled_units": 0} == result["summary"]
        assert not result["written"]
        assert not result["mp4"]
        assert not result["snapshot"]

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

        assert str(Path("clip.h264").resolve()) == (result["stream_path"])
        assert str(Path("clip.mp4").resolve()) == result["mp4_path"]
        assert str(Path("clip.jpg").resolve()) == (result["snapshot_path"])
        assert [{"frame": 1}] == result["frames"]
        assert {"assembled_units": 1} == result["summary"]
        assert result["written"]
        assert result["mp4"]
        assert "" == result["mp4_error"]
        assert not result["snapshot"]
        assert "snapshot failed" == result["snapshot_error"]
        assert "" == result["ffmpeg_skipped_reason"]
