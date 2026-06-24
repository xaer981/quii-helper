import unittest

from quii_helper.preview.processing.payloads.diagnostics_state import (
    should_analyze_wrapped_tail,
    should_find_direct_blob_candidates,
    should_record_direct_blob_sample,
)


class PreviewPayloadDiagnosticsStateTests(unittest.TestCase):
    def test_should_find_direct_blob_candidates_matches_existing_gate(
        self,
    ) -> None:
        self.assertTrue(
            should_find_direct_blob_candidates(
                source="direct_quii_blob",
                decoded={"plausible": False},
                phase="live",
            )
        )
        self.assertTrue(
            should_find_direct_blob_candidates(
                source="direct_quii_blob",
                decoded={"plausible": False},
                phase="flush",
            )
        )
        self.assertFalse(
            should_find_direct_blob_candidates(
                source="wrapped_quii",
                decoded={"plausible": False},
                phase="live",
            )
        )
        self.assertFalse(
            should_find_direct_blob_candidates(
                source="direct_quii_blob",
                decoded={"plausible": True},
                phase="live",
            )
        )
        self.assertFalse(
            should_find_direct_blob_candidates(
                source="direct_quii_blob",
                decoded={"plausible": False},
                phase="close",
            )
        )

    def test_should_record_direct_blob_sample_matches_existing_gate(
        self,
    ) -> None:
        self.assertTrue(
            should_record_direct_blob_sample(
                source="direct_quii_blob",
                phase="live",
            )
        )
        self.assertFalse(
            should_record_direct_blob_sample(
                source="direct_quii_blob",
                phase="flush",
            )
        )
        self.assertFalse(
            should_record_direct_blob_sample(
                source="wrapped_quii",
                phase="live",
            )
        )

    def test_should_analyze_wrapped_tail_matches_existing_gate(self) -> None:
        self.assertTrue(
            should_analyze_wrapped_tail(
                source="wrapped_quii",
                decoded={"plausible": True},
                phase="live",
            )
        )
        self.assertFalse(
            should_analyze_wrapped_tail(
                source="wrapped_quii",
                decoded={"plausible": True},
                phase="flush",
            )
        )
        self.assertFalse(
            should_analyze_wrapped_tail(
                source="direct_quii_blob",
                decoded={"plausible": True},
                phase="live",
            )
        )
        self.assertFalse(
            should_analyze_wrapped_tail(
                source="wrapped_quii",
                decoded={"plausible": False},
                phase="live",
            )
        )


if __name__ == "__main__":
    unittest.main()
