from quii_helper.protocols.rbudp.core.models import ParsedRbUdpWrappedPacket


class RbUdpWrappedFrameHandlerMixin:
    _wrapped_debug_seen: set[str]
    dest_id: int | None
    dest_ids: dict[int, int]
    local_id: int
    remote_id: int
    src_id: int
    word4: int
    word8: int

    def _handle_parsed_wrapped_frame(
        self,
        parsed,
        *,
        frame_hex: str,
        should_debug: bool,
        wrapped: ParsedRbUdpWrappedPacket,
    ) -> None:
        self._debug_parsed_frame(
            parsed, frame_hex=frame_hex, should_debug=should_debug
        )

        if parsed.connect is not None:
            self._handle_connect_frame(parsed.connect)
            return

        if (
            parsed.data is not None
            and not parsed.data.is_ack
            and parsed.data.payload
        ):
            self._handle_data_frame(parsed.data, wrapped=wrapped)
            return

        if (
            parsed.data is not None
            and parsed.data.is_ack
            and parsed.data.seq == 0
        ):
            self._handle_setup_ack_frame(parsed.data)

    def _handle_data_frame(
        self, data, *, wrapped: ParsedRbUdpWrappedPacket
    ) -> None:
        # Native KcpLinkClient::OnP2PRequData does not ACK inbound data frames.
        # Reliability is handled by the outer RBUDP receive stream ACK.
        self._queue_payload(
            data.payload,
            source="wrapped_quii",
            packet_type_flag=data.packet_type_flag,
            command=data.command,
            seq=data.seq,
            dest_id=data.dest_id,
            src_id=data.src_id,
        )

    def _ack_data_frame(
        self, data, *, wrapped: ParsedRbUdpWrappedPacket
    ) -> None:
        lane = self._lane_for_src_id(data.dest_id)
        if lane is None:
            self._dbg(
                "skip_quii_data_ack_no_lane",
                seq=hex(data.seq),
                dest_id=hex(data.dest_id),
                src_id=hex(data.src_id),
            )
            return
        self._send_wrapped_data_ack(
            lane,
            seq=data.seq,
            src_id=data.dest_id,
            dest_id=data.src_id,
            payload_length=data.body_length_field,
            word4=wrapped.word8,
            word8=wrapped.word4,
        )

    def _handle_setup_ack_frame(self, data) -> None:
        ack_lane = self._lane_for_src_id(data.dest_id)
        if ack_lane is not None:
            ack_lane["quii_setup_acked"] = True
        self._dbg(
            "recv_quii_setup_ack",
            seq=hex(data.seq),
            dest_id=hex(data.dest_id),
            src_id=hex(data.src_id),
        )
        self._quii_setup_acked.set()

    def _debug_unparsed_wrapped_once(
        self, inner_packet: bytes, exc: Exception
    ) -> None:
        wrapped_key = inner_packet.hex()
        if wrapped_key in self._wrapped_debug_seen:
            return
        self._wrapped_debug_seen.add(wrapped_key)
        self._dbg(
            "recv_wrapped_unparsed",
            error=repr(exc),
            inner_hex=wrapped_key,
        )

    def _debug_parsed_frame(
        self, parsed, *, frame_hex: str, should_debug: bool
    ) -> None:
        if not should_debug:
            return
        if parsed.connect is not None:
            self._dbg(
                "recv_wrapped_connect_parsed",
                packet_type=parsed.connect.packet_type_flag,
                result_code=parsed.connect.result_code,
                command=hex(parsed.connect.command),
                payload_length=parsed.connect.payload_length,
                connect_id=hex(parsed.connect.connect_id),
                dest_id=hex(parsed.connect.dest_id),
                ok=parsed.connect.ok,
                inner_hex=frame_hex,
            )
        elif parsed.data is not None:
            self._dbg(
                "recv_wrapped_data_parsed",
                packet_type=parsed.data.packet_type_flag,
                command=hex(parsed.data.command),
                seq=hex(parsed.data.seq),
                payload_length=parsed.data.payload_length,
                dest_id=hex(parsed.data.dest_id),
                src_id=hex(parsed.data.src_id),
                inner_hex=frame_hex,
            )

    def _handle_connect_frame(self, connect) -> None:
        connect_lane = self._lane_for_src_id(connect.connect_id)
        connect_valid = (
            connect.packet_type_flag == 1
            and connect_lane is not None
            and connect.connect_id == int(connect_lane["src_id"])
            and connect.dest_id != 0
        )
        if not connect_valid:
            return
        self.dest_ids[connect.connect_id] = connect.dest_id
        if self.dest_id is None:
            self.src_id = connect.connect_id
            self.dest_id = connect.dest_id
            self.word4 = int(connect_lane["word4"])
            self.word8 = int(connect_lane["word8"])
            self.local_id = int(connect_lane["local_id"])
            self.remote_id = int(connect_lane["remote_id"])
        if not bool(connect_lane["setup_probe_sent"]):
            self._send_wrapped_setup_probe(
                connect_lane,
                connect_id=connect.connect_id,
                dest_id=connect.dest_id,
            )
        self._dbg(
            "connect_ok",
            connect_id=hex(connect.connect_id),
            dest_id=hex(connect.dest_id),
            active_src_id=hex(self.src_id),
        )
        self._connected.set()
