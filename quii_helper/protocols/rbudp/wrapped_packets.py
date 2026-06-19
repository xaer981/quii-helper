import struct

from quii_helper.protocols.rbudp.control_packets import native_checksum16
from quii_helper.protocols.rbudp.models import ParsedRbUdpWrappedPacket


def parse_rb_udp_wrapped_packet(packet: bytes) -> ParsedRbUdpWrappedPacket:
    """
    Parse RB-UDP packets that wrap an inner logical packet.
    """
    if len(packet) < 0x1C:
        raise ValueError("packet too short for RB UDP wrapped packet")
    marker = struct.unpack_from("<I", packet, 0x00)[0]
    if marker != 0xFFABEFC1:
        raise ValueError("invalid RB UDP wrapped marker")
    if (
        len(packet) >= 0x24
        and struct.unpack_from("<I", packet, 0x1C)[0] == 0xFFFFFFFF
    ):
        inner_total_length = struct.unpack_from("<I", packet, 0x20)[0]
        if inner_total_length < 0x10:
            raise ValueError("inner packet length too small")
        direct_end = 0x1C + inner_total_length
        if direct_end > len(packet):
            raise ValueError(
                "direct wrapped payload size does not match inner length"
            )
        return ParsedRbUdpWrappedPacket(
            marker=marker,
            word4=struct.unpack_from("<I", packet, 0x04)[0],
            word8=struct.unpack_from("<I", packet, 0x08)[0],
            local_id=struct.unpack_from("<I", packet, 0x0C)[0],
            remote_id=struct.unpack_from("<I", packet, 0x10)[0],
            status_word=struct.unpack_from("<I", packet, 0x14)[0],
            rand16=struct.unpack_from("<H", packet, 0x18)[0],
            packet_len16=struct.unpack_from("<H", packet, 0x1A)[0],
            inner_total_length=inner_total_length,
            tag8=b"",
            inner_packet=packet[0x1C:direct_end],
        )
    if len(packet) < 0x24 + 8:
        raise ValueError("packet too short for tagged RB UDP wrapped packet")
    inner_total_length = struct.unpack_from("<I", packet, 0x20)[0]
    if inner_total_length < 0x10:
        raise ValueError("inner packet length too small")
    payload = packet[0x24:]
    if len(payload) != 8 + (inner_total_length - 0x10):
        raise ValueError("wrapped payload size does not match inner length")
    tag8 = payload[:8]
    inner_packet = bytearray(inner_total_length)
    struct.pack_into("<I", inner_packet, 0x00, 0xFFFFFFFF)
    struct.pack_into("<I", inner_packet, 0x04, inner_total_length)
    inner_packet[0x10:] = payload[8:]
    return ParsedRbUdpWrappedPacket(
        marker=marker,
        word4=struct.unpack_from("<I", packet, 0x04)[0],
        word8=struct.unpack_from("<I", packet, 0x08)[0],
        local_id=struct.unpack_from("<I", packet, 0x0C)[0],
        remote_id=struct.unpack_from("<I", packet, 0x10)[0],
        status_word=struct.unpack_from("<I", packet, 0x14)[0],
        rand16=struct.unpack_from("<H", packet, 0x18)[0],
        packet_len16=struct.unpack_from("<H", packet, 0x1A)[0],
        inner_total_length=inner_total_length,
        tag8=tag8,
        inner_packet=bytes(inner_packet),
    )


def build_rb_udp_wrapped_packet(
    inner_packet: bytes,
    *,
    word4: int,
    word8: int,
    local_id: int,
    remote_id: int,
    status_word: int,
    nonce: int,
    tag8: bytes,
) -> bytes:
    """
    Build the RB-UDP wrapper used around logical packets after the P2P stage.
    """
    if len(tag8) != 8:
        raise ValueError("tag8 must be exactly 8 bytes")
    if len(inner_packet) < 0x10:
        raise ValueError("inner packet too short for RB UDP wrapping")
    total = 0x24 + 8 + (len(inner_packet) - 0x10)
    packet = bytearray(total)
    struct.pack_into("<I", packet, 0x00, 0xFFABEFC1)
    struct.pack_into("<I", packet, 0x04, word4 & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x08, word8 & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x0C, local_id & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x10, remote_id & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x14, status_word & 0xFFFFFFFF)
    struct.pack_into("<H", packet, 0x1A, total & 0xFFFF)
    struct.pack_into("<I", packet, 0x1C, 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x20, len(inner_packet) & 0xFFFFFFFF)
    packet[0x24:0x2C] = tag8
    packet[0x2C:] = inner_packet[0x10:]
    # Native TDK_F_RB_UDP_PR_SendRbUdpData checksums only the 0x1c-byte
    # RBUDP header, even when the datagram carries wrapped payload bytes.
    struct.pack_into("<H", packet, 0x18, native_checksum16(packet[:0x1C]))
    return bytes(packet)


def classify_rb_udp_packet(packet: bytes) -> str:
    if len(packet) == 28:
        return "control28"
    if (
        len(packet) >= 0x24
        and struct.unpack_from("<I", packet, 0x00)[0] == 0xFFABEFC1
    ):
        if struct.unpack_from("<I", packet, 0x1C)[0] == 0xFFFFFFFF:
            inner_len = struct.unpack_from("<I", packet, 0x20)[0]
            if len(packet) >= 0x1C + inner_len:
                return "wrapped_direct"
    if (
        len(packet) >= 0x24 + 8
        and struct.unpack_from("<I", packet, 0x00)[0] == 0xFFABEFC1
    ):
        inner_len = struct.unpack_from("<I", packet, 0x20)[0]
        if len(packet) == 0x24 + 8 + max(0, inner_len - 0x10):
            return "wrapped"
    return "unknown"
