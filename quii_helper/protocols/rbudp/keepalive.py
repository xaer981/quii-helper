import random
import time

from quii_helper.network import is_private_ipv4
from quii_helper.protocols.p2p.transport_packets import build_p2p_active_packet


class RbUdpKeepaliveMixin:
    def _keepalive_loop(self):
        local_udp_port = self._udp_sock.getsockname()[1]
        time.sleep(1.0)
        while not self._stop.is_set():
            try:
                lan_same_peer = (
                    self._peer_addr == self._transport_peer_addr
                    and is_private_ipv4(self._peer_addr[0])
                )
                if not lan_same_peer:
                    packet = build_p2p_active_packet(
                        session_flag=self._p2p_session_flag,
                        seq=random.randrange(0x100000000),
                        local_udp_port=local_udp_port,
                        tail_code=3,
                    )
                    self._send_transport_udp(packet)
                sent_established = False
                for lane in self._lane_states:
                    if int(lane["local_id"]) and int(lane["remote_id"]):
                        sent_established = True
                        if not bool(lane["established_sent"]):
                            self._send_control_established(lane)
                if (
                    not sent_established
                    and self._bootstrap_sent_to != self._peer_addr
                ):
                    self._send_control_bootstrap()
            except Exception:
                pass
            time.sleep(1.0)
