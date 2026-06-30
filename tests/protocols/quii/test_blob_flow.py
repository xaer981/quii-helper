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


class QuiiBlobFlowTests:
    def test_safe_text_preview_strips_nuls_and_limits_output(self) -> None:
        payload = b"\x00hello\x00" + b"x" * 100

        preview = safe_text_preview(payload)

        assert 80 == len(preview)
        assert preview.startswith("hello")

    def test_is_plausible_quii_header_rejects_invalid_sizes(self) -> None:
        assert is_plausible_quii_header(
            packet_type=0x01,
            payload_size=10,
            raw_size=10,
            body_available=10,
        )
        assert not is_plausible_quii_header(
            packet_type=0x99,
            payload_size=10,
            raw_size=10,
            body_available=10,
        )
        assert not is_plausible_quii_header(
            packet_type=0x01,
            payload_size=11,
            raw_size=10,
            body_available=10,
        )

    def test_score_media_payload_prefers_decodable_h264_cpacket(self) -> None:
        stream = (
            b"\x00\x00\x00\x01\x67sps"
            b"\x00\x00\x00\x01\x68pps"
            b"\x00\x00\x01\x65idr"
        )
        media_payload = _cpacket(stream)

        assert score_media_payload(media_payload) > 0
        assert 0 == score_media_payload(b"not media")

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

        assert used_decrypt
        assert _cpacket(stream) == selected
        assert decrypt_score > raw_score

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

        assert 5 == summary["offset"]
        assert "0x1" == summary["packet_type"]
        assert 3 == summary["payload_size"]
        assert 2 == summary["raw_size"]
        assert 1 == summary["flag15"]
        assert 2 == summary["flag16"]
        assert 3 == summary["flag17"]
        assert not summary["is_media"]
        assert "616263646566" == summary["payload_prefix"]
        assert "abc" == summary["text_preview"]
