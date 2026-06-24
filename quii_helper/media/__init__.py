"""Media parsing, assembly, analysis, and output helpers."""

from quii_helper.support.lazy import lazy_exports

_EXPORTS = {
    "AssembledH264Stream": (
        "quii_helper.media.frames.assembler",
        "AssembledH264Stream",
    ),
    "QuiiHeader": ("quii_helper.media.frames.models", "QuiiHeader"),
    "analyze_h264_annexb_stream": (
        "quii_helper.media.h264.core.analysis",
        "analyze_h264_annexb_stream",
    ),
    "assemble_h264_stream_from_messages": (
        "quii_helper.media.frames.assembler",
        "assemble_h264_stream_from_messages",
    ),
    "find_h264_start_codes": (
        "quii_helper.media.h264.core.analysis",
        "find_h264_start_codes",
    ),
    "iter_quii_media_frames": (
        "quii_helper.media.frames.parsing",
        "iter_quii_media_frames",
    ),
    "parse_quii_media_frame": (
        "quii_helper.media.frames.parsing",
        "parse_quii_media_frame",
    ),
    "write_h264_stream": (
        "quii_helper.media.h264.io.writer",
        "write_h264_stream",
    ),
}

__all__, __getattr__ = lazy_exports(__name__, _EXPORTS, globals())
