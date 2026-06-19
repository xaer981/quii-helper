from quii_helper.diagnostics.wrapped.tail_probe import CONTAINER_PROBE_MARKER
from quii_helper.media.annexb_probe_analysis import analyze_annexb_h264
from quii_helper.media.cpacket_stream import analyze_cpacket_stream


def analyze_payload_embedded_probe(payload: bytes) -> dict | None:
    idx = payload.find(CONTAINER_PROBE_MARKER)
    if idx < 0:
        return None

    leading = payload[:idx]
    start4 = leading.find(b"\x00\x00\x00\x01")
    start3 = leading.find(b"\x00\x00\x01")
    leading_annexb = {}
    if start4 >= 0:
        leading_annexb = analyze_annexb_h264(leading[start4:])
    elif start3 >= 0:
        leading_annexb = analyze_annexb_h264(
            leading[start3 - 1 :]
            if start3 > 0 and leading[start3 - 1] == 0
            else leading[start3:]
        )

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
