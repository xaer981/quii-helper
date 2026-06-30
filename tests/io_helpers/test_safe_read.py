import tempfile
from pathlib import Path

from quii_helper.io.safe_read import read_existing_bytes


class SafeReadTests:
    def test_read_existing_bytes_returns_file_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.bin"
            path.write_bytes(b"abc")

            assert b"abc" == read_existing_bytes(path)

    def test_read_existing_bytes_returns_empty_for_missing_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            assert b"" == (read_existing_bytes(Path(tmp) / "missing.bin"))

    def test_read_existing_bytes_returns_empty_for_unreadable_path(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            assert b"" == read_existing_bytes(Path(tmp))
