import hashlib
from pathlib import Path

from quii_helper.preview.outputs.probes.state import (
    merge_persistent_probe_best,
    probe_family_prefix,
    probe_output_paths,
    probe_summary_payload,
)


class PreviewProbeOutputStateTests:
    def test_probe_output_paths_preserve_existing_suffix_shape(self) -> None:
        output_path, best_path = probe_output_paths("sample", "container")

        assert "sample_container_probe.bin" == output_path.name
        assert "sample_container_probe_best.bin" == best_path.name

    def test_probe_family_prefix_uses_first_16_bytes(self) -> None:
        assert b"short" == probe_family_prefix(b"short")
        assert b"1234567890abcdef" == (
            probe_family_prefix(b"1234567890abcdefTAIL")
        )

    def test_persistent_merge_uses_current_without_previous(self) -> None:
        merged, strategy = merge_persistent_probe_best(
            b"",
            b"current",
            replace_disjoint_same_header=True,
        )

        assert b"current" == merged
        assert "right_only" == strategy

    def test_container_probe_replaces_equal_length_current(self) -> None:
        merged, strategy = merge_persistent_probe_best(
            b"previous",
            b"selected",
            replace_disjoint_same_header=True,
        )

        assert b"selected" == merged
        assert "replace_equal_length_current" == strategy

    def test_container_probe_replaces_disjoint_family(self) -> None:
        merged, strategy = merge_persistent_probe_best(
            b"ABCDEFGH11111111-extra",
            b"ABCDEFGH22222222",
            replace_disjoint_same_header=True,
        )

        assert b"ABCDEFGH22222222" == merged
        assert "replace_disjoint_same_header_current" == strategy

    def test_cpacket_probe_keeps_generic_binary_merge_behavior(self) -> None:
        previous = b"A" * 16 + b"B" * 16
        selected = b"B" * 16 + b"C"

        merged, strategy = merge_persistent_probe_best(
            previous,
            selected,
            replace_disjoint_same_header=False,
        )

        assert previous + b"C" == merged
        assert "suffix_prefix_overlap:16" == strategy

    def test_probe_summary_payload_preserves_existing_fields(self) -> None:
        output_path = Path("out.bin")
        best_path = Path("best.bin")

        summary = probe_summary_payload(
            unique=[b"a", b"bb"],
            selected=b"bb",
            merge_strategy="longest",
            previous=b"a",
            merged_best=b"abb",
            persistent_strategy="suffix_prefix_overlap:1",
            analysis={"ok": True},
            output_path=output_path,
            best_path=best_path,
        )

        assert 2 == summary["candidate_count"]
        assert [1, 2] == summary["candidate_lens"]
        assert "longest" == summary["merge_strategy"]
        assert 2 == summary["selected_len"]
        assert hashlib.sha1(b"bb").hexdigest() == (summary["selected_sha1"])
        assert 1 == summary["persistent_previous_len"]
        assert "suffix_prefix_overlap:1" == (
            summary["persistent_merge_strategy"]
        )
        assert 3 == summary["persistent_len"]
        assert hashlib.sha1(b"abb").hexdigest() == (summary["persistent_sha1"])
        assert {"ok": True} == summary["analysis"]
        assert str(output_path.resolve()) == summary["stream_path"]
        assert str(best_path.resolve()) == summary["persistent_path"]
