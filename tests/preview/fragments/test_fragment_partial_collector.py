import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from quii_helper.io.paths import resolve_data_dir
from quii_helper.preview.fragments.collectors import FragmentPartialCollector


class PreviewFragmentPartialCollectorTests:
    def test_records_fragment_partial_sample_with_existing_payload_shape(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(
            dir=resolve_data_dir("test_fragment_partial_collector")
        ) as tmp_dir:
            sample_path = Path(tmp_dir) / "samples.jsonl"
            collector = FragmentPartialCollector(
                key="key",
                sample_path=sample_path,
                dump_dir=Path(tmp_dir),
                save_diagnostic_artifacts=True,
                sample_limit=2,
            )

            with (
                patch(
                    "quii_helper.preview.fragments.collectors."
                    "analyze_partial_wrapped_inner",
                    return_value={"payload_decode": {"plausible": False}},
                ),
                patch(
                    "quii_helper.preview.fragments.collectors."
                    "candidate_container_probe_from_partial_payload",
                    return_value=b"probe",
                ),
            ):
                analysis = collector.analyze(
                    b"x" * 0x40,
                    source="wrapped_fragment_partial",
                    meta={"src": "test"},
                    message_index=7,
                )

            sample_text = sample_path.read_text(encoding="utf-8")
            rows = [json.loads(line) for line in sample_text.splitlines()]
            assert {"payload_decode": {"plausible": False}} == (analysis)
            assert [b"probe"] == collector.container_probe_candidates
            assert 1 == len(rows)
            assert "sha1" in rows[0]
            assert 7 == rows[0]["msg_index"]
            assert "wrapped_fragment_partial" == rows[0]["source"]
            assert {"src": "test"} == rows[0]["meta"]
            assert analysis == rows[0]["analysis"]

    def test_fragment_partial_sample_limit_and_dedupe_are_shared_with_recorder(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(
            dir=resolve_data_dir("test_fragment_partial_collector")
        ) as tmp_dir:
            sample_path = Path(tmp_dir) / "samples.jsonl"
            collector = FragmentPartialCollector(
                key="key",
                sample_path=sample_path,
                dump_dir=Path(tmp_dir),
                save_diagnostic_artifacts=True,
                sample_limit=1,
            )

            with (
                patch(
                    "quii_helper.preview.fragments.collectors."
                    "analyze_partial_wrapped_inner",
                    return_value={"payload_decode": {"plausible": False}},
                ),
                patch(
                    "quii_helper.preview.fragments.collectors."
                    "candidate_container_probe_from_partial_payload",
                    return_value=b"",
                ),
            ):
                collector.analyze(
                    b"a" * 0x40,
                    source="wrapped_fragment_partial",
                    meta={},
                    message_index=1,
                )
                collector.analyze(
                    b"a" * 0x40,
                    source="wrapped_fragment_partial",
                    meta={},
                    message_index=2,
                )
                collector.analyze(
                    b"b" * 0x40,
                    source="wrapped_fragment_partial",
                    meta={},
                    message_index=3,
                )

            rows = sample_path.read_text(encoding="utf-8").splitlines()
            assert 1 == len(rows)
            assert 1 == len(collector.seen_hashes)

    def test_fragment_partial_samples_update_seen_hashes_when_disabled(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(
            dir=resolve_data_dir("test_fragment_partial_collector")
        ) as tmp_dir:
            sample_path = Path(tmp_dir) / "samples.jsonl"
            collector = FragmentPartialCollector(
                key="key",
                sample_path=sample_path,
                dump_dir=Path(tmp_dir),
                save_diagnostic_artifacts=False,
                sample_limit=2,
            )

            with patch(
                (
                    "quii_helper.preview.fragments."
                    "collectors.analyze_partial_wrapped_inner"
                ),
                return_value={"payload_decode": {"plausible": False}},
            ):
                collector.analyze(
                    b"x" * 0x40,
                    source="wrapped_fragment_partial",
                    meta={},
                    message_index=1,
                )

            assert not sample_path.exists()
            assert 1 == len(collector.seen_hashes)
