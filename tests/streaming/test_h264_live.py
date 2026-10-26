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
    def test_audio_and_video_use_one_packer_even_before_first_keyframe(self):
        from tests.media.audio.test_frames import audio_cpacket

        audio, video = [], []
        assembler = H264LiveAssembler(
            sink=video.append, audio_sink=audio.append, wait_for_keyframe=True
        )
        first = audio_cpacket(b"sound")
        mixed = (
            first + _cpacket(b"\x00\x00\x01\x65idr") + audio_cpacket(b"next")
        )
        for chunk in (mixed[:10], mixed[10:31], mixed[31:]):
            assembler.feed_message(
                {"header": SimpleNamespace(packet_type=0xA0), "payload": chunk}
            )
        assert [f.data for f in audio] == [b"sound", b"next"]
        assert video == [b"\x00\x00\x01\x65idr"]
        assert assembler.packer.stats["completed"] == 3
        assert assembler.audio_frame_count == 2

    def test_native_keyframe_gate_preserves_partial_frame_state(self) -> None:
        assembler = H264LiveAssembler(wait_for_keyframe=True)
        emitted = []
        assembler.sink = emitted.append
        pframe = _cpacket(b"\x00\x00\x01\x41p", frame_tag=0xE0)
        keyframe = _cpacket(b"\x00\x00\x01\x65idr")
        for chunk in (pframe, keyframe[:7], keyframe[7:], pframe):
            assembler.feed_message(
                {"header": SimpleNamespace(packet_type=0xA0), "payload": chunk}
            )
        assert emitted == [b"\x00\x00\x01\x65idr", b"\x00\x00\x01\x41p"]
        assert assembler.frame_count == 2
        assert not assembler.wait_for_keyframe

    def test_frame_history_is_bounded_but_total_count_is_not(self) -> None:
        assembler = H264LiveAssembler()
        decoded = {
            "header": SimpleNamespace(packet_type=0xA0),
            "payload": _cpacket(b"\x00\x00\x00\x01\x65idr"),
        }
        for _ in range(2000):
            assert len(assembler.feed_message(decoded)) == 1
        assert len(assembler.frame_info) == 128
        assert assembler.stats["frames"] == 2000
        assert assembler.stats["access_units"] == 2000

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
