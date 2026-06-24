"""Wrapped payload and tail diagnostics."""

from quii_helper.support.lazy import lazy_exports

_EXPORTS = {
    "analyze_partial_wrapped_inner": (
        "quii_helper.diagnostics.wrapped.payload.inner_analysis",
        "analyze_partial_wrapped_inner",
    ),
    "analyze_payload_embedded_probe": (
        "quii_helper.diagnostics.wrapped.tail.candidates",
        "analyze_payload_embedded_probe",
    ),
    "analyze_wrapped_quii_tail": (
        "quii_helper.diagnostics.wrapped.tail.analysis",
        "analyze_wrapped_quii_tail",
    ),
    "candidate_container_probe": (
        "quii_helper.diagnostics.wrapped.tail.candidates",
        "candidate_container_probe",
    ),
    "candidate_container_probe_from_partial_payload": (
        "quii_helper.diagnostics.wrapped.tail.candidates",
        "candidate_container_probe_from_partial_payload",
    ),
    "candidate_cpacket_from_decrypted_tail": (
        "quii_helper.diagnostics.wrapped.tail.candidates",
        "candidate_cpacket_from_decrypted_tail",
    ),
    "candidate_cpacket_stream": (
        "quii_helper.diagnostics.wrapped.tail.candidates",
        "candidate_cpacket_stream",
    ),
    "candidate_embedded_h264": (
        "quii_helper.diagnostics.wrapped.tail.candidates",
        "candidate_embedded_h264",
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
