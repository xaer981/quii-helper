from quii_helper.protocols.rbudp.fragments.state import (
    active_fragment_streams_summary,
    classify_fragment_append,
    initial_fragment_stats,
    is_duplicate_fragment_restart,
    wrapped_fragment_summary,
)
from quii_helper.protocols.rbudp.fragments.stream import (
    RbUdpWrappedFragmentStream,
)


def _stream(
    *,
    inner_total_length: int = 10,
    payload: bytes = b"abc",
) -> RbUdpWrappedFragmentStream:
    return RbUdpWrappedFragmentStream(
        marker=0xFFABEFC1,
        word4=0x1000000,
        word8=0x3D000022,
        start_local_id=100,
        remote_id=200,
        status_word=0x1900,
        rand16=0x1234,
        packet_len16=0,
        inner_total_length=inner_total_length,
        payload=bytearray(payload),
        next_local_id=100 + len(payload),
    )


class RbUdpFragmentStateTests:
    def test_initial_fragment_stats_contains_existing_keys(self) -> None:
        assert {
            "started": 0,
            "appended": 0,
            "completed": 0,
            "replayed": 0,
            "replay_acked": 0,
            "restart_acked": 0,
            "gaps": 0,
            "partials": 0,
        } == (initial_fragment_stats())

    def test_is_duplicate_fragment_restart_matches_existing_condition(
        self,
    ) -> None:
        stream = _stream(inner_total_length=10, payload=b"abcdef")

        assert is_duplicate_fragment_restart(
            stream,
            inner_total_length=10,
            incoming_payload_len=3,
        )
        assert not is_duplicate_fragment_restart(
            stream,
            inner_total_length=11,
            incoming_payload_len=3,
        )
        assert not is_duplicate_fragment_restart(
            stream,
            inner_total_length=10,
            incoming_payload_len=7,
        )

    def test_classify_fragment_append_reports_replay_gap_or_in_order(
        self,
    ) -> None:
        assert "in_order" == (
            classify_fragment_append(local_id=100, next_local_id=100)
        )
        assert "replay" == (
            classify_fragment_append(local_id=99, next_local_id=100)
        )
        assert "gap" == (
            classify_fragment_append(local_id=101, next_local_id=100)
        )

    def test_wrapped_fragment_summary_reports_active_streams(self) -> None:
        stream = _stream(inner_total_length=10, payload=b"abc")
        streams = {stream.key: stream}

        active = active_fragment_streams_summary(streams)
        summary = wrapped_fragment_summary({"started": 1}, streams)

        assert active == summary["active_streams"]
        assert 1 == summary["started"]
        assert 1 == summary["active"]
        assert "0x1000000" == summary["active_streams"][0]["word4"]
        assert "0x3d000022" == summary["active_streams"][0]["word8"]
        assert 100 == summary["active_streams"][0]["start_local_id"]
        assert 103 == summary["active_streams"][0]["next_local_id"]
        assert 3 == summary["active_streams"][0]["have"]
        assert 10 == summary["active_streams"][0]["need"]
        assert 7 == summary["active_streams"][0]["missing"]
