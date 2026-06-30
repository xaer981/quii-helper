from quii_helper.media.h264.merge.annexb_merge_state import (
    containment_merge_decision,
    false_positive_or_degraded_merge_decision,
    is_degraded_sps_only,
    is_false_positive_sps_only,
    is_sps_only,
    overlap_merge_decision,
    sps_only_tie_break_decision,
)


def sps_analysis(count: int = 1, **overrides: object) -> dict:
    analysis = {
        "counts": {"sps": count},
        "has_pps": False,
        "has_vcl": False,
    }
    analysis.update(overrides)
    return analysis


class MediaAnnexBMergeStateTests:
    def test_sps_only_classification_preserves_existing_gates(self) -> None:
        assert is_sps_only(sps_analysis())
        assert is_degraded_sps_only(sps_analysis(2))
        assert not is_sps_only(sps_analysis(has_pps=True))
        assert is_false_positive_sps_only({"false_positive_sps_only": True})

    def test_false_positive_and_degraded_decisions_keep_strategy_names(
        self,
    ) -> None:
        false_positive = sps_analysis(false_positive_sps_only=True)
        valid = sps_analysis()

        assert (b"right", "replace_false_positive_with_current") == (
            false_positive_or_degraded_merge_decision(
                b"left", false_positive, b"right", false_positive
            )
        )
        assert (b"right", "replace_degraded_persistent_sps_only") == (
            false_positive_or_degraded_merge_decision(
                b"left", sps_analysis(2), b"right", valid
            )
        )
        assert (b"left", "keep_non_false_positive_left") == (
            false_positive_or_degraded_merge_decision(
                b"left", valid, b"right", false_positive
            )
        )

    def test_containment_decision_keeps_existing_precedence(self) -> None:
        assert (b"abcdef", "left_contains_right") == (
            containment_merge_decision(b"abcdef", b"cde")
        )
        assert (b"abcdef", "right_extends_left") == (
            containment_merge_decision(b"abc", b"abcdef")
        )

    def test_overlap_decision_preserves_suffix_and_prefix_merges(
        self,
    ) -> None:
        left = b"A" * 4 + b"B" * 16
        right = b"B" * 16 + b"C" * 4

        assert (
            b"A" * 4 + b"B" * 16 + b"C" * 4,
            "suffix_prefix_overlap:16",
        ) == (overlap_merge_decision(left, right))
        assert (
            b"A" * 4 + b"B" * 16 + b"C" * 4,
            "prefix_suffix_overlap:16",
        ) == (overlap_merge_decision(right, left))

    def test_sps_only_tie_break_prefers_longer_or_current_equal(self) -> None:
        analysis = sps_analysis()

        assert (b"right-longer", "prefer_longer_sps_only") == (
            sps_only_tie_break_decision(
                b"left", analysis, b"right-longer", analysis
            )
        )
        assert (b"new", "prefer_longer_sps_only") == (
            sps_only_tie_break_decision(b"old", analysis, b"new", analysis)
        )
