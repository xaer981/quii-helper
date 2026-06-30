import socket
import time
from typing import Protocol, cast

from quii_helper.network import is_private_ipv4
from quii_helper.protocols.rbudp.tunnel.threads import RbUdpBackgroundThreads


class _EventLike(Protocol):
    def is_set(self) -> bool: ...

    def set(self) -> None: ...

    def wait(self, timeout: float | None = None) -> bool: ...


class _LifecycleConfig(Protocol):
    connect_timeout: float


class _WrappedFragmentsLike(Protocol):
    def emit_active(self) -> None: ...


class RbUdpTunnelLifecycleOwner(Protocol):
    _connected: _EventLike
    _p2p_session_flag: str
    _peer_addr: tuple[str, int]
    _quii_ready: _EventLike
    _stop: _EventLike
    _threads: RbUdpBackgroundThreads
    _transport_frames_seen: int
    _transport_peer_addr: tuple[str, int]
    _udp_sock: socket.socket | None
    _wrapped_fragments: _WrappedFragmentsLike
    config: _LifecycleConfig

    def _dbg(self, message: str, **kwargs: object) -> None: ...

    def _keepalive_loop(self) -> None: ...

    def _play_sync_loop(self) -> None: ...

    def _prime_lan_transport(self, *, seq_base: int | None = None) -> None: ...

    def _receive_loop(self) -> None: ...

    def _send_control_bootstrap(self) -> None: ...


class RbUdpTunnelLifecycle:
    """Coordinate RBUDP tunnel startup and shutdown side effects."""

    def __init__(self, owner: RbUdpTunnelLifecycleOwner) -> None:
        self._owner = owner

    def start(self) -> None:
        owner = self._owner
        if owner._udp_sock is None:
            raise RuntimeError("RB UDP tunnel requires an existing UDP socket")
        owner._dbg(
            "start",
            peer=owner._peer_addr,
            transport_peer=owner._transport_peer_addr,
            p2p_session_flag=owner._p2p_session_flag,
        )
        owner._udp_sock.settimeout(0.5)
        owner._threads.start_receive_loop(owner._receive_loop)
        owner._threads.start_play_sync_loop(owner._play_sync_loop)
        self.prime_lan_peer_if_needed()
        owner._send_control_bootstrap()
        owner._threads.start_keepalive_loop(owner._keepalive_loop)
        if not owner._connected.wait(owner.config.connect_timeout):
            raise TimeoutError(
                "timed out waiting for RB UDP logical connect response"
            )
        owner._quii_ready.wait(0.5)

    def flush_fragment_partials(self) -> None:
        self._owner._wrapped_fragments.emit_active()

    def close(self) -> None:
        owner = self._owner
        owner._stop.set()
        owner._wrapped_fragments.emit_active()
        self.join_background_threads()
        if owner._udp_sock is not None:
            try:
                owner._udp_sock.close()
            except Exception:
                pass
            owner._udp_sock = None

    def join_background_threads(self) -> None:
        self._owner._threads.join_all(timeout=0.75)

    def prime_lan_peer_if_needed(self) -> None:
        owner = self._owner
        lan_same_peer = (
            owner._peer_addr == owner._transport_peer_addr
            and is_private_ipv4(owner._peer_addr[0])
        )
        if not lan_same_peer:
            return
        owner._prime_lan_transport()
        deadline = time.time() + 1.5
        while time.time() < deadline and owner._transport_frames_seen == 0:
            time.sleep(0.05)
