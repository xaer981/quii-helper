from typing import get_type_hints

from quii_helper.media.frames.assembler import AssembledH264Stream
from quii_helper.media.frames.assembler_state import (
    frame_info_from_parsed_frame,
)
from quii_helper.media.h264.core.analysis import analyze_h264_annexb_stream
from quii_helper.models.capture import (
    H264AnalysisSummary,
    MediaCollectionSummary,
    MediaFrameSummary,
)
from quii_helper.preview.summaries.media_summary import (
    media_collection_summary,
    media_message_nal_analysis,
)
from quii_helper.preview.summaries.media_summary_state import (
    initial_nal_collection_state,
)


class CaptureModelUsageTests:
    def test_h264_analysis_uses_typed_summary_model(self) -> None:
        hints = get_type_hints(analyze_h264_annexb_stream)

        assert H264AnalysisSummary is hints["return"]

    def test_media_frame_helpers_use_typed_summary_model(self) -> None:
        hints = get_type_hints(frame_info_from_parsed_frame)
        dataclass_hints = get_type_hints(AssembledH264Stream)

        assert MediaFrameSummary is hints["return"]
        assert list[MediaFrameSummary] == dataclass_hints["frames"]

    def test_media_collection_helpers_use_typed_summary_model(self) -> None:
        collection_hints = get_type_hints(media_collection_summary)
        message_hints = get_type_hints(media_message_nal_analysis)
        state_hints = get_type_hints(initial_nal_collection_state)

        assert MediaCollectionSummary is collection_hints["return"]
        assert H264AnalysisSummary is message_hints["return"]
        assert MediaCollectionSummary is state_hints["return"]
