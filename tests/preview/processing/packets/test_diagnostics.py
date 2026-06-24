import unittest
from types import SimpleNamespace
from unittest.mock import patch

from quii_helper.preview.processing.packets.diagnostics import (
    collect_packet_diagnostics,
)


class PreviewPacketDiagnosticsTests(unittest.TestCase):
    def test_collect_packet_diagnostics_returns_empty_when_disabled(
        self,
    ) -> None:
        diagnostics = collect_packet_diagnostics(
            artifacts=SimpleNamespace(diagnostics_enabled=False),
            blob=b"blob",
            key="key",
            decoded={"plausible": False},
            message_index=1,
            source="direct_quii_blob",
            meta={},
            phase="live",
        )

        self.assertEqual([], diagnostics.decode_candidates)
        self.assertIsNone(diagnostics.wrapped_tail_analysis)

    def test_collect_packet_diagnostics_runs_candidate_and_tail_hooks(
        self,
    ) -> None:
        artifacts = SimpleNamespace(diagnostics_enabled=True)
        decoded = {"plausible": True}
        candidates = [{"candidate": True}]
        tail = {"tail": True}

        with (
            patch(
                "quii_helper.preview.processing.packets.diagnostics."
                "direct_blob_decode_candidates",
                return_value=candidates,
            ) as direct_candidates,
            patch(
                "quii_helper.preview.processing.packets.diagnostics."
                "record_direct_blob_sample",
            ) as record_sample,
            patch(
                "quii_helper.preview.processing.packets.diagnostics."
                "wrapped_tail_diagnostics",
                return_value=tail,
            ) as wrapped_tail,
        ):
            diagnostics = collect_packet_diagnostics(
                artifacts=artifacts,
                blob=b"blob",
                key="key",
                decoded=decoded,
                message_index=2,
                source="wrapped_quii",
                meta={"src_id": 1},
                phase="live",
            )

        direct_candidates.assert_called_once()
        record_sample.assert_called_once()
        wrapped_tail.assert_called_once()
        self.assertEqual(candidates, diagnostics.decode_candidates)
        self.assertEqual(tail, diagnostics.wrapped_tail_analysis)


if __name__ == "__main__":
    unittest.main()
