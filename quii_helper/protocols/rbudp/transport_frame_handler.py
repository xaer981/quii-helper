from quii_helper.network import is_private_ipv4
from quii_helper.protocols.p2p.transport_packets import (
    build_p2p_transport_ack,
    parse_p2p_transport_frame,
)


class RbUdpTransportFrameMixin:
    def _consume_transport_frame(self, data: bytes) -> bool:
        try:
            frame = parse_p2p_transport_frame(data)
        except Exception as exc:
            if len(data) == 164:
                self._dbg(
                    "transport_parse_fail",
                    error=repr(exc),
                    prefix=data[:32].hex(),
                )
            return False
        if frame.session_flag != self._p2p_session_flag and not (
            self._p2p_session_flag.startswith(frame.session_flag)
            or frame.session_flag.startswith(self._p2p_session_flag)
        ):
            self._dbg(
                "transport_session_mismatch",
                got=frame.session_flag,
                want=self._p2p_session_flag,
                remote_ip=frame.remote_ip,
                remote_port=frame.remote_port,
                tail=frame.tail_code,
                packet_type=frame.packet_type_flag,
            )
            return False
        self._dbg(
            "transport_frame",
            remote_ip=frame.remote_ip,
            remote_port=frame.remote_port,
            tail=frame.tail_code,
            packet_type=frame.packet_type_flag,
        )
        self._transport_frames_seen += 1
        self._handle_late_bootstrap_progress()
        if frame.is_request and frame.remote_ip and frame.remote_port:
            self._ack_transport_rebind(frame)
        return True

    def _handle_late_bootstrap_progress(self) -> None:
        if self._late_bootstrap_pending <= 0:
            return
        self._late_bootstrap_pending -= 1
        if self._late_bootstrap_pending != 0:
            return
        self._send_control_bootstrap()
        if self._late_post_bootstrap_prime:
            self._prime_lan_transport()
            self._late_post_bootstrap_prime = False

    def _ack_transport_rebind(self, frame) -> None:
        ack = build_p2p_transport_ack(
            frame, local_udp_port=self._udp_sock.getsockname()[1]
        )
        new_peer = (frame.remote_ip, frame.remote_port)
        self._transport_peer_addr = new_peer
        self._send_transport_udp(ack, peer_addr=new_peer)
        current_peer_is_private = is_private_ipv4(self._peer_addr[0])
        if current_peer_is_private:
            self._dbg(
                "ignore_transport_peer_rebind",
                current_peer=self._peer_addr,
                transport_peer=new_peer,
                transport_keepalive_peer=self._transport_peer_addr,
            )
            return
        peer_changed = new_peer != self._peer_addr
        self._peer_addr = new_peer
        if (
            self.local_id == 0
            and self.remote_id == 0
            and (peer_changed or self._bootstrap_sent_to != new_peer)
        ):
            self._dbg("bootstrap_to_new_transport_peer", peer=new_peer)
            self._send_control_bootstrap()
