import unittest
from types import SimpleNamespace

from quii_helper.media.cpacket import (
    cpacket_frame_len,
    find_next_cpacket,
    parse_cpacket_header,
    starts_cpacket,
)
from quii_helper.media.frames.assembler import (
    assemble_h264_stream_from_messages,
)
from quii_helper.media.frames.cframe_pack import (
    QuiiCFramePack as DirectCFramePack,
)
from quii_helper.media.frames.frame_parsing import parse_quii_media_frame_at
from quii_helper.media.frames.parsing import (
    QuiiCFramePack,
    iter_quii_media_frames,
    parse_quii_media_frame,
)


def _cpacket(
    bitstream: bytes,
    *,
    frame_tag: int = 0xE1,
    frame_stamp: int = 1234,
    codec: int = 1,
    fps_raw: int = 100,
    width: int = 960,
    height: int = 576,
) -> bytes:
    header = bytearray(20)
    header[:3] = b"\x00\x00\x01"
    header[3] = frame_tag
    header[4:8] = len(bitstream).to_bytes(4, "little")
    header[8:12] = frame_stamp.to_bytes(4, "little")
    header[14] = codec
    header[15] = fps_raw
    header[16:18] = width.to_bytes(2, "little")
    header[18:20] = height.to_bytes(2, "little")
    return bytes(header) + bitstream


class MediaParsingTests(unittest.TestCase):
    def test_cpacket_helpers_parse_complete_header(self) -> None:
        payload = _cpacket(
            b"\x00\x00\x00\x01\x65idr",
            frame_tag=0xE1,
            frame_stamp=55,
            fps_raw=120,
            width=1280,
            height=720,
        )

        header = parse_cpacket_header(payload)

        self.assertTrue(starts_cpacket(payload, 0))
        self.assertEqual(len(payload) - 20, cpacket_frame_len(payload))
        self.assertIsNotNone(header)
        self.assertEqual(0xE1, header["frame_tag"])
        self.assertEqual(55, header["frame_stamp"])
        self.assertEqual(30.0, header["fps"])
        self.assertEqual(1280, header["width"])
        self.assertEqual(720, header["height"])

    def test_cpacket_helpers_skip_false_prefix_type(self) -> None:
        valid = _cpacket(b"\x00\x00\x01\x41p", frame_tag=0xE0)
        payload = b"\x00\x00\x01\x01noise" + valid

        self.assertFalse(starts_cpacket(payload, 0))
        self.assertEqual(9, find_next_cpacket(payload, 0))

    def test_cpacket_header_can_parse_incomplete_frame_header_only(
        self,
    ) -> None:
        full = _cpacket(b"\x00\x00\x00\x01\x65idr")
        partial = full[:20]

        self.assertIsNone(parse_cpacket_header(partial))
        self.assertIsNotNone(
            parse_cpacket_header(partial, require_complete=False)
        )

    def test_parse_quii_media_frame_reads_cpacket_header(self) -> None:
        bitstream = b"\x00\x00\x00\x01\x67sps"
        frame = parse_quii_media_frame(_cpacket(bitstream))

        self.assertIsNotNone(frame)
        self.assertEqual(0xE1, frame["frame_tag"])
        self.assertEqual((0xE1 + 0x20) & 0xFF, frame["frame_type"])
        self.assertEqual(len(bitstream), frame["frame_len"])
        self.assertEqual(1234, frame["frame_stamp"])
        self.assertEqual(25.0, frame["fps"])
        self.assertEqual(960, frame["width"])
        self.assertEqual(576, frame["height"])
        self.assertEqual(0, frame["nal_offset"])

    def test_direct_frame_parser_matches_parsing_facade(self) -> None:
        bitstream = b"\x00\x00\x01\x41p"
        payload = b"noise" + _cpacket(bitstream, frame_tag=0xE0)

        frame = parse_quii_media_frame_at(payload, 5)

        self.assertIsNotNone(frame)
        self.assertEqual(0xE0, frame["frame_tag"])
        self.assertEqual(bitstream, frame["bitstream"])
        self.assertIs(DirectCFramePack, QuiiCFramePack)

    def test_iter_quii_media_frames_skips_prefix_noise(self) -> None:
        first = _cpacket(b"\x00\x00\x00\x01\x65idr", frame_tag=0xE1)
        second = _cpacket(b"\x00\x00\x01\x41p", frame_tag=0xE0)

        frames = iter_quii_media_frames(b"noise" + first + second)

        self.assertEqual(
            [0xE1, 0xE0],
            [frame["frame_tag"] for frame in frames],
        )

    def test_cframe_pack_assembles_fragmented_frame(self) -> None:
        payload = _cpacket(b"\x00\x00\x00\x01\x65idr")
        packer = QuiiCFramePack()

        self.assertEqual([], packer.feed(payload[:10]))
        frames = packer.feed(payload[10:])

        self.assertEqual(1, len(frames))
        self.assertEqual(payload[20:], frames[0]["bitstream"])
        self.assertEqual(2, frames[0]["cframe_fragments"])
        self.assertEqual(1, packer.stats["started"])
        self.assertEqual(1, packer.stats["continued"])
        self.assertEqual(1, packer.stats["completed"])

    def test_assembler_collects_video_access_units(self) -> None:
        idr = b"\x00\x00\x00\x01\x65idr"
        non_idr = b"\x00\x00\x01\x41p"
        messages = [
            {
                "header": SimpleNamespace(packet_type=0xA0),
                "payload": _cpacket(idr),
            },
            {
                "header": SimpleNamespace(packet_type=0xA0),
                "payload": _cpacket(non_idr, frame_tag=0xE0),
            },
        ]

        assembled = assemble_h264_stream_from_messages(messages)

        self.assertEqual(idr + non_idr, assembled.stream_bytes)
        self.assertTrue(assembled.has_access_units)
        self.assertEqual(2, assembled.summary["video_frames"])
        self.assertEqual(1, assembled.summary["keyframes"])
        self.assertEqual(2, assembled.summary["assembled_units"])


if __name__ == "__main__":
    unittest.main()
