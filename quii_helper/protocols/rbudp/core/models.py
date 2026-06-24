from dataclasses import dataclass


@dataclass
class ParsedKcpConnectResponse:
    packet_length: int
    packet_type_flag: int
    command: int
    result_code: int
    payload_length: int
    connect_id: int
    dest_id: int

    @property
    def ok(self) -> bool:
        return self.packet_type_flag == 1 and self.result_code == 0


@dataclass
class ParsedRbDataPacket:
    packet_length: int
    packet_type_flag: int
    command: int
    seq: int
    payload_length: int
    dest_id: int
    src_id: int
    body_length_field: int
    payload: bytes

    @property
    def is_ack(self) -> bool:
        return self.packet_type_flag == 1


@dataclass
class ParsedPacketFrame:
    command: int
    raw: bytes


@dataclass
class ParsedPacketDispatch:
    connect: ParsedKcpConnectResponse | None = None
    disconnect: ParsedPacketFrame | None = None
    data: ParsedRbDataPacket | None = None


@dataclass
class ParsedRbUdpControlPacket:
    marker: int
    word4: int
    word8: int
    local_id: int
    remote_id: int
    status_word: int
    rand16: int
    packet_len16: int


@dataclass
class ParsedRbUdpWrappedPacket:
    marker: int
    word4: int
    word8: int
    local_id: int
    remote_id: int
    status_word: int
    rand16: int
    packet_len16: int
    inner_total_length: int
    tag8: bytes
    inner_packet: bytes
