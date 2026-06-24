from dataclasses import dataclass

from quii_helper.protocols.rbudp.fragments.stream import (
    RBUDP_OUTER_HEADER_LEN,
    stream_key_for_packet_words,
)


@dataclass(frozen=True)
class RbUdpFragmentPacket:
    marker: int
    word4: int
    word8: int
    local_id: int
    remote_id: int
    status_word: int
    rand16: int
    packet_len16: int
    payload: bytes
    inner_total_length: int = 0

    @classmethod
    def parse(cls, data: bytes) -> "RbUdpFragmentPacket":
        if len(data) < RBUDP_OUTER_HEADER_LEN:
            raise ValueError("packet too short for RB UDP fragment packet")
        inner_total_length = (
            int.from_bytes(data[0x20:0x24], "little")
            if len(data) >= 0x24
            else 0
        )
        return cls(
            marker=int.from_bytes(data[0x00:0x04], "little"),
            word4=int.from_bytes(data[0x04:0x08], "little"),
            word8=int.from_bytes(data[0x08:0x0C], "little"),
            local_id=int.from_bytes(data[0x0C:0x10], "little"),
            remote_id=int.from_bytes(data[0x10:0x14], "little"),
            status_word=int.from_bytes(data[0x14:0x18], "little"),
            rand16=int.from_bytes(data[0x18:0x1A], "little"),
            packet_len16=int.from_bytes(data[0x1A:0x1C], "little"),
            payload=data[RBUDP_OUTER_HEADER_LEN:],
            inner_total_length=inner_total_length,
        )

    @property
    def stream_key(self) -> tuple[int, int]:
        return stream_key_for_packet_words(word4=self.word4, word8=self.word8)
