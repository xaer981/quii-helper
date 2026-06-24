import unittest

from quii_helper.media.cpacket.constants import CPACKET_HEADER_LEN
from quii_helper.media.frames.cframe_pack_state import (
    append_buffer_bytes,
    cframe_expected_total_len,
    initial_cframe_pack_stats,
)


class MediaCFramePackStateTests(unittest.TestCase):
    def test_initial_cframe_pack_stats_preserves_existing_keys(self) -> None:
        self.assertEqual(
            {
                "started": 0,
                "continued": 0,
                "completed": 0,
                "reset_incomplete": 0,
                "invalid_headers": 0,
                "dropped_orphan_bytes": 0,
                "dropped_oversize_frames": 0,
                "trailing_partial_bytes": 0,
            },
            initial_cframe_pack_stats(),
        )

    def test_cframe_expected_total_len_adds_header_len(self) -> None:
        self.assertEqual(
            CPACKET_HEADER_LEN + 123,
            cframe_expected_total_len(123),
        )

    def test_append_buffer_bytes_extends_until_target_len(self) -> None:
        buffer = bytearray(b"abc")

        offset = append_buffer_bytes(
            buffer,
            b"defghi",
            0,
            target_len=5,
        )

        self.assertEqual(2, offset)
        self.assertEqual(bytearray(b"abcde"), buffer)

    def test_append_buffer_bytes_consumes_remaining_payload_when_short(
        self,
    ) -> None:
        buffer = bytearray(b"abc")

        offset = append_buffer_bytes(
            buffer,
            b"de",
            0,
            target_len=10,
        )

        self.assertEqual(2, offset)
        self.assertEqual(bytearray(b"abcde"), buffer)

    def test_append_buffer_bytes_noops_when_buffer_already_full(self) -> None:
        buffer = bytearray(b"abc")

        offset = append_buffer_bytes(
            buffer,
            b"de",
            0,
            target_len=3,
        )

        self.assertEqual(0, offset)
        self.assertEqual(bytearray(b"abc"), buffer)


if __name__ == "__main__":
    unittest.main()
