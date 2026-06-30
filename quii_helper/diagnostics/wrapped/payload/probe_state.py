from typing import Any


def payload_embedded_probe_context(
    payload: bytes, *, marker: bytes
) -> dict[str, Any] | None:
    marker_offset = payload.find(marker)
    if marker_offset < 0:
        return None

    leading = payload[:marker_offset]
    start4 = leading.find(b"\x00\x00\x00\x01")
    start3 = leading.find(b"\x00\x00\x01")
    return {
        "marker_offset": marker_offset,
        "leading": leading,
        "leading_start_code4_at": start4,
        "leading_start_code3_at": start3,
        "leading_annexb_payload": leading_annexb_payload(
            leading, start4=start4, start3=start3
        ),
    }


def leading_annexb_payload(
    leading: bytes, *, start4: int, start3: int
) -> bytes:
    if start4 >= 0:
        return leading[start4:]
    if start3 < 0:
        return b""
    if start3 > 0 and leading[start3 - 1] == 0:
        return leading[start3 - 1 :]
    return leading[start3:]
