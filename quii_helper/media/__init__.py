"""Media parsing, assembly, analysis, and output helpers."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "AssembledH264Stream": (
        "quii_helper.media.assembler",
        "AssembledH264Stream",
    ),
    "QuiiHeader": ("quii_helper.media.models", "QuiiHeader"),
    "analyze_h264_annexb_stream": (
        "quii_helper.media.h264_analysis",
        "analyze_h264_annexb_stream",
    ),
    "assemble_h264_stream_from_messages": (
        "quii_helper.media.assembler",
        "assemble_h264_stream_from_messages",
    ),
    "find_h264_start_codes": (
        "quii_helper.media.h264_analysis",
        "find_h264_start_codes",
    ),
    "iter_quii_media_frames": (
        "quii_helper.media.parsing",
        "iter_quii_media_frames",
    ),
    "parse_quii_media_frame": (
        "quii_helper.media.parsing",
        "parse_quii_media_frame",
    ),
    "write_h264_stream": ("quii_helper.media.writer", "write_h264_stream"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        ) from exc
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
