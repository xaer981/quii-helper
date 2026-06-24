"""Diagnostic helpers for protocol payload analysis."""

from quii_helper.support.lazy import lazy_exports

_EXPORTS = {
    "analyze_partial_wrapped_inner": (
        "quii_helper.diagnostics.wrapped.payload.inner_analysis",
        "analyze_partial_wrapped_inner",
    ),
    "analyze_wrapped_quii_tail": (
        "quii_helper.diagnostics.wrapped.tail.analysis",
        "analyze_wrapped_quii_tail",
    ),
    "decrypt_wrapped_quii_tail_bytes": (
        "quii_helper.diagnostics.wrapped.tail.analysis",
        "decrypt_wrapped_quii_tail_bytes",
    ),
    "dump_partial_tail_artifacts": (
        "quii_helper.diagnostics.wrapped.tail.candidates",
        "dump_partial_tail_artifacts",
    ),
}

__all__, __getattr__ = lazy_exports(__name__, _EXPORTS, globals())
