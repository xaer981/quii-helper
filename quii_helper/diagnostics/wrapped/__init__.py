"""Wrapped payload and tail diagnostics."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "analyze_partial_wrapped_inner": (
        "quii_helper.diagnostics.wrapped.inner_analysis",
        "analyze_partial_wrapped_inner",
    ),
    "analyze_payload_embedded_probe": (
        "quii_helper.diagnostics.wrapped.tail_candidates",
        "analyze_payload_embedded_probe",
    ),
    "analyze_wrapped_quii_tail": (
        "quii_helper.diagnostics.wrapped.tail_analysis",
        "analyze_wrapped_quii_tail",
    ),
    "candidate_container_probe": (
        "quii_helper.diagnostics.wrapped.tail_candidates",
        "candidate_container_probe",
    ),
    "candidate_container_probe_from_partial_payload": (
        "quii_helper.diagnostics.wrapped.tail_candidates",
        "candidate_container_probe_from_partial_payload",
    ),
    "candidate_cpacket_from_decrypted_tail": (
        "quii_helper.diagnostics.wrapped.tail_candidates",
        "candidate_cpacket_from_decrypted_tail",
    ),
    "candidate_cpacket_stream": (
        "quii_helper.diagnostics.wrapped.tail_candidates",
        "candidate_cpacket_stream",
    ),
    "candidate_embedded_h264": (
        "quii_helper.diagnostics.wrapped.tail_candidates",
        "candidate_embedded_h264",
    ),
    "decrypt_wrapped_quii_tail_bytes": (
        "quii_helper.diagnostics.wrapped.tail_analysis",
        "decrypt_wrapped_quii_tail_bytes",
    ),
    "dump_partial_tail_artifacts": (
        "quii_helper.diagnostics.wrapped.tail_candidates",
        "dump_partial_tail_artifacts",
    ),
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
