import struct

from quii_helper.protocols.rbudp.core.models import ParsedKcpConnectResponse


def build_kcp_conv(app_session: int, response_session_id: int) -> int:
    """
    Reproduce the conv composition from P2PTest::OnRespMsg():
    conv = (app_session << 16) | (response_session_id & 0xffff)
    """
    return ((app_session & 0xFFFF) << 16) | (response_session_id & 0xFFFF)


def build_kcp_connect_packet(
    *, src_id: int, channel: int, conn_type: int = 0
) -> bytes:
    """
    Reimplementation of KcpLinkClient::OnConnect().
    """
    packet = bytearray(0x4C)
    struct.pack_into("<I", packet, 0x00, 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x04, 0x4C)
    struct.pack_into("<H", packet, 0x10, 0x0100)
    struct.pack_into("<H", packet, 0x12, 0x0000)
    struct.pack_into("<I", packet, 0x14, 0x00120101)
    struct.pack_into("<I", packet, 0x24, 0x24)
    struct.pack_into("<I", packet, 0x28, src_id & 0xFFFFFFFF)
    packet[0x40] = ((channel & 0x0F) << 4) | ((conn_type & 0x01) << 3)
    return bytes(packet)


def parse_kcp_connect_response(packet: bytes) -> ParsedKcpConnectResponse:
    """
    Parse the fields consumed by KcpLinkClient::OnP2PRequConnect().
    """
    if len(packet) < 0x3C:
        raise ValueError("packet too short for KCP connect response")
    packet_length = struct.unpack_from("<I", packet, 0x04)[0]
    packet_type_flag = struct.unpack_from("<H", packet, 0x12)[0]
    command = struct.unpack_from("<I", packet, 0x14)[0]
    payload_length = struct.unpack_from("<I", packet, 0x24)[0]

    if packet_length >= 0x4C and len(packet) >= packet_length:
        return ParsedKcpConnectResponse(
            packet_length=packet_length,
            packet_type_flag=packet_type_flag,
            command=command,
            result_code=struct.unpack_from("<H", packet, 0x10)[0],
            payload_length=payload_length,
            connect_id=struct.unpack_from("<I", packet, 0x28)[0],
            dest_id=struct.unpack_from("<I", packet, packet_length - 4)[0],
        )

    return ParsedKcpConnectResponse(
        packet_length=packet_length,
        packet_type_flag=packet_type_flag,
        command=command,
        result_code=struct.unpack_from("<I", packet, 0x10)[0],
        payload_length=payload_length,
        connect_id=struct.unpack_from("<I", packet, 0x18)[0],
        dest_id=struct.unpack_from("<I", packet, 0x38)[0],
    )


def build_kcp_disconnect_packet(*, src_id: int, dest_id: int) -> bytes:
    """
    Reimplementation of KcpLinkClient::OnClose().
    """
    packet = bytearray(0x30)
    struct.pack_into("<I", packet, 0x00, 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x04, 0x30)
    struct.pack_into("<H", packet, 0x10, 0x0100)
    struct.pack_into("<H", packet, 0x12, 0x0000)
    struct.pack_into("<I", packet, 0x14, 0x00120102)
    struct.pack_into("<I", packet, 0x24, 0x08)
    struct.pack_into("<I", packet, 0x28, dest_id & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x2C, src_id & 0xFFFFFFFF)
    return bytes(packet)
