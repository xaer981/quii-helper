import unittest

from quii_helper.diagnostics.wrapped.tail.candidate_state import (
    TAIL_ARTIFACT_CONTAINER_PROBE,
    TAIL_ARTIFACT_H264_FROM_STARTCODE,
    is_marker_before_offset,
    partial_payload_container_candidate,
    tail_container_probe_candidate,
    tail_startcode_artifact_candidate,
    tail_startcode_h264_candidate,
)
from quii_helper.diagnostics.wrapped.tail.probe import CONTAINER_PROBE_MARKER


class WrappedTailCandidateStateTests(unittest.TestCase):
    def test_tail_startcode_h264_candidate_ignores_missing_start_code(
        self,
    ) -> None:
        self.assertEqual(
            b"",
            tail_startcode_h264_candidate(
                b"tail", marker=CONTAINER_PROBE_MARKER
            ),
        )

    def test_tail_startcode_h264_candidate_skips_container_probe_prefix(
        self,
    ) -> None:
        tail = CONTAINER_PROBE_MARKER + b"\x00\x00\x00\x01g"

        self.assertEqual(
            b"",
            tail_startcode_h264_candidate(tail, marker=CONTAINER_PROBE_MARKER),
        )

    def test_tail_startcode_h264_candidate_returns_from_first_start_code(
        self,
    ) -> None:
        tail = b"prefix" + b"\x00\x00\x00\x01g" + b"rest"

        self.assertEqual(
            b"\x00\x00\x00\x01grest",
            tail_startcode_h264_candidate(tail, marker=CONTAINER_PROBE_MARKER),
        )

    def test_tail_container_probe_candidate_returns_marker_to_tail(
        self,
    ) -> None:
        tail = b"xx" + CONTAINER_PROBE_MARKER + b"\x00\x00\x00\x01g"

        self.assertEqual(
            CONTAINER_PROBE_MARKER + b"\x00\x00\x00\x01g",
            tail_container_probe_candidate(
                tail, marker=CONTAINER_PROBE_MARKER
            ),
        )

    def test_tail_container_probe_candidate_requires_marker_prefix(
        self,
    ) -> None:
        tail = b"xx" + b"\x00\x00\x00\x01g"

        self.assertEqual(
            b"",
            tail_container_probe_candidate(
                tail, marker=CONTAINER_PROBE_MARKER
            ),
        )

    def test_partial_payload_container_candidate_returns_marker_slice(
        self,
    ) -> None:
        payload = b"prefix" + CONTAINER_PROBE_MARKER + b"tail"

        self.assertEqual(
            CONTAINER_PROBE_MARKER + b"tail",
            partial_payload_container_candidate(
                payload, marker=CONTAINER_PROBE_MARKER
            ),
        )

    def test_partial_payload_container_candidate_handles_empty_or_missing(
        self,
    ) -> None:
        self.assertEqual(
            b"",
            partial_payload_container_candidate(
                b"", marker=CONTAINER_PROBE_MARKER
            ),
        )
        self.assertEqual(
            b"",
            partial_payload_container_candidate(
                b"payload", marker=CONTAINER_PROBE_MARKER
            ),
        )

    def test_is_marker_before_offset_preserves_boundary_check(self) -> None:
        blob = b"x" + CONTAINER_PROBE_MARKER + b"\x00\x00\x00\x01"
        offset = blob.index(b"\x00\x00\x00\x01")

        self.assertTrue(
            is_marker_before_offset(
                blob, offset, marker=CONTAINER_PROBE_MARKER
            )
        )
        self.assertFalse(
            is_marker_before_offset(
                blob,
                len(CONTAINER_PROBE_MARKER) - 1,
                marker=CONTAINER_PROBE_MARKER,
            )
        )

    def test_tail_startcode_artifact_candidate_reports_h264_artifact(
        self,
    ) -> None:
        tail = b"prefix" + b"\x00\x00\x00\x01g"

        self.assertEqual(
            (
                TAIL_ARTIFACT_H264_FROM_STARTCODE,
                len(b"prefix"),
                b"\x00\x00\x00\x01g",
            ),
            tail_startcode_artifact_candidate(
                tail, marker=CONTAINER_PROBE_MARKER
            ),
        )

    def test_tail_startcode_artifact_candidate_reports_container_artifact(
        self,
    ) -> None:
        tail = b"prefix" + CONTAINER_PROBE_MARKER + b"\x00\x00\x00\x01g"

        self.assertEqual(
            (
                TAIL_ARTIFACT_CONTAINER_PROBE,
                len(b"prefix"),
                CONTAINER_PROBE_MARKER + b"\x00\x00\x00\x01g",
            ),
            tail_startcode_artifact_candidate(
                tail, marker=CONTAINER_PROBE_MARKER
            ),
        )

    def test_tail_startcode_artifact_candidate_ignores_missing_start_code(
        self,
    ) -> None:
        self.assertIsNone(
            tail_startcode_artifact_candidate(
                b"tail", marker=CONTAINER_PROBE_MARKER
            )
        )


if __name__ == "__main__":
    unittest.main()
