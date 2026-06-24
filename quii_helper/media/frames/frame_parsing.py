from quii_helper.media.cpacket import parse_cpacket_header
from quii_helper.media.cpacket.constants import CPACKET_HEADER_LEN


def parse_quii_media_frame_at(payload: bytes, offset: int) -> dict | None:
    header = parse_cpacket_header(payload, offset)
    if header is None:
        return None

    total_len = int(header["total_len"])
    bitstream = payload[offset + CPACKET_HEADER_LEN : offset + total_len]
    nal_offset = bitstream.find(b"\x00\x00\x00\x01")
    if nal_offset < 0:
        nal_offset = bitstream.find(b"\x00\x00\x01")

    return {
        **header,
        "bitstream": bitstream,
        "nal_offset": nal_offset,
    }
