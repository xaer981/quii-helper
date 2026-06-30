import queue
import threading
from types import SimpleNamespace

import pytest

from quii_helper.config import RuntimeCredentials
from quii_helper.protocols.quii.live_rb import build_direct_quii_setup_rb
from quii_helper.protocols.rbudp.core.constants import RbUdpProtocolConstants
from quii_helper.protocols.rbudp.live.sender import RbUdpLiveCommandSender


class _Owner(RbUdpProtocolConstants):
    def __init__(self) -> None:
        self.config = SimpleNamespace(
            channel=1,
            stream=1,
            live_inner=False,
            live_newcn=True,
            live_play_payload="path",
            live_keepalive_interval=0.0,
            connect_mode=-1,
            oem="G0083",
        )
        self.src_id = 0x04000006
        self.dest_id = 0x12340000
        self._data = queue.Queue()
        self._quii_play_sent = threading.Event()
        self._quii_setup_acked = threading.Event()
        self.sent: list[tuple[bytes, bytes, dict]] = []
        self.debug: list[tuple[str, dict]] = []
        self.lane = {
            "src_id": self.src_id,
            "word4": 0x11000008,
            "word8": 0x01000000,
            "local_id": 77,
            "remote_id": 165,
            "quii_setup_acked": True,
            "quii_next_seq": 3,
        }

    def _connected_lane_destinations(self) -> list[tuple[dict, int]]:
        return [(self.lane, self.dest_id)]

    def _send_wrapped(self, inner: bytes, *, tag8: bytes, lane: dict) -> None:
        self.sent.append((inner, tag8, lane))

    def _dbg(self, message: str, **kwargs: object) -> None:
        self.debug.append((message, kwargs))


def _credentials() -> RuntimeCredentials:
    return RuntimeCredentials(
        session_id="session",
        dynamic_password="password",
        data_encode_key="0123456789abcdef0123456789abcdef",
        auth_code="auth",
        transparent_basedata="",
        raw={},
    )


class RbUdpLiveCommandSenderTests:
    def test_send_setup_uses_same_direct_quii_payload(self) -> None:
        owner = _Owner()
        sender = RbUdpLiveCommandSender(owner)

        sender.send_setup(seq=9)

        expected = build_direct_quii_setup_rb(
            src_id=owner.src_id,
            dest_id=owner.dest_id,
            seq=9,
        )
        assert [(expected, owner.DATA_TAG, owner.lane)] == owner.sent
        assert "send_quii_setup" == owner.debug[0][0]

    def test_send_keepalive_uses_lane_sequence_and_increments_it(self) -> None:
        owner = _Owner()
        sender = RbUdpLiveCommandSender(owner)

        sender.send_keepalive(_credentials())

        assert 1 == len(owner.sent)
        assert owner.DATA_TAG == owner.sent[0][1]
        assert owner.lane is owner.sent[0][2]
        assert 4 == owner.lane["quii_next_seq"]
        assert "send_quii_keepalive" == owner.debug[0][0]

    def test_wait_setup_ack_observes_selected_lane_state(self) -> None:
        owner = _Owner()
        sender = RbUdpLiveCommandSender(owner)

        assert True is sender.wait_setup_ack(timeout=0.01)

    def test_unconnected_tunnel_rejects_send(self) -> None:
        owner = _Owner()
        owner.dest_id = None
        sender = RbUdpLiveCommandSender(owner)

        with pytest.raises(RuntimeError, match="tunnel is not connected"):
            sender.send_setup()
