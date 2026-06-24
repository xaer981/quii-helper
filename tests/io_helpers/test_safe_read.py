import tempfile
import unittest
from pathlib import Path

from quii_helper.io.safe_read import read_existing_bytes


class SafeReadTests(unittest.TestCase):
    def test_read_existing_bytes_returns_file_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.bin"
            path.write_bytes(b"abc")

            self.assertEqual(b"abc", read_existing_bytes(path))

    def test_read_existing_bytes_returns_empty_for_missing_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                b"",
                read_existing_bytes(Path(tmp) / "missing.bin"),
            )

    def test_read_existing_bytes_returns_empty_for_unreadable_path(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(b"", read_existing_bytes(Path(tmp)))


if __name__ == "__main__":
    unittest.main()
