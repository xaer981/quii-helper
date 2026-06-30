from typing import Any

from quii_helper.diagnostics.wrapped.payload.probe_state import (
    payload_embedded_probe_context,
)
from quii_helper.diagnostics.wrapped.tail.probe import CONTAINER_PROBE_MARKER
from quii_helper.media.cpacket.stream import analyze_cpacket_stream
from quii_helper.media.h264.merge.probe_analysis import analyze_annexb_h264


def analyze_payload_embedded_probe(
    payload: bytes,
) -> dict[str, Any] | None:
    context = payload_embedded_probe_context(
        payload, marker=CONTAINER_PROBE_MARKER
    )
    if context is None:
        return None

    idx = int(context["marker_offset"])
    leading = context["leading"]
    start4 = int(context["leading_start_code4_at"])
    start3 = int(context["leading_start_code3_at"])
    leading_annexb: dict[str, Any] = {}
    leading_annexb_payload = context["leading_annexb_payload"]
    if isinstance(leading_annexb_payload, bytes) and leading_annexb_payload:
        leading_annexb = analyze_annexb_h264(leading_annexb_payload)
    if not isinstance(leading, bytes):
        leading = b""

    return {
        "marker_offset": idx,
        "payload_len": len(payload),
        "payload_prefix_hex": payload[:64].hex(),
        "leading_len": len(leading),
        "leading_prefix_hex": leading[:64].hex(),
        "leading_suffix_hex": leading[-64:].hex() if leading else "",
        "leading_start_code4_at": start4,
        "leading_start_code3_at": start3,
        "leading_annexb": leading_annexb,
        "leading_cpacket": analyze_cpacket_stream(leading),
        "payload_cpacket": analyze_cpacket_stream(payload),
        "probe_prefix_hex": payload[idx : idx + 64].hex(),
    }
