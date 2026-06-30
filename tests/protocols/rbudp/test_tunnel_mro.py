from quii_helper.protocols.rbudp.tunnel.session import RbUdpQuiiTunnel

CONTROL_MIXIN_NAMES = {
    "RbUdpControlAckStatusMixin",
    "RbUdpControlFlowMixin",
    "RbUdpControlHandlerMixin",
    "RbUdpControlHandshakeMixin",
    "RbUdpControlLaneUpdateMixin",
    "RbUdpControlPlayStatusMixin",
    "RbUdpControlProgressMixin",
    "RbUdpControlStatusMixin",
    "RbUdpLaneControlMixin",
    "RbUdpLaneStateMixin",
    "RbUdpIncomingPayloadMixin",
    "RbUdpPayloadQueueMixin",
    "RbUdpReceiveLoopMixin",
    "RbUdpTransportFrameMixin",
    "RbUdpTransportIOMixin",
    "RbUdpKeepaliveMixin",
    "RbUdpTunnelLifecycleMixin",
    "RbUdpLiveCommandsMixin",
    "RbUdpPlayProbeMixin",
    "RbUdpPlayStageMixin",
    "RbUdpPlaySyncMixin",
    "RbUdpWrappedFlowMixin",
    "RbUdpWrappedFrameHandlerMixin",
    "RbUdpWrappedHandlerMixin",
    "RbUdpWrappedLaneMixin",
    "RbUdpWrappedSenderMixin",
}


