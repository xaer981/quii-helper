from dataclasses import dataclass

from quii_helper.protocols.rbudp.core.models import ParsedRbUdpWrappedPacket

RBUDP_OUTER_HEADER_LEN = 0x1C


def stream_key_for_packet_words(*, word4: int, word8: int) -> tuple[int, int]:
    return (word4 & 0xFFFFFFFF, word8 & 0xFFFFFFFF)


@dataclass
class RbUdpWrappedFragmentStream:
    marker: int
    word4: int
    word8: int
    start_local_id: int
    remote_id: int
    status_word: int
    rand16: int
    packet_len16: int
    inner_total_length: int
    payload: bytearray
    next_local_id: int
    last_ack_remote_id: int = 0

    @classmethod
    def from_start_packet(
        cls, data: bytes, *, inner_total_length: int
    ) -> "RbUdpWrappedFragmentStream":
        payload = bytearray(data[RBUDP_OUTER_HEADER_LEN:])
        local_id = int.from_bytes(data[0x0C:0x10], "little")
        return cls(
            marker=int.from_bytes(data[0x00:0x04], "little"),
            word4=int.from_bytes(data[0x04:0x08], "little"),
            word8=int.from_bytes(data[0x08:0x0C], "little"),
            start_local_id=local_id,
            remote_id=int.from_bytes(data[0x10:0x14], "little"),
            status_word=int.from_bytes(data[0x14:0x18], "little"),
            rand16=int.from_bytes(data[0x18:0x1A], "little"),
            packet_len16=int.from_bytes(data[0x1A:0x1C], "little"),
            inner_total_length=inner_total_length,
            payload=payload,
            next_local_id=local_id + len(payload),
        )

    @classmethod
    def from_remainder(
        cls,
        parent: "RbUdpWrappedFragmentStream",
        *,
        remainder: bytes,
        previous_total_length: int,
        inner_total_length: int,
    ) -> "RbUdpWrappedFragmentStream":
        next_start_local_id = parent.start_local_id + previous_total_length
        next_local_id = next_start_local_id + len(remainder)
        return cls(
            marker=parent.marker,
            word4=parent.word4,
            word8=parent.word8,
            start_local_id=next_start_local_id,
            remote_id=parent.remote_id,
            status_word=parent.status_word,
            rand16=parent.rand16,
            packet_len16=parent.packet_len16,
            inner_total_length=inner_total_length,
            payload=bytearray(remainder),
            next_local_id=next_local_id,
            last_ack_remote_id=next_local_id,
        )

    @property
    def key(self) -> tuple[int, int]:
        return stream_key_for_packet_words(word4=self.word4, word8=self.word8)

    @property
    def have(self) -> int:
        return len(self.payload)

    @property
    def missing(self) -> int:
        return max(0, self.inner_total_length - len(self.payload))

    @property
    def inner_end_local_id(self) -> int:
        return self.start_local_id + self.inner_total_length

    def append_payload(self, *, local_id: int, payload: bytes) -> None:
        self.payload.extend(payload)
        self.next_local_id = local_id + len(payload)

    def split_complete_payload(self) -> tuple[bytes, bytes]:
        full_payload = bytes(self.payload)
        return (
            full_payload[: self.inner_total_length],
            full_payload[self.inner_total_length :],
        )

    def to_wrapped_packet(
        self, *, local_id: int, remote_id: int, inner_packet: bytes
    ) -> ParsedRbUdpWrappedPacket:
        return ParsedRbUdpWrappedPacket(
            marker=self.marker,
            word4=self.word4,
            word8=self.word8,
            local_id=local_id,
            remote_id=remote_id,
            status_word=self.status_word,
            rand16=self.rand16,
            packet_len16=self.packet_len16,
            inner_total_length=self.inner_total_length,
            tag8=b"",
            inner_packet=inner_packet,
        )
