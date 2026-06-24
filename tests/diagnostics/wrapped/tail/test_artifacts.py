import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from quii_helper.diagnostics.wrapped.tail.artifacts import (
    dump_partial_tail_artifacts,
)
from quii_helper.diagnostics.wrapped.tail.probe import CONTAINER_PROBE_MARKER
from quii_helper.io.paths import resolve_data_dir


class WrappedTailArtifactsTests(unittest.TestCase):
    def test_dump_partial_tail_artifacts_writes_h264_startcode_artifact(
        self,
    ) -> None:
        decrypted_tail = b"prefix" + b"\x00\x00\x00\x01g" + b"tail"

        with tempfile.TemporaryDirectory(
            dir=resolve_data_dir("test_tail_artifacts")
        ) as tmp_dir:
            with patch(
                "quii_helper.diagnostics.wrapped.tail.artifacts"
                ".decrypt_wrapped_quii_tail_bytes",
                return_value=decrypted_tail,
            ):
                artifacts = dump_partial_tail_artifacts(
                    blob=b"blob",
                    key="key",
                    decoded={},
                    dump_dir=Path(tmp_dir),
                    stem="sample",
                )

            h264_path = Path(artifacts["h264_from_startcode_path"])
            self.assertEqual(
                str(len(b"prefix")), artifacts["h264_from_startcode_offset"]
            )
            self.assertEqual(b"\x00\x00\x00\x01gtail", h264_path.read_bytes())
            self.assertEqual(
                decrypted_tail,
                Path(artifacts["decrypted_tail_path"]).read_bytes(),
            )

    def test_dump_partial_tail_artifacts_writes_container_probe_artifact(
        self,
    ) -> None:
        decrypted_tail = (
            b"prefix" + CONTAINER_PROBE_MARKER + b"\x00\x00\x00\x01g"
        )

        with tempfile.TemporaryDirectory(
            dir=resolve_data_dir("test_tail_artifacts")
        ) as tmp_dir:
            with patch(
                "quii_helper.diagnostics.wrapped.tail.artifacts"
                ".decrypt_wrapped_quii_tail_bytes",
                return_value=decrypted_tail,
            ):
                artifacts = dump_partial_tail_artifacts(
                    blob=b"blob",
                    key="key",
                    decoded={},
                    dump_dir=Path(tmp_dir),
                    stem="sample",
                )

            container_path = Path(artifacts["container_probe_path"])
            self.assertEqual(
                str(len(b"prefix")), artifacts["container_probe_offset"]
            )
            self.assertEqual(
                CONTAINER_PROBE_MARKER + b"\x00\x00\x00\x01g",
                container_path.read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
