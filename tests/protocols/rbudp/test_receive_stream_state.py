import unittest

from quii_helper.protocols.rbudp.receive.stream_state import (
    RbUdpReceiveStreamState,
    advance_local_id,
    append_receive_stream_payload,
    drain_receive_stream_cache,
    has_pending_receive_streams,
    receive_ack_status_word,
    receive_stream_summary,
)


class RbUdpReceiveStreamStateTests(unittest.TestCase):
    def test_advance_local_id_wraps_at_uint32_boundary(self) -> None:
        self.assertEqual(2, advance_local_id(0xFFFFFFFE, 4))

    def test_receive_ack_status_word_advertises_native_window(self) -> None:
        self.assertEqual(0xFFFF0900, receive_ack_status_word(0))
        self.assertEqual(0xFFFF0900, receive_ack_status_word(1))
        self.assertEqual(0xFFFE0900, receive_ack_status_word(2))
        self.assertEqual(0x00000900, receive_ack_status_word(0x10000))
        self.assertEqual(0x00000900, receive_ack_status_word(0x20000))

    def test_receive_stream_summary_reports_only_pending_streams(self) -> None:
        pending = RbUdpReceiveStreamState(
            word4=0x1000000,
            word8=0x3D000022,
            next_local_id=100,
            buffer=bytearray(b"abc"),
            cache={103: b"def"},
        )
        completed = RbUdpReceiveStreamState(
            word4=0x2000001,
            word8=0x3E000023,
            next_local_id=200,
        )

        summary = receive_stream_summary(
            {"initialized": 2, "acked": 3},
            {
                (pending.word4, pending.word8): pending,
                (completed.word4, completed.word8): completed,
            },
        )

        self.assertEqual(2, summary["initialized"])
        self.assertEqual(3, summary["acked"])
        self.assertEqual(1, summary["active"])
        self.assertEqual(
            [
                {
                    "word4": "0x1000000",
                    "word8": "0x3d000022",
                    "next_local_id": 100,
                    "buffered": 3,
                    "cached": 1,
                }
            ],
            summary["streams"],
        )

    def test_has_pending_receive_streams_checks_buffer_and_cache(self) -> None:
        empty = RbUdpReceiveStreamState(word4=1, word8=2)
        buffered = RbUdpReceiveStreamState(
            word4=3,
            word8=4,
            buffer=bytearray(b"x"),
        )
        cached = RbUdpReceiveStreamState(word4=5, word8=6, cache={1: b"x"})

        self.assertFalse(has_pending_receive_streams({(1, 2): empty}))
        self.assertTrue(has_pending_receive_streams({(3, 4): buffered}))
        self.assertTrue(has_pending_receive_streams({(5, 6): cached}))

    def test_append_receive_stream_payload_updates_buffer_and_sequence(
        self,
    ) -> None:
        state = RbUdpReceiveStreamState(word4=1, word8=2)

        event = append_receive_stream_payload(
            state,
            local_id=0xFFFFFFFE,
            payload=b"abc",
        )

        self.assertEqual(b"abc", bytes(state.buffer))
        self.assertEqual(1, state.next_local_id)
        self.assertEqual(0xFFFFFFFE, event.local_id)
        self.assertEqual(3, event.payload_len)
        self.assertEqual(3, event.buffered_len)
        self.assertEqual(1, event.next_local_id)
        self.assertFalse(event.from_cache)

    def test_drain_receive_stream_cache_appends_contiguous_payloads(
        self,
    ) -> None:
        state = RbUdpReceiveStreamState(
            word4=1,
            word8=2,
            next_local_id=10,
            buffer=bytearray(b"a"),
            cache={10: b"bc", 12: b"d", 20: b"z"},
        )

        events = drain_receive_stream_cache(state)

        self.assertEqual(b"abcd", bytes(state.buffer))
        self.assertEqual(13, state.next_local_id)
        self.assertEqual({20: b"z"}, state.cache)
        self.assertEqual([10, 12], [event.local_id for event in events])
        self.assertEqual([2, 1], [event.payload_len for event in events])
        self.assertTrue(all(event.from_cache for event in events))


if __name__ == "__main__":
    unittest.main()
