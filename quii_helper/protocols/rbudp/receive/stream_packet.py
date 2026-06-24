from dataclasses import dataclass

RBUDP_RECEIVE_STREAM_HEADER_LEN = 0x1C


@dataclass(frozen=True)
class RbUdpReceiveStreamPacket:
    marker: int
    word4: int
    word8: int
    local_id: int
    remote_id: int
    status_word: int
    rand16: int
    packet_len16: int
    payload: bytes

    @property
    def stream_key(self) -> tuple[int, int]:
        return (self.word4, self.word8)


def parse_receive_stream_packet(
    data: bytes,
) -> RbUdpReceiveStreamPacket | None:
    if len(data) < RBUDP_RECEIVE_STREAM_HEADER_LEN:
        return None
    return RbUdpReceiveStreamPacket(
        marker=int.from_bytes(data[0x00:0x04], "little"),
        word4=int.from_bytes(data[0x04:0x08], "little"),
        word8=int.from_bytes(data[0x08:0x0C], "little"),
        local_id=int.from_bytes(data[0x0C:0x10], "little"),
        remote_id=int.from_bytes(data[0x10:0x14], "little"),
        status_word=int.from_bytes(data[0x14:0x18], "little"),
        rand16=int.from_bytes(data[0x18:0x1A], "little"),
        packet_len16=int.from_bytes(data[0x1A:0x1C], "little"),
        payload=data[RBUDP_RECEIVE_STREAM_HEADER_LEN:],
    )
