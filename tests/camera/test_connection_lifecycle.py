import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from quii_helper.camera.connection.session import CameraPreviewSession
from quii_helper.direct import preview


@pytest.mark.parametrize(
    "stage", ["socket", "connect", "probe", "construct", "start"]
)
def test_failed_preview_start_releases_owned_resources(monkeypatch, stage):
    config = SimpleNamespace(
        ust_address="test",
        ust_test_address="test",
        rng_seed=0,
        log_peer_diagnostics=False,
    )
    sock = Mock()
    sock.getsockname.return_value = ("127.0.0.1", 1234)
    tunnel = Mock()
    connect = Mock(
        return_value=SimpleNamespace(
            response=object(), request_session_id=1, session_flag="test"
        )
    )
    probe = Mock(return_value=(object(), ("127.0.0.1", 1), ("127.0.0.1", 1)))
    construct = Mock(return_value=tunnel)
    for name, value in {
        "validate_camera_app_config": Mock(),
        "discover_public_ip": lambda: "127.0.0.1",
        "discover_local_ips": lambda: ["127.0.0.1"],
        "make_dualstack_udp_socket": lambda: sock,
        "establish_direct_p2pconnect_session": connect,
        "probe_and_select_direct_peers": probe,
        "DirectKcpQuiiTunnel": construct,
    }.items():
        monkeypatch.setattr(preview, name, value)
    failure = RuntimeError("startup failed")
    {
        "socket": sock.getsockname,
        "connect": connect,
        "probe": probe,
        "construct": construct,
        "start": tunnel.start,
    }[stage].side_effect = failure
    with pytest.raises(RuntimeError) as raised:
        preview.open_direct_preview(config, credentials=object())
    assert raised.value is failure
    sock.close.assert_called_once_with()
    assert tunnel.close.call_count == (1 if stage == "start" else 0)


@pytest.mark.parametrize("acked", [False, True])
def test_cancelled_setup_does_not_send_more_commands(acked):
    stop = threading.Event()
    tunnel = Mock()

    def wait(timeout):
        stop.set()
        return acked

    tunnel.wait_quii_setup_ack.side_effect = wait
    session = CameraPreviewSession(None, None, None, None, tunnel)
    assert session.start_live_preview(stop_event=stop) is False
    tunnel.send_quii_setup.assert_not_called()
    tunnel.send_quii_play.assert_not_called()
