import unittest

from quii_helper.media.frames.models import QuiiHeader
from quii_helper.protocols.quii.blob_flow import (
    decode_candidate_summary,
    is_plausible_quii_header,
    safe_text_preview,
    score_media_payload,
    select_media_payload,
)


def _cpacket(bitstream: bytes, *, frame_tag: int = 0xE1) -> bytes:
    header = bytearray(20)
    header[:3] = b"\x00\x00\x01"
    header[3] = frame_tag
    header[4:8] = len(bitstream).to_bytes(4, "little")
    header[15] = 100
    header[16:18] = (960).to_bytes(2, "little")
    header[18:20] = (576).to_bytes(2, "little")
    return bytes(header) + bitstream


class QuiiBlobFlowTests(unittest.TestCase):
    def test_safe_text_preview_strips_nuls_and_limits_output(self) -> None:
        payload = b"\x00hello\x00" + b"x" * 100

        preview = safe_text_preview(payload)

        self.assertEqual(80, len(preview))
        self.assertTrue(preview.startswith("hello"))

    def test_is_plausible_quii_header_rejects_invalid_sizes(self) -> None:
        self.assertTrue(
            is_plausible_quii_header(
                packet_type=0x01,
                payload_size=10,
                raw_size=10,
                body_available=10,
            )
        )
        self.assertFalse(
            is_plausible_quii_header(
                packet_type=0x99,
                payload_size=10,
                raw_size=10,
                body_available=10,
            )
        )
        self.assertFalse(
            is_plausible_quii_header(
                packet_type=0x01,
                payload_size=11,
                raw_size=10,
                body_available=10,
            )
        )

    def test_score_media_payload_prefers_decodable_h264_cpacket(self) -> None:
        stream = (
            b"\x00\x00\x00\x01\x67sps"
            b"\x00\x00\x00\x01\x68pps"
            b"\x00\x00\x01\x65idr"
        )
        media_payload = _cpacket(stream)

        self.assertGreater(score_media_payload(media_payload), 0)
        self.assertEqual(0, score_media_payload(b"not media"))

    def test_select_media_payload_prefers_higher_scored_candidate(
        self,
    ) -> None:
        stream = (
            b"\x00\x00\x00\x01\x67sps"
            b"\x00\x00\x00\x01\x68pps"
            b"\x00\x00\x01\x65idr"
        )
        selected, used_decrypt, raw_score, decrypt_score = (
            select_media_payload(b"noise", _cpacket(stream))
        )

        self.assertTrue(used_decrypt)
        self.assertEqual(_cpacket(stream), selected)
        self.assertGreater(decrypt_score, raw_score)

    def test_decode_candidate_summary_keeps_existing_shape(self) -> None:
        header = QuiiHeader(
            packet_type=0x01,
            payload_size=3,
            raw_size=2,
            flag13=0,
            flag14=0,
            flag15=1,
            flag16=2,
            flag17=3,
            raw=b"",
        )
        decoded = {
            "is_media": False,
            "payload": b"abcdef",
            "text_preview": "abc",
        }

        summary = decode_candidate_summary(
            offset=5,
            header=header,
            decoded=decoded,
        )

        self.assertEqual(5, summary["offset"])
        self.assertEqual("0x1", summary["packet_type"])
        self.assertEqual(3, summary["payload_size"])
        self.assertEqual(2, summary["raw_size"])
        self.assertEqual(1, summary["flag15"])
        self.assertEqual(2, summary["flag16"])
        self.assertEqual(3, summary["flag17"])
        self.assertFalse(summary["is_media"])
        self.assertEqual("616263646566", summary["payload_prefix"])
        self.assertEqual("abc", summary["text_preview"])


if __name__ == "__main__":
    unittest.main()
