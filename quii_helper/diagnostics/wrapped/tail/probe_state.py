def empty_decrypted_tail_analysis() -> dict:
    return {
        "decrypted_prefix": "",
        "decrypted_text_preview": "",
        "h264_start_codes": 0,
        "annexb_start_codes": 0,
        "h264_start_offsets": [],
        "annexb_start_offsets": [],
        "first_h264_offset": -1,
        "pre_h264_prefix_hex": "",
        "pre_h264_dwords_le": [],
        "pre_h264_dwords_be": [],
        "pre_h264_tail_hex": "",
        "post_h264_prefix_hex": "",
        "container_probe": {},
        "cpacket_analysis": {},
    }


def container_probe_without_marker() -> dict:
    return {
        "first_marker_offset": -1,
        "pre_marker_hex": "",
        "pre_marker_tail_hex": "",
        "pre_marker_dwords_le": [],
        "pre_marker_dwords_be": [],
        "post_marker_prefix_hex": "",
        "looks_like_false_h264_container": False,
    }


def dwords_from_bytes(blob: bytes, byteorder: str) -> list[int]:
    aligned_len = len(blob) - (len(blob) % 4)
    return [
        int.from_bytes(blob[i : i + 4], byteorder)
        for i in range(0, aligned_len, 4)
    ]


def container_probe_context(
    decrypted: bytes, first_marker_offset: int, *, marker: bytes
) -> dict:
    pre_start = max(0, first_marker_offset - 16)
    pre_marker = decrypted[pre_start:first_marker_offset]
    post_marker = decrypted[first_marker_offset : first_marker_offset + 32]
    pre_marker_tail_hex = pre_marker[-4:].hex() if pre_marker else ""
    return {
        "first_marker_offset": first_marker_offset,
        "pre_marker_hex": pre_marker.hex(),
        "pre_marker_tail_hex": pre_marker_tail_hex,
        "pre_marker_dwords_le": dwords_from_bytes(pre_marker, "little"),
        "pre_marker_dwords_be": dwords_from_bytes(pre_marker, "big"),
        "post_marker_prefix_hex": post_marker.hex(),
        "looks_like_false_h264_container": (
            pre_marker_tail_hex == marker.hex()
        ),
    }
