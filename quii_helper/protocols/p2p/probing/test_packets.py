import random
import struct

from quii_helper.protocols.p2p.models import ParsedP2PTestResponse


def parse_p2p_test_response(packet: bytes) -> ParsedP2PTestResponse:
    """
    Parse the fields used by
    P2PTest::OnRespMsg() from a returned KcpLinkPacket.

    Observed offsets:
    - 0x20: int32 result
    - 0x28: NUL-terminated session-flag string
    - 0x70: NUL-terminated address string
    - 0x80: uint16 port
    - 0x82: uint16 status
    - 0x84: uint32 test_id / connection type
    """
    if (
        len(packet) >= 0xA4
        and struct.unpack_from("<I", packet, 0x30)[0] == 0x00120002
    ):
        packet_type_flag = struct.unpack_from("<H", packet, 0x2E)[0]
        return ParsedP2PTestResponse(
            result_code=0 if packet_type_flag == 1 else 1,
            session_flag=_read_cstr(packet, 0x44, 0x40),
            address=_read_cstr(packet, 0x8C, 0x10),
            port=struct.unpack_from("<H", packet, 0x9C)[0],
            status_code=0 if packet_type_flag == 1 else packet_type_flag,
            test_id=struct.unpack_from("<I", packet, 0xA0)[0],
        )

    if len(packet) < 0x88:
        raise ValueError("packet too short for P2P test response")

    return ParsedP2PTestResponse(
        result_code=struct.unpack_from("<I", packet, 0x20)[0],
        session_flag=_read_cstr(packet, 0x28, 0x40),
        address=_read_cstr(packet, 0x70, 0x10),
        port=struct.unpack_from("<H", packet, 0x80)[0],
        status_code=struct.unpack_from("<H", packet, 0x82)[0],
        test_id=struct.unpack_from("<I", packet, 0x84)[0],
    )


def build_p2p_test_packet(
    *,
    rb_seq: int,
    probe_seq: int,
    session_flag: str,
    response_session_id: int,
    local_udp_port: int,
    target_ip: str,
    target_udp_port: int,
    test_mode: int,
    rand16: int | None = None,
) -> bytes:
    """
    Reimplementation of P2PTest::SendTestMsg() payload builder.

    Native uses the same 0xA4 transport frame shape as later OnRequMsg /
    SendActiveMsg packets, but with filled remote-ip/remote-port/tail fields.
    """
    if len(session_flag.encode("utf-8")) > 0x40:
        raise ValueError("session_flag must fit into 0x40 bytes")
    if len(target_ip.encode("utf-8")) >= 0x10:
        raise ValueError("target_ip must fit into 0x10 bytes including NUL")

    packet = bytearray(0xA4)

    # Minimal observed RB header footprint from native P2PTest::SendTestMsg().
    struct.pack_into("<I", packet, 0x00, 0xFFABEFC1)
    struct.pack_into("<H", packet, 0x1A, 0x00A4)
    struct.pack_into("<I", packet, 0x1C, 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x20, 0x88)
    struct.pack_into(
        "<H",
        packet,
        0x2A,
        (rand16 if rand16 is not None else random.randrange(0x10000)) & 0xFFFF,
    )
    struct.pack_into("<H", packet, 0x2C, 0x100)
    struct.pack_into("<H", packet, 0x2E, 0x0000)
    struct.pack_into("<I", packet, 0x30, 0x120002)
    struct.pack_into("<I", packet, 0x38, probe_seq & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x40, 0x60)

    session_flag_bytes = session_flag.encode("utf-8")
    packet[0x44 : 0x44 + len(session_flag_bytes)] = session_flag_bytes

    struct.pack_into("<H", packet, 0x84, 0)
    struct.pack_into("<H", packet, 0x86, local_udp_port & 0xFFFF)
    struct.pack_into("<H", packet, 0x88, 0)
    struct.pack_into("<H", packet, 0x8A, local_udp_port & 0xFFFF)

    target_ip_bytes = target_ip.encode("utf-8")
    packet[0x8C : 0x8C + len(target_ip_bytes)] = target_ip_bytes

    struct.pack_into("<H", packet, 0x9C, target_udp_port & 0xFFFF)
    struct.pack_into("<I", packet, 0xA0, test_mode & 0xFFFFFFFF)
    return bytes(packet)


def _read_cstr(packet: bytes, offset: int, size: int) -> str:
    raw = packet[offset : offset + size]
    return raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
