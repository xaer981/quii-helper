from quii_helper.streaming.rtp.h264 import (
    annexb_nal_units,
    build_rtp_header,
    packetize_h264_access_unit,
)


class H264RtpPacketizerTests:
    def test_annexb_nal_units_removes_start_codes(self) -> None:
        assert [b"\x67sps", b"\x68pps", b"\x65idr"] == (
            annexb_nal_units(
                b"\x00\x00\x00\x01\x67sps"
                b"\x00\x00\x01\x68pps"
                b"\x00\x00\x00\x01\x65idr"
            )
        )

    def test_build_rtp_header_sets_marker_payload_type_and_ids(self) -> None:
        header = build_rtp_header(
            payload_type=96,
            sequence_number=7,
            timestamp=123,
            ssrc=456,
            marker=True,
        )

        assert 12 == len(header)
        assert 0x80 == header[0]
        assert 0xE0 == header[1]
        assert 7 == int.from_bytes(header[2:4], "big")
        assert 123 == int.from_bytes(header[4:8], "big")
        assert 456 == int.from_bytes(header[8:12], "big")

    def test_packetize_small_access_unit_uses_single_nal_packet(self) -> None:
        result = packetize_h264_access_unit(
            b"\x00\x00\x00\x01\x65idr",
            sequence_number=10,
            timestamp=20,
            ssrc=30,
            max_payload_size=1200,
        )

        assert 1 == len(result.packets)
        assert 11 == result.next_sequence_number
        packet = result.packets[0]
        assert 0xE0 == packet[1]
        assert b"\x65idr" == packet[12:]

    def test_packetize_large_nal_uses_fu_a_start_and_end_packets(
        self,
    ) -> None:
        nal = b"\x65" + b"x" * 10
        result = packetize_h264_access_unit(
            b"\x00\x00\x00\x01" + nal,
            sequence_number=1,
            timestamp=2,
            ssrc=3,
            max_payload_size=6,
        )

        assert 3 == len(result.packets)
        assert 4 == result.next_sequence_number
        first_payload = result.packets[0][12:]
        last_payload = result.packets[-1][12:]
        assert 28 == first_payload[0] & 0x1F
        assert first_payload[1] & 0x80
        assert not first_payload[1] & 0x40
        assert 28 == last_payload[0] & 0x1F
        assert not last_payload[1] & 0x80
        assert last_payload[1] & 0x40
        assert 0x60 == result.packets[0][1]
        assert 0xE0 == result.packets[-1][1]
