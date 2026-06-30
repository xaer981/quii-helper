from quii_helper.protocols.rbudp.receive.stream_packet import (
    RBUDP_RECEIVE_STREAM_HEADER_LEN,
    parse_receive_stream_packet,
)


def _packet(payload: bytes = b"payload") -> bytes:
    header = bytearray(RBUDP_RECEIVE_STREAM_HEADER_LEN)
    header[0x00:0x04] = (0xFFABEFC1).to_bytes(4, "little")
    header[0x04:0x08] = (0x1000000).to_bytes(4, "little")
    header[0x08:0x0C] = (0x3D000022).to_bytes(4, "little")
    header[0x0C:0x10] = (123).to_bytes(4, "little")
    header[0x10:0x14] = (456).to_bytes(4, "little")
    header[0x14:0x18] = (0x1900).to_bytes(4, "little")
    header[0x18:0x1A] = (0xBEEF).to_bytes(2, "little")
    header[0x1A:0x1C] = (len(payload)).to_bytes(2, "little")
    return bytes(header) + payload


class RbUdpReceiveStreamPacketTests:
    def test_parse_receive_stream_packet_returns_none_for_short_data(
        self,
    ) -> None:
        assert parse_receive_stream_packet(b"x" * 10) is None

    def test_parse_receive_stream_packet_reads_outer_header(self) -> None:
        parsed = parse_receive_stream_packet(_packet(b"abc"))

        assert parsed is not None
        assert 0xFFABEFC1 == parsed.marker
        assert 0x1000000 == parsed.word4
        assert 0x3D000022 == parsed.word8
        assert 123 == parsed.local_id
        assert 456 == parsed.remote_id
        assert 0x1900 == parsed.status_word
        assert 0xBEEF == parsed.rand16
        assert 3 == parsed.packet_len16
        assert b"abc" == parsed.payload
        assert (0x1000000, 0x3D000022) == parsed.stream_key
