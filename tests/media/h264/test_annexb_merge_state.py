import unittest

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


class MediaAnnexBMergeStateTests(unittest.TestCase):
    def test_sps_only_classification_preserves_existing_gates(self) -> None:
        self.assertTrue(is_sps_only(sps_analysis()))
        self.assertTrue(is_degraded_sps_only(sps_analysis(2)))
        self.assertFalse(is_sps_only(sps_analysis(has_pps=True)))
        self.assertTrue(
            is_false_positive_sps_only({"false_positive_sps_only": True})
        )

    def test_false_positive_and_degraded_decisions_keep_strategy_names(
        self,
    ) -> None:
        false_positive = sps_analysis(false_positive_sps_only=True)
        valid = sps_analysis()

        self.assertEqual(
            (b"right", "replace_false_positive_with_current"),
            false_positive_or_degraded_merge_decision(
                b"left", false_positive, b"right", false_positive
            ),
        )
        self.assertEqual(
            (b"right", "replace_degraded_persistent_sps_only"),
            false_positive_or_degraded_merge_decision(
                b"left", sps_analysis(2), b"right", valid
            ),
        )
        self.assertEqual(
            (b"left", "keep_non_false_positive_left"),
            false_positive_or_degraded_merge_decision(
                b"left", valid, b"right", false_positive
            ),
        )

    def test_containment_decision_keeps_existing_precedence(self) -> None:
        self.assertEqual(
            (b"abcdef", "left_contains_right"),
            containment_merge_decision(b"abcdef", b"cde"),
        )
        self.assertEqual(
            (b"abcdef", "right_extends_left"),
            containment_merge_decision(b"abc", b"abcdef"),
        )

    def test_overlap_decision_preserves_suffix_and_prefix_merges(
        self,
    ) -> None:
        left = b"A" * 4 + b"B" * 16
        right = b"B" * 16 + b"C" * 4

        self.assertEqual(
            (
                b"A" * 4 + b"B" * 16 + b"C" * 4,
                "suffix_prefix_overlap:16",
            ),
            overlap_merge_decision(left, right),
        )
        self.assertEqual(
            (
                b"A" * 4 + b"B" * 16 + b"C" * 4,
                "prefix_suffix_overlap:16",
            ),
            overlap_merge_decision(right, left),
        )

    def test_sps_only_tie_break_prefers_longer_or_current_equal(self) -> None:
        analysis = sps_analysis()

        self.assertEqual(
            (b"right-longer", "prefer_longer_sps_only"),
            sps_only_tie_break_decision(
                b"left", analysis, b"right-longer", analysis
            ),
        )
        self.assertEqual(
            (b"new", "prefer_longer_sps_only"),
            sps_only_tie_break_decision(b"old", analysis, b"new", analysis),
        )


if __name__ == "__main__":
    unittest.main()
