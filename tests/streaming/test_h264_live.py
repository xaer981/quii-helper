from types import SimpleNamespace

from quii_helper.streaming.h264 import H264LiveAssembler


def _cpacket(bitstream: bytes, *, frame_tag: int = 0xE1) -> bytes:
    header = bytearray(20)
    header[:3] = b"\x00\x00\x01"
    header[3] = frame_tag
    header[4:8] = len(bitstream).to_bytes(4, "little")
    header[8:12] = (1234).to_bytes(4, "little")
    header[14] = 1
    header[15] = 100
    header[16:18] = (960).to_bytes(2, "little")
    header[18:20] = (576).to_bytes(2, "little")
    return bytes(header) + bitstream


class H264LiveAssemblerTests:
    def test_feed_message_emits_access_units_to_sink(self) -> None:
        emitted = []
        assembler = H264LiveAssembler(sink=emitted.append)
        access_unit = b"\x00\x00\x00\x01\x65idr"

        result = assembler.feed_message(
            {
                "header": SimpleNamespace(packet_type=0xA0),
                "payload": _cpacket(access_unit),
            }
        )

        assert [access_unit] == result
        assert [access_unit] == emitted
        assert 1 == assembler.stats["frames"]
        assert 1 == assembler.stats["access_units"]

    def test_feed_message_keeps_fragmented_cpacket_state(self) -> None:
        assembler = H264LiveAssembler()
        payload = _cpacket(b"\x00\x00\x00\x01\x65idr")

        assert [] == (
            assembler.feed_message(
                {
                    "header": SimpleNamespace(packet_type=0xA0),
                    "payload": payload[:10],
                }
            )
        )
        assert [b"\x00\x00\x00\x01\x65idr"] == (
            assembler.feed_message(
                {
                    "header": SimpleNamespace(packet_type=0xA0),
                    "payload": payload[10:],
                }
            )
        )

    def test_feed_message_ignores_non_media_packets(self) -> None:
        assembler = H264LiveAssembler()

        assert [] == (
            assembler.feed_message(
                {"header": SimpleNamespace(packet_type=0x01), "payload": b"x"}
            )
        )
