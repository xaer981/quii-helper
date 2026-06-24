import unittest
from pathlib import Path

from quii_helper.preview.outputs.manager.state import sample_recorder


class PreviewArtifactManagerStateTests(unittest.TestCase):
    def test_sample_recorder_preserves_configuration_and_seen_hash_set(
        self,
    ) -> None:
        seen_hashes: set[str] = set()

        recorder = sample_recorder(
            sample_path=Path("samples.jsonl"),
            limit=3,
            enabled=True,
            seen_hashes=seen_hashes,
        )

        self.assertEqual(Path("samples.jsonl"), recorder.sample_path)
        self.assertEqual(3, recorder.limit)
        self.assertTrue(recorder.enabled)
        self.assertIs(seen_hashes, recorder.seen_hashes)


if __name__ == "__main__":
    unittest.main()
