import struct

from quii_helper.protocols.rbudp.core.models import ParsedRbUdpControlPacket


def parse_rb_udp_control_packet(packet: bytes) -> ParsedRbUdpControlPacket:
    """
    Parse the fixed 28-byte RB-UDP control/ack frames seen after P2P transport.
    """
    if len(packet) != 28:
        raise ValueError("RB UDP control packet must be exactly 28 bytes")
    marker = struct.unpack_from("<I", packet, 0x00)[0]
    if marker != 0xFFABEFC1:
        raise ValueError("invalid RB UDP control marker")
    return ParsedRbUdpControlPacket(
        marker=marker,
        word4=struct.unpack_from("<I", packet, 0x04)[0],
        word8=struct.unpack_from("<I", packet, 0x08)[0],
        local_id=struct.unpack_from("<I", packet, 0x0C)[0],
        remote_id=struct.unpack_from("<I", packet, 0x10)[0],
        status_word=struct.unpack_from("<I", packet, 0x14)[0],
        rand16=struct.unpack_from("<H", packet, 0x18)[0],
        packet_len16=struct.unpack_from("<H", packet, 0x1A)[0],
    )


def build_rb_udp_control_packet(
    *,
    word4: int,
    word8: int,
    local_id: int,
    remote_id: int,
    status_word: int,
    nonce: int,
) -> bytes:
    packet = bytearray(28)
    struct.pack_into("<I", packet, 0x00, 0xFFABEFC1)
    struct.pack_into("<I", packet, 0x04, word4 & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x08, word8 & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x0C, local_id & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x10, remote_id & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x14, status_word & 0xFFFFFFFF)
    struct.pack_into("<H", packet, 0x1A, len(packet))
    struct.pack_into("<H", packet, 0x18, native_checksum16(packet))
    return bytes(packet)


def native_checksum16(packet: bytes | bytearray) -> int:
    """
    Match libqv-p2p-v2.so TDK_F_SYS_CheckSum().

    Native zeros the checksum field before summing 16-bit little-endian words,
    folds carry bits, then stores the one's complement at offset 0x18.
    """
    checksum_packet = bytearray(packet)
    checksum_packet[0x18] = 0
    checksum_packet[0x19] = 0
    total = 0
    for offset in range(0, len(checksum_packet) - 1, 2):
        total += struct.unpack_from("<H", checksum_packet, offset)[0]
    if len(checksum_packet) % 2:
        total += checksum_packet[-1]
    folded = (total >> 16) + (total & 0xFFFF)
    return (~(folded + (folded >> 16))) & 0xFFFF
