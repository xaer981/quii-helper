import unittest

from quii_helper.diagnostics.wrapped.tail.probe import (
    CONTAINER_PROBE_MARKER,
    analyze_decrypted_tail,
    container_probe_for_first_h264,
    find_start_code_offsets,
    is_container_probe_before_start_code,
)
from quii_helper.diagnostics.wrapped.tail.probe_state import (
    container_probe_without_marker,
    dwords_from_bytes,
    empty_decrypted_tail_analysis,
)


class WrappedTailProbeTests(unittest.TestCase):
    def test_empty_tail_analysis_shape_is_stable(self) -> None:
        self.assertEqual(
            empty_decrypted_tail_analysis(), analyze_decrypted_tail(b"")
        )

    def test_find_start_code_offsets_can_exclude_four_byte_markers(
        self,
    ) -> None:
        blob = b"\x00\x00\x00\x01a\x00\x00\x01b"

        self.assertEqual(
            [0],
            find_start_code_offsets(blob, marker=b"\x00\x00\x00\x01"),
        )
        self.assertEqual(
            [5],
            find_start_code_offsets(
                blob,
                marker=b"\x00\x00\x01",
                exclude_four_byte=True,
            ),
        )

    def test_container_probe_without_marker_shape_is_stable(self) -> None:
        self.assertEqual(
            container_probe_without_marker(),
            container_probe_for_first_h264(b"abc", []),
        )

    def test_container_probe_reports_false_h264_marker_context(self) -> None:
        blob = b"prefix" + CONTAINER_PROBE_MARKER + b"\x00\x00\x00\x01g"
        marker_offset = blob.index(b"\x00\x00\x00\x01")

        probe = container_probe_for_first_h264(blob, [marker_offset])

        self.assertEqual(marker_offset, probe["first_marker_offset"])
        self.assertEqual(
            CONTAINER_PROBE_MARKER.hex(), probe["pre_marker_tail_hex"]
        )
        self.assertTrue(probe["looks_like_false_h264_container"])
        self.assertTrue(
            is_container_probe_before_start_code(blob, marker_offset)
        )

    def test_dwords_from_bytes_ignores_trailing_partial_word(self) -> None:
        self.assertEqual(
            [0x04030201],
            dwords_from_bytes(b"\x01\x02\x03\x04x", "little"),
        )
        self.assertEqual(
            [0x01020304],
            dwords_from_bytes(b"\x01\x02\x03\x04x", "big"),
        )


if __name__ == "__main__":
    unittest.main()
