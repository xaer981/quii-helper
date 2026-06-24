import unittest
from pathlib import Path

from quii_helper.preview.outputs.manager.state import (
    direct_blob_sample_payload,
    should_save_wrapped_tail_dump,
    wrapped_tail_dump_path,
    wrapped_tail_sample_payload,
)


class PreviewArtifactStateTests(unittest.TestCase):
    def test_should_save_wrapped_tail_dump_requires_flag_and_tail(
        self,
    ) -> None:
        self.assertFalse(
            should_save_wrapped_tail_dump(
                diagnostics_enabled=False,
                decrypted_tail=b"tail",
            )
        )
        self.assertFalse(
            should_save_wrapped_tail_dump(
                diagnostics_enabled=True,
                decrypted_tail=b"",
            )
        )
        self.assertTrue(
            should_save_wrapped_tail_dump(
                diagnostics_enabled=True,
                decrypted_tail=b"tail",
            )
        )

    def test_wrapped_tail_dump_path_keeps_existing_filename_shape(
        self,
    ) -> None:
        self.assertEqual(
            Path("dump") / "msg_007_wrapped_quii.bin",
            wrapped_tail_dump_path(
                Path("dump"),
                msg_index=7,
                source="wrapped_quii",
            ),
        )

    def test_direct_blob_sample_payload_keeps_jsonl_shape(self) -> None:
        payload = direct_blob_sample_payload(
            blob=b"\x01\x02",
            msg_index=7,
            source="direct_quii_blob",
            meta={"src_id": "0x1"},
            candidates=[{"mode": "raw"}],
        )

        self.assertEqual(
            {
                "msg_index": 7,
                "source": "direct_quii_blob",
                "meta": {"src_id": "0x1"},
                "blob_len": 2,
                "blob_hex": "0102",
                "candidates": [{"mode": "raw"}],
            },
            payload,
        )

    def test_wrapped_tail_sample_payload_limits_prefix_to_128_bytes(
        self,
    ) -> None:
        blob = bytes(range(256))
        payload = wrapped_tail_sample_payload(
            blob=blob,
            msg_index=8,
            source="wrapped_quii",
            meta={"lane": 1},
            analysis={"ok": True},
        )

        self.assertEqual(8, payload["msg_index"])
        self.assertEqual("wrapped_quii", payload["source"])
        self.assertEqual({"lane": 1}, payload["meta"])
        self.assertEqual({"ok": True}, payload["analysis"])
        self.assertEqual(256, payload["blob_len"])
        self.assertEqual(blob[:128].hex(), payload["blob_prefix"])


if __name__ == "__main__":
    unittest.main()
