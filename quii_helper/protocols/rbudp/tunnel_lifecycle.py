import threading
import time

from quii_helper.network import is_private_ipv4


class RbUdpTunnelLifecycleMixin:
    def start(self) -> None:
        if self._udp_sock is None:
            raise RuntimeError("RB UDP tunnel requires an existing UDP socket")
        self._dbg(
            "start",
            peer=self._peer_addr,
            transport_peer=self._transport_peer_addr,
            p2p_session_flag=self._p2p_session_flag,
        )
        self._udp_sock.settimeout(0.5)
        self._thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._thread.start()
        self._play_sync_thread = threading.Thread(
            target=self._play_sync_loop, daemon=True
        )
        self._play_sync_thread.start()
        self._prime_lan_peer_if_needed()
        self._send_control_bootstrap()
        threading.Thread(target=self._keepalive_loop, daemon=True).start()
        if not self._connected.wait(self.config.connect_timeout):
            raise TimeoutError(
                "timed out waiting for RB UDP logical connect response"
            )
        self._quii_ready.wait(0.5)

    def flush_fragment_partials(self) -> None:
        self._wrapped_fragments.emit_active()

    def close(self) -> None:
        self._stop.set()
        self._wrapped_fragments.emit_active()
        if self._udp_sock is not None:
            try:
                self._udp_sock.close()
            except Exception:
                pass

    def _prime_lan_peer_if_needed(self) -> None:
        lan_same_peer = (
            self._peer_addr == self._transport_peer_addr
            and is_private_ipv4(self._peer_addr[0])
        )
        if not lan_same_peer:
            return
        self._prime_lan_transport()
        deadline = time.time() + 1.5
        while time.time() < deadline and self._transport_frames_seen == 0:
            time.sleep(0.05)
