from quii_helper.media.h264.core.analysis import (
    analyze_h264_annexb_stream,
    find_h264_start_codes,
)
from quii_helper.media.h264.merge.probe_analysis import analyze_annexb_h264


class H264AnalysisTests:
    def test_find_h264_start_codes_supports_three_and_four_byte_codes(
        self,
    ) -> None:
        stream = b"\x00\x00\x01\x67abc\x00\x00\x00\x01\x68d"

        assert [(0, 3), (7, 4)] == find_h264_start_codes(stream)

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

        assert {"sps": 1, "pps": 1, "idr_slice": 1, "non_idr_slice": 1} == (
            summary["counts"]
        )
        assert summary["has_sps"]
        assert summary["has_pps"]
        assert summary["has_idr"]
        assert summary["has_vcl"]
        assert summary["decodable_h264_context"]

    def test_probe_analysis_keeps_false_positive_sps_heuristic(self) -> None:
        stream = b"\x00\x00\x00\x01\x67" + (b"x" * 512)

        summary = analyze_annexb_h264(stream)

        assert {"sps": 1} == summary["counts"]
        assert summary["has_sps"]
        assert not summary["has_pps"]
        assert not summary["has_vcl"]
        assert summary["false_positive_sps_only"]
