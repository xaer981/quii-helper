from pathlib import Path

from quii_helper.preview.outputs.manager.state import sample_recorder


class PreviewArtifactManagerStateTests:
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

        assert Path("samples.jsonl") == recorder.sample_path
        assert 3 == recorder.limit
        assert recorder.enabled
        assert seen_hashes is recorder.seen_hashes
