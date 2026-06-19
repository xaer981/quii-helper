import struct

from quii_helper.protocols.rbudp.kcp_connect_packets import (
    parse_kcp_connect_response,
)
from quii_helper.protocols.rbudp.models import (
    ParsedPacketDispatch,
    ParsedPacketFrame,
)
from quii_helper.protocols.rbudp.rb_data_packets import parse_rb_data_packet


def iter_kcp_packet_frames(buffer: bytes) -> list[ParsedPacketFrame]:
    """
    Reimplementation of KcpLinkClient::DoRecvData().
    """
    frames: list[ParsedPacketFrame] = []
    offset = 0
    total = len(buffer)

    while offset < total:
        if total - offset < 0x10:
            raise ValueError("trailing partial packet header in KCP buffer")
        if struct.unpack_from("<I", buffer, offset)[0] != 0xFFFFFFFF:
            raise ValueError(f"invalid packet marker at offset {offset:#x}")

        packet_len = struct.unpack_from("<I", buffer, offset + 0x04)[0]
        if packet_len == 0:
            raise ValueError(f"zero packet length at offset {offset:#x}")
        if packet_len > 20 * 1024 * 1024:
            raise ValueError(
                f"unreasonable packet length {packet_len} "
                f"at offset {offset:#x}"
            )
        end = offset + packet_len
        if end > total:
            raise ValueError("truncated RB packet in KCP buffer")

        raw = buffer[offset:end]
        command = struct.unpack_from("<I", raw, 0x14)[0]
        frames.append(ParsedPacketFrame(command=command, raw=raw))
        offset = end

    return frames


def pop_complete_kcp_packet_frames(
    buffer: bytearray,
) -> list[ParsedPacketFrame]:
    """
    Incremental variant of KcpLinkClient::DoRecvData().

    Native keeps incomplete packet bytes in Buffer and returns until more RBUDP
    data arrives. This function mirrors that behavior by popping only complete
    frames and leaving a trailing partial frame in ``buffer``.
    """
    frames: list[ParsedPacketFrame] = []

    while len(buffer) >= 0x10:
        if struct.unpack_from("<I", buffer, 0)[0] != 0xFFFFFFFF:
            raise ValueError("invalid packet marker at stream head")

        packet_len = struct.unpack_from("<I", buffer, 0x04)[0]
        if packet_len == 0:
            raise ValueError("zero packet length at stream head")
        if packet_len > 20 * 1024 * 1024:
            raise ValueError(f"unreasonable packet length {packet_len}")
        if len(buffer) < packet_len:
            break

        raw = bytes(buffer[:packet_len])
        del buffer[:packet_len]
        command = struct.unpack_from("<I", raw, 0x14)[0]
        frames.append(ParsedPacketFrame(command=command, raw=raw))

    return frames


def parse_kcp_packet_frame(
    frame: ParsedPacketFrame | bytes,
) -> ParsedPacketDispatch:
    if isinstance(frame, bytes):
        frame = ParsedPacketFrame(
            command=struct.unpack_from("<I", frame, 0x14)[0], raw=frame
        )

    if frame.command == 0x120101:
        return ParsedPacketDispatch(
            connect=parse_kcp_connect_response(frame.raw)
        )
    if frame.command == 0x120102:
        return ParsedPacketDispatch(disconnect=frame)
    if frame.command == 0x120103:
        return ParsedPacketDispatch(data=parse_rb_data_packet(frame.raw))
    raise ValueError(f"unsupported KCP/RB command: {frame.command:#x}")
