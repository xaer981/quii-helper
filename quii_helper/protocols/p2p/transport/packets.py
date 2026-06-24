import random
import struct

from quii_helper.protocols.p2p.models import ParsedP2PTransportFrame


def parse_p2p_transport_frame(packet: bytes) -> ParsedP2PTransportFrame:
    if len(packet) < 0xA4:
        raise ValueError("packet too short for P2P transport frame")
    if struct.unpack_from("<I", packet, 0x30)[0] != 0x00120002:
        raise ValueError("packet is not a P2P transport/test frame")

    return ParsedP2PTransportFrame(
        marker=struct.unpack_from("<I", packet, 0x00)[0],
        packet_type_flag=struct.unpack_from("<H", packet, 0x2E)[0],
        command=struct.unpack_from("<I", packet, 0x30)[0],
        seq=struct.unpack_from("<I", packet, 0x38)[0],
        session_flag=_read_cstr(packet, 0x44, 0x40),
        remote_ip=_read_cstr(packet, 0x8C, 0x10),
        remote_port=struct.unpack_from("<H", packet, 0x9C)[0],
        tail_code=struct.unpack_from("<I", packet, 0xA0)[0],
    )


def build_p2p_transport_packet(
    *,
    session_flag: str,
    seq: int,
    local_udp_port: int,
    remote_ip: str,
    remote_port: int,
    tail_code: int,
    packet_type_flag: int = 0,
    rand16: int | None = None,
) -> bytes:
    packet = bytearray(0xA4)
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
    struct.pack_into("<H", packet, 0x2C, 0x0100)
    struct.pack_into("<H", packet, 0x2E, packet_type_flag & 0xFFFF)
    struct.pack_into("<I", packet, 0x30, 0x00120002)
    struct.pack_into("<I", packet, 0x38, seq & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x40, 0x60)

    session_flag_bytes = session_flag.encode("utf-8")
    packet[0x44 : 0x44 + len(session_flag_bytes)] = session_flag_bytes

    struct.pack_into("<H", packet, 0x84, 0)
    struct.pack_into("<H", packet, 0x86, local_udp_port & 0xFFFF)
    struct.pack_into("<H", packet, 0x88, 0)
    struct.pack_into("<H", packet, 0x8A, local_udp_port & 0xFFFF)

    remote_ip_bytes = remote_ip.encode("utf-8")
    packet[0x8C : 0x8C + len(remote_ip_bytes)] = remote_ip_bytes
    struct.pack_into("<H", packet, 0x9C, remote_port & 0xFFFF)
    struct.pack_into("<I", packet, 0xA0, tail_code & 0xFFFFFFFF)
    return bytes(packet)


def build_p2p_active_packet(
    *,
    session_flag: str,
    seq: int,
    local_udp_port: int,
    tail_code: int,
) -> bytes:
    return build_p2p_transport_packet(
        session_flag=session_flag,
        seq=seq,
        local_udp_port=local_udp_port,
        remote_ip="",
        remote_port=0,
        tail_code=tail_code,
        packet_type_flag=0,
    )


def build_p2p_transport_ack(
    frame: ParsedP2PTransportFrame, *, local_udp_port: int
) -> bytes:
    return build_p2p_transport_packet(
        session_flag=frame.session_flag,
        seq=frame.seq,
        local_udp_port=local_udp_port,
        remote_ip=frame.remote_ip,
        remote_port=frame.remote_port,
        tail_code=frame.tail_code,
        packet_type_flag=1,
    )


def _read_cstr(packet: bytes, offset: int, size: int) -> str:
    raw = packet[offset : offset + size]
    return raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
