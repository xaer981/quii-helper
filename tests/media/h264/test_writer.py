import tempfile
from pathlib import Path

import pytest

from quii_helper.media.h264.io.writer import _write_stream_bytes
from quii_helper.support.errors import MediaRenderError


class H264WriterTests:
    def test_write_stream_bytes_reports_raw_stream_write_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stream_path = Path(tmp) / "clip.h264"
            stream_path.mkdir()

            with pytest.raises(
                MediaRenderError, match="unable to write raw H.264 stream"
            ):
                _write_stream_bytes(stream_path, b"\x00\x00\x00\x01\x65idr")
