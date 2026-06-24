import unittest

from quii_helper.media.h264.core.analysis import (
    analyze_h264_annexb_stream,
    find_h264_start_codes,
)
from quii_helper.media.h264.merge.probe_analysis import analyze_annexb_h264


class H264AnalysisTests(unittest.TestCase):
    def test_find_h264_start_codes_supports_three_and_four_byte_codes(
        self,
    ) -> None:
        stream = b"\x00\x00\x01\x67abc\x00\x00\x00\x01\x68d"

        self.assertEqual([(0, 3), (7, 4)], find_h264_start_codes(stream))

    def test_analyze_h264_annexb_stream_reports_decodable_context(
        self,
    ) -> None:
        stream = (
            b"\x00\x00\x00\x01\x67sps"
            b"\x00\x00\x00\x01\x68pps"
            b"\x00\x00\x01\x65idr"
            b"\x00\x00\x01\x41p"
        )

        summary = analyze_h264_annexb_stream(stream)

        self.assertEqual(
            {"sps": 1, "pps": 1, "idr_slice": 1, "non_idr_slice": 1},
            summary["counts"],
        )
        self.assertTrue(summary["has_sps"])
        self.assertTrue(summary["has_pps"])
        self.assertTrue(summary["has_idr"])
        self.assertTrue(summary["has_vcl"])
        self.assertTrue(summary["decodable_h264_context"])

    def test_probe_analysis_keeps_false_positive_sps_heuristic(self) -> None:
        stream = b"\x00\x00\x00\x01\x67" + (b"x" * 512)

        summary = analyze_annexb_h264(stream)

        self.assertEqual({"sps": 1}, summary["counts"])
        self.assertTrue(summary["has_sps"])
        self.assertFalse(summary["has_pps"])
        self.assertFalse(summary["has_vcl"])
        self.assertTrue(summary["false_positive_sps_only"])


if __name__ == "__main__":
    unittest.main()
