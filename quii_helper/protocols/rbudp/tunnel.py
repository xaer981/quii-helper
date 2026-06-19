import socket
import threading
from typing import Any

from quii_helper.config import AutonomousConfig
from quii_helper.protocols.p2p.models import (
    P2PConnectResponse,
    ParsedP2PTestResponse,
)
from quii_helper.protocols.rbudp.constants import RbUdpProtocolConstants
from quii_helper.protocols.rbudp.control_flow import RbUdpControlFlowMixin
from quii_helper.protocols.rbudp.control_handler import (
    RbUdpControlHandlerMixin,
)
from quii_helper.protocols.rbudp.fragments import RbUdpWrappedFragmentAssembler
from quii_helper.protocols.rbudp.keepalive import RbUdpKeepaliveMixin
from quii_helper.protocols.rbudp.lane_state import RbUdpLaneStateMixin
from quii_helper.protocols.rbudp.lanes import (
    RbUdpLane,
    build_rbudp_lane_states,
)
from quii_helper.protocols.rbudp.live_commands import RbUdpLiveCommandsMixin
from quii_helper.protocols.rbudp.models import (
    ParsedRbUdpControlPacket,
    ParsedRbUdpWrappedPacket,
)
from quii_helper.protocols.rbudp.payload_queue import RbUdpPayloadQueueMixin
from quii_helper.protocols.rbudp.play_sync import RbUdpPlaySyncMixin
from quii_helper.protocols.rbudp.receive_loop import RbUdpReceiveLoopMixin
from quii_helper.protocols.rbudp.receive_stream import (
    RbUdpReceiveStreamAssembler,
)
from quii_helper.protocols.rbudp.transport_io import RbUdpTransportIOMixin
from quii_helper.protocols.rbudp.tunnel_lifecycle import (
    RbUdpTunnelLifecycleMixin,
)
from quii_helper.protocols.rbudp.wrapped_flow import RbUdpWrappedFlowMixin


class RbUdpQuiiTunnel(
    RbUdpTunnelLifecycleMixin,
    RbUdpPayloadQueueMixin,
    RbUdpLiveCommandsMixin,
    RbUdpReceiveLoopMixin,
    RbUdpControlHandlerMixin,
    RbUdpPlaySyncMixin,
    RbUdpControlFlowMixin,
    RbUdpWrappedFlowMixin,
    RbUdpKeepaliveMixin,
    RbUdpLaneStateMixin,
    RbUdpTransportIOMixin,
    RbUdpProtocolConstants,
):
    def __init__(
        self,
        config: AutonomousConfig,
        response: P2PConnectResponse,
        test_response: ParsedP2PTestResponse,
        request_session_id: int,
        udp_sock: socket.socket | None = None,
        peer_addr: tuple[str, int] | None = None,
        transport_peer_addr: tuple[str, int] | None = None,
        p2p_session_flag: str | None = None,
    ):
        self.config = config
        self.response = response
        self.test_response = test_response
        self.request_session_id = request_session_id
        self.src_ids = [
            (config.logical_src_id_base + i) & 0xFFFFFFFF
            for i in range(max(1, int(config.logical_src_id_count)))
        ]
        self.src_id = self.src_ids[0]
        self.dest_id: int | None = None
        self.dest_ids: dict[int, int] = {}
        self._lane_states: list[RbUdpLane] = build_rbudp_lane_states(
            src_ids=self.src_ids,
            bootstrap_word4=self.CONTROL_BOOTSTRAP_WORD4,
            bootstrap_remote_id=self.BOOTSTRAP_REMOTE_ID,
            bootstrap_local_ids=self.BOOTSTRAP_LOCAL_IDS,
        )
        self._connected = threading.Event()
        self._quii_ready = threading.Event()
        self._quii_setup_acked = threading.Event()
        self._quii_play_sent = threading.Event()
        self._stop = threading.Event()
        self._init_payload_queue()
        self._udp_sock = udp_sock
        self._peer_addr = peer_addr or (
            test_response.address,
            test_response.port,
        )
        self._transport_peer_addr = transport_peer_addr or (
            test_response.address,
            test_response.port,
        )
        self._p2p_session_flag = (
            p2p_session_flag or response.session_flag or ""
        )
        self.local_id = 0
        self.remote_id = 0
        self.word4 = self.CONTROL_BOOTSTRAP_WORD4
        self.word8 = 0
        self.status_word = self.CONTROL_BOOTSTRAP_STATUS
        self._forced_transition = False
        self._transport_frames_seen = 0
        self._late_bootstrap_pending = 0
        self._late_post_bootstrap_prime = False
        self._thread: threading.Thread | None = None
        self._play_sync_thread: threading.Thread | None = None
        self._last_control: ParsedRbUdpControlPacket | None = None
        self._last_wrapped: ParsedRbUdpWrappedPacket | None = None
        self._bootstrap_sent_to: tuple[str, int] | None = None
        self._wrapped_debug_seen: set[str] = set()
        self._wrapped_fragments = RbUdpWrappedFragmentAssembler(
            debug=self._dbg,
            lane_for_packet_words=self._lane_for_packet_words,
            send_fragment_ack=self._send_fragment_ack,
            handle_wrapped=self._handle_wrapped,
            queue_payload=self._queue_payload,
        )
        self._receive_streams = RbUdpReceiveStreamAssembler(
            debug=self._dbg,
            lane_for_packet_words=self._lane_for_packet_words,
            send_fragment_ack=self._send_fragment_ack,
            handle_wrapped=self._handle_wrapped,
        )
        self._direct_data_next_ids: dict[tuple[int, int], int] = {}
        self._direct_data_stats: dict[str, int] = {
            "acked": 0,
            "replayed": 0,
            "gaps": 0,
        }
        self.stream_payload_early_filler_count = 0
        self.stream_payload_early_count = 0
        self.stream_payload_filler_count = 0
        self.stream_payload_count = 0

    def play_sync_summary(self) -> list[dict[str, object]]:
        return [
            {
                "src_id": hex(int(lane["src_id"])),
                "active": bool(lane["play_sync_active"]),
                "sent": int(lane["play_sync_sent_count"]),
                "remaining": int(lane["play_sync_remaining"]),
            }
            for lane in self._lane_states
        ]

    def fragment_summary(self) -> dict[str, object]:
        return {
            **self._wrapped_fragments.summary(),
            "rbudp_receive_stream": self._receive_streams.summary(),
            "direct_data_acked": self._direct_data_stats["acked"],
            "direct_data_replayed": self._direct_data_stats["replayed"],
            "direct_data_gaps": self._direct_data_stats["gaps"],
        }

    def has_pending_receive_stream_buffers(self) -> bool:
        return self._receive_streams.has_pending()

    def _dbg(self, message: str, **kwargs: Any) -> None:
        if not getattr(self.config, "rbudp_debug", False):
            return
        details = " ".join(f"{key}={value}" for key, value in kwargs.items())
        if details:
            print(f"[RbUdp] {message} {details}")
        else:
            print(f"[RbUdp] {message}")


DirectKcpQuiiTunnel = RbUdpQuiiTunnel
