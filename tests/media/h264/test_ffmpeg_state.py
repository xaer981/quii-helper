import tempfile
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


class H264FfmpegStateTests:
    def test_audio_mux_preserves_video_and_bounds_padded_audio(self) -> None:
        command = h264_mp4_command(
            Path("stream.h264"),
            Path("video.mp4"),
            input_rate_args=["-r", "20.000000"],
            audio_path=Path("audio.g711"),
            audio_format="mulaw",
            audio_offset_seconds=0.2,
            duration_seconds=1.0,
        )
        assert command.count("-i") == 2
        assert command[command.index("-af") + 1] == (
            "adelay=200:all=1,apad,atrim=duration=1.000000"
        )
        assert command[command.index("-t") + 1] == "1.000000"
        assert command[command.index("-c:a") + 1] == "aac"
        assert command[command.index("-c:v") + 1] == "copy"
        assert "-itsoffset" not in command and "-shortest" not in command

    def test_mp4_skip_reason_preserves_false_positive_sps_gate(self) -> None:
        assert FALSE_POSITIVE_SPS_SKIP_REASON == (
            mp4_skip_reason({"false_positive_sps_only": True})
        )
        assert "" == mp4_skip_reason({})

    def test_decodable_mp4_skip_reason_preserves_context_gate(self) -> None:
        assert MISSING_H264_CONTEXT_SKIP_REASON == (
            decodable_mp4_skip_reason({})
        )
        assert "" == (
            decodable_mp4_skip_reason({"decodable_h264_context": True})
        )

    def test_ffmpeg_input_rate_args_preserves_fps_format(self) -> None:
        assert [] == ffmpeg_input_rate_args(None)
        assert [] == ffmpeg_input_rate_args(0)
        assert ["-r", "12.345679"] == (ffmpeg_input_rate_args(12.3456789))

    def test_h264_mp4_command_preserves_existing_arg_order(self) -> None:
        command = h264_mp4_command(
            Path("stream.h264"),
            Path("video.mp4"),
            input_rate_args=["-r", "1.000000"],
        )

        assert [
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
        ] == (command)

    def test_snapshot_input_args_selects_mp4_only_when_available(self) -> None:
        assert ["-f", "h264", "-i", "stream.h264"] == (
            raw_h264_input_args(Path("stream.h264"))
        )
        assert ["-i", "video.mp4"] == (
            snapshot_input_args(
                Path("stream.h264"),
                Path("video.mp4"),
                mp4_ok=True,
            )
        )
        assert ["-f", "h264", "-i", "stream.h264"] == (
            snapshot_input_args(
                Path("stream.h264"),
                Path("video.mp4"),
                mp4_ok=False,
            )
        )

    def test_h264_snapshot_command_preserves_existing_arg_order(self) -> None:
        assert [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            "video.mp4",
            "-frames:v",
            "1",
            "snapshot.jpg",
        ] == (
            h264_snapshot_command(
                Path("snapshot.jpg"),
                input_args=["-i", "video.mp4"],
            )
        )

    def test_path_written_matches_existing_file_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.bin"

            assert not path_written(path)
            path.write_bytes(b"")
            assert path_written(path)
            assert not path_written(path, require_non_empty=True)
            path.write_bytes(b"x")
            assert path_written(path, require_non_empty=True)
