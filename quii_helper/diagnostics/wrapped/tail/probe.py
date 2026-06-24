from quii_helper.diagnostics.wrapped.tail.probe_state import (
    container_probe_context,
    container_probe_without_marker,
    empty_decrypted_tail_analysis,
)
from quii_helper.media.cpacket.stream import analyze_cpacket_stream
from quii_helper.protocols.quii.blob import safe_text_preview

CONTAINER_PROBE_MARKER = bytes.fromhex("c0034002")


def analyze_decrypted_tail(decrypted: bytes) -> dict:
    if not decrypted:
        return empty_decrypted_tail_analysis()

    start_code_offsets4 = find_start_code_offsets(
        decrypted, marker=b"\x00\x00\x00\x01"
    )
    start_code_offsets3 = find_start_code_offsets(
        decrypted, marker=b"\x00\x00\x01", exclude_four_byte=True
    )
    container_probe = container_probe_for_first_h264(
        decrypted, start_code_offsets4
    )

    return {
        "decrypted_prefix": decrypted[:128].hex(),
        "decrypted_text_preview": safe_text_preview(decrypted[:160]),
        "h264_start_codes": decrypted.count(b"\x00\x00\x00\x01"),
        "annexb_start_codes": decrypted.count(b"\x00\x00\x01"),
        "h264_start_offsets": start_code_offsets4,
        "annexb_start_offsets": start_code_offsets3,
        "first_h264_offset": container_probe["first_marker_offset"],
        "pre_h264_prefix_hex": container_probe["pre_marker_hex"],
        "pre_h264_dwords_le": container_probe["pre_marker_dwords_le"],
        "pre_h264_dwords_be": container_probe["pre_marker_dwords_be"],
        "pre_h264_tail_hex": container_probe["pre_marker_tail_hex"],
        "post_h264_prefix_hex": container_probe["post_marker_prefix_hex"],
        "container_probe": (
            {}
            if container_probe["first_marker_offset"] < 0
            else container_probe
        ),
        "cpacket_analysis": analyze_cpacket_stream(decrypted),
    }


def find_start_code_offsets(
    blob: bytes,
    *,
    marker: bytes,
    exclude_four_byte: bool = False,
    limit: int = 8,
) -> list[int]:
    offsets: list[int] = []
    cursor = 0
    while len(offsets) < limit:
        idx = blob.find(marker, cursor)
        if idx < 0:
            break
        if not exclude_four_byte or idx == 0 or blob[idx - 1] != 0x00:
            offsets.append(idx)
        cursor = idx + len(marker)
    return offsets


def container_probe_for_first_h264(
    decrypted: bytes, start_code_offsets4: list[int]
) -> dict:
    if not start_code_offsets4:
        return container_probe_without_marker()

    first_h264_offset = start_code_offsets4[0]
    return container_probe_context(
        decrypted, first_h264_offset, marker=CONTAINER_PROBE_MARKER
    )


def is_container_probe_before_start_code(
    blob: bytes, start_code_offset: int
) -> bool:
    return start_code_offset >= len(CONTAINER_PROBE_MARKER) and (
        blob[
            start_code_offset - len(CONTAINER_PROBE_MARKER) : start_code_offset
        ]
        == CONTAINER_PROBE_MARKER
    )