class RbUdpTunnelMroTests:
    def require_mixin_name_not_in_mro(self, name: str) -> None:
        assert name not in {cls.__name__ for cls in RbUdpQuiiTunnel.__mro__}

    def test_cross_mixin_methods_resolve_to_real_implementations(self) -> None:
        assert callable(RbUdpQuiiTunnel._start_play_sync)

    def test_tunnel_mro_has_no_control_mixin_names(self) -> None:
        for name in CONTROL_MIXIN_NAMES:
            self.require_mixin_name_not_in_mro(name)

    def test_tunnel_uses_explicit_control_flow_component(self) -> None:
        assert callable(RbUdpQuiiTunnel._send_pending_established)
        assert callable(RbUdpQuiiTunnel._send_control_bootstrap)
        assert callable(RbUdpQuiiTunnel._send_fragment_ack)

    def test_tunnel_uses_explicit_control_handler_component(self) -> None:
        assert callable(RbUdpQuiiTunnel._handle_control)
        assert callable(RbUdpQuiiTunnel._is_quii_play_ack_control)

    def test_tunnel_uses_explicit_control_ack_and_lane_update_components(
        self,
    ) -> None:
        assert callable(RbUdpQuiiTunnel._send_offset_ack)
        assert callable(RbUdpQuiiTunnel._apply_control_lane_ids)

    def test_tunnel_uses_explicit_control_play_status_component(self) -> None:
        assert callable(RbUdpQuiiTunnel._handle_play_late_status)
        assert callable(RbUdpQuiiTunnel._handle_play_sync_status)

    def test_tunnel_uses_explicit_control_progress_component(self) -> None:
        assert callable(RbUdpQuiiTunnel._handle_flow_control)
        assert callable(RbUdpQuiiTunnel._handle_progress_control)
        assert callable(RbUdpQuiiTunnel._start_play_sync_from_control)

    def test_tunnel_uses_explicit_control_handshake_component(self) -> None:
        assert callable(RbUdpQuiiTunnel._handle_syn_ack_control)

    def test_tunnel_uses_explicit_lifecycle_component(self) -> None:
        self.require_mixin_name_not_in_mro("RbUdpTunnelLifecycleMixin")
        assert callable(RbUdpQuiiTunnel.start)
        assert callable(RbUdpQuiiTunnel.close)
        assert callable(RbUdpQuiiTunnel.flush_fragment_partials)

    def test_tunnel_uses_explicit_payload_queue_component(self) -> None:
        self.require_mixin_name_not_in_mro("RbUdpPayloadQueueMixin")
        assert callable(RbUdpQuiiTunnel.recv_packet)
        assert callable(RbUdpQuiiTunnel.recv_payload)

    def test_receive_loop_uses_explicit_incoming_payload_component(
        self,
    ) -> None:
        self.require_mixin_name_not_in_mro("RbUdpIncomingPayloadMixin")

    def test_tunnel_uses_explicit_receive_loop_component(self) -> None:
        self.require_mixin_name_not_in_mro("RbUdpReceiveLoopMixin")
        assert callable(RbUdpQuiiTunnel._receive_loop)

    def test_tunnel_uses_explicit_keepalive_component(self) -> None:
        self.require_mixin_name_not_in_mro("RbUdpKeepaliveMixin")

    def test_tunnel_uses_explicit_transport_io_component(self) -> None:
        self.require_mixin_name_not_in_mro("RbUdpTransportIOMixin")
        assert callable(RbUdpQuiiTunnel._send_udp)
        assert callable(RbUdpQuiiTunnel._send_transport_udp)
        assert callable(RbUdpQuiiTunnel._prime_lan_transport)

    def test_tunnel_uses_explicit_transport_frame_component(self) -> None:
        self.require_mixin_name_not_in_mro("RbUdpTransportFrameMixin")

    def test_tunnel_uses_explicit_live_command_sender(self) -> None:
        self.require_mixin_name_not_in_mro("RbUdpLiveCommandsMixin")
        assert callable(RbUdpQuiiTunnel.send_quii_setup)
        assert callable(RbUdpQuiiTunnel.send_quii_play)
        assert callable(RbUdpQuiiTunnel.send_quii_keepalive)

    def test_play_sync_uses_explicit_stage_and_probe_components(self) -> None:
        self.require_mixin_name_not_in_mro("RbUdpPlaySyncMixin")
        self.require_mixin_name_not_in_mro("RbUdpPlayStageMixin")
        self.require_mixin_name_not_in_mro("RbUdpPlayProbeMixin")
        assert callable(RbUdpQuiiTunnel._play_sync_loop)
        assert callable(RbUdpQuiiTunnel._maybe_send_play_probe)
        assert callable(RbUdpQuiiTunnel._maybe_send_play_stage_controls)

    def test_tunnel_uses_explicit_lane_state_component(self) -> None:
        assert callable(RbUdpQuiiTunnel._next_lane_nonce)
        assert callable(RbUdpQuiiTunnel._lane_for_packet_words)
        assert callable(RbUdpQuiiTunnel._lane_for_src_id)

    def test_tunnel_uses_explicit_lane_control_component(self) -> None:
        assert callable(RbUdpQuiiTunnel._send_lane_control)
        assert callable(RbUdpQuiiTunnel._native_control_status_word)

    def test_tunnel_skips_empty_wrapped_flow_abstraction(self) -> None:
        self.require_mixin_name_not_in_mro("RbUdpWrappedFlowMixin")

    def test_tunnel_uses_explicit_wrapped_sender_component(self) -> None:
        self.require_mixin_name_not_in_mro("RbUdpWrappedSenderMixin")
        assert callable(RbUdpQuiiTunnel._send_wrapped)
        assert callable(RbUdpQuiiTunnel._send_wrapped_connect)
        assert callable(RbUdpQuiiTunnel._send_wrapped_data_ack)

    def test_tunnel_uses_explicit_wrapped_frame_handler_component(
        self,
    ) -> None:
        self.require_mixin_name_not_in_mro("RbUdpWrappedFrameHandlerMixin")
        assert callable(RbUdpQuiiTunnel._handle_wrapped)

    def test_tunnel_uses_explicit_wrapped_handler_component(self) -> None:
        self.require_mixin_name_not_in_mro("RbUdpWrappedHandlerMixin")
        assert callable(RbUdpQuiiTunnel._handle_wrapped)
