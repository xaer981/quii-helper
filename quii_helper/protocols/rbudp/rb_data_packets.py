import struct

from quii_helper.protocols.rbudp.models import ParsedRbDataPacket


def build_rb_data_packet(
    *, payload: bytes, src_id: int, dest_id: int, seq: int
) -> bytes:
    """
    Reimplementation of BuildRbRespHead() as used by KcpLinkConn::Send().
    """
    total_len = 0x38 + len(payload)
    packet = bytearray(total_len)
    struct.pack_into("<I", packet, 0x00, 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x04, total_len)
    struct.pack_into("<H", packet, 0x10, 0x0100)
    struct.pack_into("<H", packet, 0x12, 0x0000)
    struct.pack_into("<I", packet, 0x14, 0x00120103)
    struct.pack_into("<I", packet, 0x18, seq & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x24, total_len - 0x28)
    struct.pack_into("<I", packet, 0x28, dest_id & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x2C, src_id & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x30, (total_len - 0x28) - 0x10)
    packet[0x38:] = payload
    return bytes(packet)


def build_rb_data_ack_packet(
    *, payload_length: int, seq: int, src_id: int, dest_id: int
) -> bytes:
    """
    Reimplementation of BuildRbResp()
    as used by KcpLinkServer::OnP2PRequData().
    """
    packet = bytearray(0x38)
    struct.pack_into("<I", packet, 0x00, 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x04, 0x38)
    struct.pack_into("<H", packet, 0x10, 0x0100)
    struct.pack_into("<H", packet, 0x12, 0x0001)
    struct.pack_into("<I", packet, 0x14, 0x00120103)
    struct.pack_into("<I", packet, 0x18, seq & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x24, 0x10)
    struct.pack_into("<I", packet, 0x28, dest_id & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x2C, src_id & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x30, payload_length & 0xFFFFFFFF)
    return bytes(packet)


def parse_rb_data_packet(packet: bytes) -> ParsedRbDataPacket:
    """
    Parse both ordinary RB data packets and their ACK-only counterparts.
    """
    if len(packet) < 0x38:
        raise ValueError("packet too short for RB data packet")

    packet_length = struct.unpack_from("<I", packet, 0x04)[0]
    payload = packet[0x38:packet_length]
    return ParsedRbDataPacket(
        packet_length=packet_length,
        packet_type_flag=struct.unpack_from("<H", packet, 0x12)[0],
        command=struct.unpack_from("<I", packet, 0x14)[0],
        seq=struct.unpack_from("<I", packet, 0x18)[0],
        payload_length=struct.unpack_from("<I", packet, 0x24)[0],
        dest_id=struct.unpack_from("<I", packet, 0x28)[0],
        src_id=struct.unpack_from("<I", packet, 0x2C)[0],
        body_length_field=struct.unpack_from("<I", packet, 0x30)[0],
        payload=payload,
    )
