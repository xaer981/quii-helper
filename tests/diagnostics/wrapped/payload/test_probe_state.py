import unittest

from quii_helper.diagnostics.wrapped.payload.probe_state import (
    leading_annexb_payload,
    payload_embedded_probe_context,
)
from quii_helper.diagnostics.wrapped.tail.probe import CONTAINER_PROBE_MARKER


class WrappedPayloadProbeStateTests(unittest.TestCase):
    def test_payload_embedded_probe_context_returns_none_without_marker(
        self,
    ) -> None:
        self.assertIsNone(
            payload_embedded_probe_context(
                b"payload", marker=CONTAINER_PROBE_MARKER
            )
        )

    def test_payload_embedded_probe_context_preserves_offsets_and_leading(
        self,
    ) -> None:
        payload = (
            b"prefix"
            + b"\x00\x00\x00\x01"
            + b"g"
            + CONTAINER_PROBE_MARKER
            + b"tail"
        )

        context = payload_embedded_probe_context(
            payload, marker=CONTAINER_PROBE_MARKER
        )

        self.assertIsNotNone(context)
        assert context is not None
        self.assertEqual(
            payload.index(CONTAINER_PROBE_MARKER), context["marker_offset"]
        )
        self.assertEqual(
            b"prefix" + b"\x00\x00\x00\x01" + b"g",
            context["leading"],
        )
        self.assertEqual(6, context["leading_start_code4_at"])
        self.assertEqual(7, context["leading_start_code3_at"])
        self.assertEqual(
            b"\x00\x00\x00\x01g", context["leading_annexb_payload"]
        )

    def test_leading_annexb_payload_prefers_four_byte_start_code(
        self,
    ) -> None:
        leading = b"xx\x00\x00\x00\x01g\x00\x00\x01h"

        self.assertEqual(
            b"\x00\x00\x00\x01g\x00\x00\x01h",
            leading_annexb_payload(leading, start4=2, start3=3),
        )

    def test_leading_annexb_payload_restores_preceding_zero_for_3byte_code(
        self,
    ) -> None:
        leading = b"x\x00\x00\x01g"

        self.assertEqual(
            b"\x00\x00\x01g",
            leading_annexb_payload(leading, start4=-1, start3=2),
        )

    def test_leading_annexb_payload_handles_missing_start_code(self) -> None:
        self.assertEqual(
            b"",
            leading_annexb_payload(b"abc", start4=-1, start3=-1),
        )


if __name__ == "__main__":
    unittest.main()
