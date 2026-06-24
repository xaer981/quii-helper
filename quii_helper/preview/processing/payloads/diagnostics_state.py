from collections.abc import Mapping


def should_find_direct_blob_candidates(
    *, source: str, decoded: Mapping[str, object], phase: str
) -> bool:
    return (
        source == "direct_quii_blob"
        and not bool(decoded["plausible"])
        and phase in ("live", "flush")
    )


def should_record_direct_blob_sample(*, source: str, phase: str) -> bool:
    return phase == "live" and source == "direct_quii_blob"


def should_analyze_wrapped_tail(
    *, source: str, decoded: Mapping[str, object], phase: str
) -> bool:
    return (
        phase == "live"
        and source == "wrapped_quii"
        and bool(decoded["plausible"])
    )
