from types import SimpleNamespace

import pytest

from quii_helper.protocols.rbudp.tunnel.lifecycle import (
    RbUdpTunnelLifecycle,
)


class _Event:
    def __init__(self) -> None:
        self.set_called = False

    def is_set(self) -> bool:
        return self.set_called

    def set(self) -> None:
        self.set_called = True

    def wait(self, timeout: float | None = None) -> bool:
        return False


class _Fragments:
    def __init__(self) -> None:
        self.emitted = 0

    def emit_active(self) -> None:
        self.emitted += 1


class _Socket:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def settimeout(self, timeout: float) -> None:
        pass


class _Threads:
    def __init__(self) -> None:
        self.joined = False

    def join_all(self, *, timeout: float = 0.75) -> None:
        self.joined = True


class _Owner:
    def __init__(self) -> None:
        self._connected = _Event()
        self._p2p_session_flag = "session"
        self._peer_addr = ("127.0.0.1", 1000)
        self._quii_ready = _Event()
        self._stop = _Event()
        self._threads = _Threads()
        self._transport_frames_seen = 0
        self._transport_peer_addr = ("127.0.0.1", 1000)
        self._udp_sock = None
        self._wrapped_fragments = _Fragments()
        self.config = SimpleNamespace(connect_timeout=0.01)
        self.debug: list[tuple[str, dict[str, object]]] = []
        self.lifecycle = RbUdpTunnelLifecycle(self)

    def _dbg(self, message: str, **kwargs: object) -> None:
        self.debug.append((message, kwargs))

    def _keepalive_loop(self) -> None:
        pass

    def _play_sync_loop(self) -> None:
        pass

    def _prime_lan_transport(self, *, seq_base: int | None = None) -> None:
        pass

    def _receive_loop(self) -> None:
        pass

    def _send_control_bootstrap(self) -> None:
        pass


class RbUdpTunnelLifecycleTests:
    def test_start_requires_existing_udp_socket(self) -> None:
        owner = _Owner()

        with pytest.raises(
            RuntimeError, match="requires an existing UDP socket"
        ):
            owner.lifecycle.start()

    def test_close_stops_threads_emits_fragments_and_closes_socket(
        self,
    ) -> None:
        owner = _Owner()
        sock = _Socket()
        owner._udp_sock = sock

        owner.lifecycle.close()

        assert owner._stop.is_set()
        assert 1 == owner._wrapped_fragments.emitted
        assert owner._threads.joined
        assert sock.closed
        assert owner._udp_sock is None
