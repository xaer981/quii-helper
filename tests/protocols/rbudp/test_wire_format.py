from quii_helper.protocols.rbudp.control.packets import (
    build_rb_udp_control_packet,
    native_checksum16,
    parse_rb_udp_control_packet,
)

OBSERVED_CONTROL_PACKETS = [
    {
        "name": "established",
        "hex": "c1efabff0700000f0000000101000000010000000009ffff6cf71c00",
        "word4": 0x0F000007,
        "word8": 0x01000000,
        "local_id": 1,
        "remote_id": 1,
        "status_word": 0xFFFF0900,
        "checksum": 0xF76C,
    },
    {
        "name": "play_established_ack",
        "hex": "c1efabff0800001100000001a5000000dd00000000099efb4cf81c00",
        "word4": 0x11000008,
        "word8": 0x01000000,
        "local_id": 165,
        "remote_id": 221,
        "status_word": 0xFB9E0900,
        "checksum": 0xF84C,
    },
    {
        "name": "post_setup_ack",
        "hex": "c1efabff0b00001700000001cd0100002d0200000009b0febfec1c00",
        "word4": 0x1700000B,
        "word8": 0x01000000,
        "local_id": 461,
        "remote_id": 557,
        "status_word": 0xFEB00900,
        "checksum": 0xECBF,
    },
    {
        "name": "play_stage6_ack_second_lane",
        "hex": "c1efabff2300003e010000022d030000ab4b010000097ffbf87c1c00",
        "word4": 0x3E000023,
        "word8": 0x02000001,
        "local_id": 813,
        "remote_id": 84907,
        "status_word": 0xFB7F0900,
        "checksum": 0x7CF8,
    },
]


class RbUdpWireFormatTests:
    def test_build_control_packet_matches_observed_native_bytes(self) -> None:
        packet = build_rb_udp_control_packet(
            word4=0x0F000007,
            word8=0x01000000,
            local_id=1,
            remote_id=1,
            status_word=0xFFFF0900,
            nonce=0x5A8F,
        )

        assert (
            bytes.fromhex(
                "c1efabff0700000f0000000101000000010000000009ffff6cf71c00"
            )
            == packet
        )

    def test_parse_control_packet_reads_observed_native_bytes(self) -> None:
        for fixture in OBSERVED_CONTROL_PACKETS:
            parsed = parse_rb_udp_control_packet(
                bytes.fromhex(str(fixture["hex"]))
            )

            assert parsed.marker == 0xFFABEFC1
            assert parsed.word4 == fixture["word4"]
            assert parsed.word8 == fixture["word8"]
            assert parsed.local_id == fixture["local_id"]
            assert parsed.remote_id == fixture["remote_id"]
            assert parsed.status_word == fixture["status_word"]
            assert parsed.rand16 == fixture["checksum"]
            assert parsed.packet_len16 == 28

    def test_rebuild_control_packets_matches_observed_native_bytes(
        self,
    ) -> None:
        for fixture in OBSERVED_CONTROL_PACKETS:
            rebuilt = build_rb_udp_control_packet(
                word4=int(fixture["word4"]),
                word8=int(fixture["word8"]),
                local_id=int(fixture["local_id"]),
                remote_id=int(fixture["remote_id"]),
                status_word=int(fixture["status_word"]),
                nonce=0,
            )

            assert bytes.fromhex(str(fixture["hex"])) == rebuilt

    def test_control_packet_nonce_is_not_serialized(self) -> None:
        fixture = OBSERVED_CONTROL_PACKETS[0]

        first = build_rb_udp_control_packet(
            word4=int(fixture["word4"]),
            word8=int(fixture["word8"]),
            local_id=int(fixture["local_id"]),
            remote_id=int(fixture["remote_id"]),
            status_word=int(fixture["status_word"]),
            nonce=0x0000,
        )
        second = build_rb_udp_control_packet(
            word4=int(fixture["word4"]),
            word8=int(fixture["word8"]),
            local_id=int(fixture["local_id"]),
            remote_id=int(fixture["remote_id"]),
            status_word=int(fixture["status_word"]),
            nonce=0xFFFF,
        )

        assert first == second
        assert (
            bytes.fromhex(
                "c1efabff0700000f0000000101000000010000000009ffff6cf71c00"
            )
            == first
        )

    def test_native_checksum_ignores_existing_checksum_field(self) -> None:
        packet = bytearray(
            bytes.fromhex(
                "c1efabff0700000f0000000101000000010000000009ffff00001c00"
            )
        )

        assert 0xF76C == native_checksum16(packet)
        packet[0x18:0x1A] = b"\xff\xff"
        assert 0xF76C == native_checksum16(packet)
