from pathlib import Path
from unittest.mock import Mock

import pytest

from quii_helper.media.audio.recording import AudioRecording
from quii_helper.media.h264.io import ffmpeg
from tests.media.audio.test_recording import audio, video


def test_missing_ffmpeg_reports_installation_and_path_check(monkeypatch):
    run = Mock(side_effect=FileNotFoundError("synthetic missing executable"))
    monkeypatch.setattr(ffmpeg.subprocess, "run", run)
    ok, error = ffmpeg._run_ffmpeg(["ffmpeg", "-version"])
    assert not ok
    assert "not found on PATH" in error
    assert "ffmpeg -version" in error
    assert "install FFmpeg" in error


def test_temporary_audio_is_private_and_removed_after_ffmpeg_failure(
    tmp_path, monkeypatch
):
    recording = AudioRecording()
    recording.start_video(video())
    recording.feed(audio(data=b"private-audio"))
    temporary_paths = []

    def fail(command):
        inputs = [
            command[index + 1]
            for index, arg in enumerate(command)
            if arg == "-i"
        ]
        path = Path(inputs[1])
        assert path.read_bytes() == b"private-audio"
        assert path.parent.parent == tmp_path
        temporary_paths.append(path)
        return False, "synthetic ffmpeg failure"

    monkeypatch.setattr(ffmpeg, "_run_ffmpeg", fail)
    result = ffmpeg.write_h264_mp4_if_decodable(
        tmp_path / "video.h264",
        tmp_path / "video.mp4",
        {"decodable_h264_context": True},
        input_fps=20,
        audio=recording,
        duration_seconds=1,
    )
    assert result == (False, "synthetic ffmpeg failure", "")
    assert temporary_paths and not temporary_paths[0].parent.exists()


@pytest.mark.parametrize("duration", [None, 0, -1, float("inf"), float("nan")])
def test_audio_padding_requires_a_finite_duration(
    tmp_path, monkeypatch, duration
):
    recording = AudioRecording()
    recording.start_video(video())
    recording.feed(audio())
    run = Mock()
    monkeypatch.setattr(ffmpeg, "_run_ffmpeg", run)
    ok, error, _ = ffmpeg.write_h264_mp4_if_decodable(
        tmp_path / "video.h264",
        tmp_path / "video.mp4",
        {"decodable_h264_context": True},
        input_fps=20,
        audio=recording,
        duration_seconds=duration,
    )
    assert not ok and "finite positive" in error
    run.assert_not_called()
