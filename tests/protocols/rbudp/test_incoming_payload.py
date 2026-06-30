from typing import Any

from quii_helper.protocols.rbudp.lanes.registry import RbUdpLane
from quii_helper.protocols.rbudp.receive.incoming_payload import (
    RBUDP_DIRECT_STATUS,
    RBUDP_MARKER,
    RBUDP_STREAM_STATUS,
    RbUdpIncomingPayloadHandler,
)


class _Event:
    def __init__(self, value: bool) -> None:
        self.value = value

    def is_set(self) -> bool:
        return self.value


class _ReceiveStreams:
    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.seen: list[bytes] = []

    def feed(self, data: bytes) -> bool:
        self.seen.append(data)
        return self.result


class _WrappedFragments:
    def __init__(self) -> None:
        self.start_result = False
        self.append_result = False
        self.started: list[bytes] = []
        self.appended: list[bytes] = []

    def start(self, data: bytes) -> bool:
        self.started.append(data)
        return self.start_result

    def append(self, data: bytes) -> bool:
        self.appended.append(data)
        return self.append_result


def _packet(
    payload: bytes,
    *,
    status_word: int,
    word4: int = 0x01000000,
    word8: int = 0x3D000022,
    local_id: int = 100,
    remote_id: int = 200,
) -> bytes:
    header = bytearray(0x1C)
    header[0x00:0x04] = RBUDP_MARKER.to_bytes(4, "little")
    header[0x04:0x08] = word4.to_bytes(4, "little")
    header[0x08:0x0C] = word8.to_bytes(4, "little")
    header[0x0C:0x10] = local_id.to_bytes(4, "little")
    header[0x10:0x14] = remote_id.to_bytes(4, "little")
    header[0x14:0x18] = status_word.to_bytes(4, "little")
    header[0x18:0x1A] = (0xCAFE).to_bytes(2, "little")
    header[0x1A:0x1C] = len(payload).to_bytes(2, "little")
    return bytes(header) + payload


class _IncomingPayloadOwner:
    def __init__(self, *, after_play: bool = True) -> None:
        self._direct_data_next_ids: dict[tuple[int, int], int] = {}
        self._direct_data_stats = {"acked": 0, "replayed": 0, "gaps": 0}
        self._quii_play_sent = _Event(after_play)
        self._receive_streams = _ReceiveStreams()
        self._wrapped_fragments = _WrappedFragments()
        self.stream_payload_count = 0
        self.stream_payload_early_count = 0
        self.stream_payload_early_filler_count = 0
        self.stream_payload_filler_count = 0
        self.queued: list[tuple[bytes, str, dict[str, Any]]] = []
        self.debug: list[tuple[str, dict[str, object]]] = []
        self.fragment_acks: list[
            tuple[RbUdpLane, int, int, dict[str, Any]]
        ] = []
        self.lane: RbUdpLane = {
            "src_id": 0x04000006,
            "word4": 0x3D000022,
            "word8": 0x01000000,
            "local_id": 77,
            "remote_id": 165,
            "nonce": 1,
            "connect_sent": False,
            "setup_probe_sent": False,
            "peer_logic_id": 77,
            "progress_sent": False,
            "quii_setup_acked": False,
        }

    def _dbg(self, message: str, **kwargs: object) -> None:
        self.debug.append((message, kwargs))

    def _lane_for_packet_words(
        self, *, word4: int, word8: int
    ) -> RbUdpLane | None:
        if (word4, word8) == (0x01000000, 0x3D000022):
            return self.lane
        return None

    def _queue_payload(
        self, payload: bytes, *, source: str, **meta: Any
    ) -> None:
        self.queued.append((payload, source, meta))

    def _send_fragment_ack(
        self,
        lane: RbUdpLane,
        local_id: int,
        remote_id: int,
        *,
        word4: int | None = None,
        word8: int | None = None,
        status_word: int | None = None,
        log_label: str = "send_control_fragment_ack",
    ) -> None:
        self.fragment_acks.append(
            (
                lane,
                local_id,
                remote_id,
                {
                    "word4": word4,
                    "word8": word8,
                    "status_word": status_word,
                    "log_label": log_label,
                },
            )
        )


class RbUdpIncomingPayloadTests:
    def test_component_delegates_rbudp_data_to_receive_streams(self) -> None:
        owner = _IncomingPayloadOwner()
        data = b"packet"

        consumed = RbUdpIncomingPayloadHandler(owner).handle_rbudp_data_packet(
            data
        )

        assert consumed
        assert owner._receive_streams.seen == [data]

    def test_component_queues_stream_payload_after_play(self) -> None:
        owner = _IncomingPayloadOwner(after_play=True)
        payload = b"media"

        RbUdpIncomingPayloadHandler(owner).handle_stream_payload_packet(
            _packet(payload, status_word=RBUDP_STREAM_STATUS)
        )

        assert owner.stream_payload_count == 1
        assert owner.stream_payload_filler_count == 0
        assert owner.queued[0][0] == payload
        assert owner.queued[0][1] == "stream_payload"

    def test_component_counts_early_filler_without_queueing(self) -> None:
        owner = _IncomingPayloadOwner(after_play=False)

        RbUdpIncomingPayloadHandler(owner).handle_stream_payload_packet(
            _packet(b"\xbb" * 4, status_word=RBUDP_STREAM_STATUS)
        )

        assert owner.stream_payload_early_filler_count == 1
        assert owner.queued == []

    def test_component_acks_and_queues_direct_quii_blob_after_play(
        self,
    ) -> None:
        owner = _IncomingPayloadOwner(after_play=True)
        payload = b"blob"

        RbUdpIncomingPayloadHandler(owner).handle_direct_quii_blob_packet(
            _packet(payload, status_word=RBUDP_DIRECT_STATUS)
        )

        assert owner._direct_data_stats["acked"] == 1
        assert owner._direct_data_next_ids[(0x01000000, 0x3D000022)] == 104
        assert owner.queued[0][0] == payload
        assert owner.queued[0][1] == "direct_quii_blob"
        _lane, ack_local_id, ack_remote_id, ack_meta = owner.fragment_acks[0]
        assert ack_local_id == 200
        assert ack_remote_id == 104
        assert ack_meta["word4"] == 0x3D000022
        assert ack_meta["word8"] == 0x01000000
        assert ack_meta["log_label"] == "send_control_direct_data_ack"
