from types import SimpleNamespace

from quii_helper.protocols.rbudp.control.dispatcher import (
    RbUdpControlDispatcher,
)
from quii_helper.protocols.rbudp.core.constants import RbUdpProtocolConstants
from quii_helper.protocols.rbudp.core.models import ParsedRbUdpControlPacket


def _control(*, status_word: int, local_id: int = 10, remote_id: int = 20):
    return ParsedRbUdpControlPacket(
        marker=0xFFABEFC1,
        word4=0x1000000,
        word8=0x3D000022,
        local_id=local_id,
        remote_id=remote_id,
        status_word=status_word,
        rand16=0,
        packet_len16=28,
    )


class _Event:
    def __init__(self, value: bool = False) -> None:
        self.value = value
        self.set_called = False

    def is_set(self) -> bool:
        return self.value

    def set(self) -> None:
        self.set_called = True
        self.value = True


class _Owner(RbUdpProtocolConstants):
    def __init__(self) -> None:
        self._peer_addr = ("127.0.0.1", 1234)
        self._quii_ready = _Event()
        self._quii_play_sent = _Event()
        self._last_control = None
        self.lane = {
            "quii_play_acked": False,
            "quii_play_end_local_id": 0,
        }
        self.calls: list[tuple] = []

    def _dbg(self, *args, **kwargs) -> None:
        self.calls.append(("dbg", args, kwargs))

    def _handle_syn_ack_control(self, control) -> bool:
        return False

    def _lane_for_control(self, control):
        return self.lane

    def _apply_control_lane_ids(self, lane, control):
        self.calls.append(("apply_ids", control.local_id, control.remote_id))
        return 77

    def _send_fragment_ack(self, *args, **kwargs) -> None:
        self.calls.append(("fragment_ack", args, kwargs))

    def _handle_flow_control(self, *args, **kwargs) -> None:
        self.calls.append(("flow", args, kwargs))

    def _handle_established_control(self, *args) -> None:
        self.calls.append(("established", args))

    def _handle_progress_control(self, *args, **kwargs) -> None:
        self.calls.append(("progress", args, kwargs))

    def _send_offset_ack(self, *args, **kwargs) -> None:
        self.calls.append(("offset_ack", args, kwargs))

    def _is_quii_play_ack_control(self, *args, **kwargs) -> bool:
        return False

    def _start_play_sync_from_control(self, *args, **kwargs) -> None:
        self.calls.append(("play_sync", args, kwargs))

    def _handle_play_late_status(self, *args) -> None:
        self.calls.append(("play_late", args))

    def _handle_play_sync_status(self, *args) -> None:
        self.calls.append(("play_sync_status", args))


class RbUdpControlDispatcherTests:
    def test_dispatches_post_connect_to_offset_ack(self) -> None:
        owner = _Owner()

        RbUdpControlDispatcher(owner).handle(
            _control(status_word=owner.CONTROL_POST_CONNECT_STATUS)
        )

        assert owner._last_control is not None
        assert "offset_ack" == owner.calls[-1][0]
        assert (
            owner.CONTROL_POST_CONNECT_ACK_STATUS
            == owner.calls[-1][2]["status_word"]
        )
        assert 0x38 == owner.calls[-1][2]["remote_delta"]

    def test_dispatches_stream_ready_to_ack_sync_and_ready_event(self) -> None:
        owner = _Owner()

        RbUdpControlDispatcher(owner).handle(
            _control(status_word=owner.CONTROL_STREAM_READY_STATUS)
        )

        call_names = [call[0] for call in owner.calls]
        assert "offset_ack" in call_names
        assert "play_sync" in call_names
        assert owner._quii_ready.is_set()

    def test_dispatches_play_late_status(self) -> None:
        owner = _Owner()

        RbUdpControlDispatcher(owner).handle(
            _control(status_word=owner.CONTROL_PLAY_LATE_STATUS)
        )

        assert "play_late" == owner.calls[-1][0]

    def test_syn_ack_short_circuits_before_lane_lookup(self) -> None:
        owner = _Owner()

        def syn_ack(_control) -> bool:
            owner.calls.append(("syn_ack",))
            return True

        owner._handle_syn_ack_control = syn_ack
        owner._lane_for_control = lambda _control: (_ for _ in ()).throw(
            AssertionError("lane lookup should not run")
        )

        RbUdpControlDispatcher(owner).handle(_control(status_word=0))

        assert "syn_ack" == owner.calls[-1][0]
