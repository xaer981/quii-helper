from unittest.mock import Mock

from quii_helper.media.h264.io import ffmpeg


def test_missing_ffmpeg_reports_installation_and_path_check(monkeypatch):
    run = Mock(side_effect=FileNotFoundError("synthetic missing executable"))
    monkeypatch.setattr(ffmpeg.subprocess, "run", run)
    ok, error = ffmpeg._run_ffmpeg(["ffmpeg", "-version"])
    assert not ok
    assert "not found on PATH" in error
    assert "ffmpeg -version" in error
    assert "install FFmpeg" in error
