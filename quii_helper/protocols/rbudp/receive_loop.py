from quii_helper.protocols.rbudp.control_packets import (
    parse_rb_udp_control_packet,
)
from quii_helper.protocols.rbudp.incoming_payload import (
    RBUDP_DATA_STATUS_FLAG,
    RBUDP_DIRECT_STATUS,
    RBUDP_MARKER,
    RBUDP_STATUS_MASK,
    RBUDP_STREAM_STATUS,
    RbUdpIncomingPayloadMixin,
)
from quii_helper.protocols.rbudp.transport_frame_handler import (
    RbUdpTransportFrameMixin,
)
from quii_helper.protocols.rbudp.wrapped_packets import (
    parse_rb_udp_wrapped_packet,
)


class RbUdpReceiveLoopMixin(
    RbUdpTransportFrameMixin, RbUdpIncomingPayloadMixin
):
    def _receive_loop(self) -> None:
        while not self._stop.is_set():
            try:
                data, _addr = self._udp_sock.recvfrom(4096)
            except TimeoutError:
                continue
            except OSError:
                break
            if len(data) < 4:
                continue
            marker = int.from_bytes(data[:4], "little")
            if marker == RBUDP_MARKER:
                if len(data) >= 0x1C:
                    status_word = int.from_bytes(data[0x14:0x18], "little")
                    if status_word & RBUDP_DATA_STATUS_FLAG:
                        if self._handle_rbudp_data_packet(data):
                            continue
                if len(data) >= 0x20:
                    status_word = int.from_bytes(data[0x14:0x18], "little")
                    inner_marker = int.from_bytes(data[0x1C:0x20], "little")
                    if self._maybe_start_wrapped_fragment(
                        data,
                        status_word=status_word,
                        inner_marker=inner_marker,
                    ):
                        continue
                    if inner_marker != 0xFFFFFFFF:
                        status16 = status_word & RBUDP_STATUS_MASK
                        if status16 == RBUDP_STREAM_STATUS:
                            self._handle_stream_payload_packet(data)
                            continue
                        if status16 == RBUDP_DIRECT_STATUS:
                            self._handle_direct_quii_blob_packet(data)
                            continue
                try:
                    if len(data) == 28:
                        control = parse_rb_udp_control_packet(data)
                        self._handle_control(control)
                        continue
                    if len(data) != 164:
                        wrapped = parse_rb_udp_wrapped_packet(data)
                        self._handle_wrapped(wrapped)
                        continue
                except Exception as exc:
                    self._dbg(
                        "marker_parse_fail",
                        packet_len=len(data),
                        error=repr(exc),
                        prefix=data[:32].hex(),
                    )
            if self._consume_transport_frame(data):
                continue
            if marker != RBUDP_MARKER:
                continue
            try:
                if len(data) == 28:
                    control = parse_rb_udp_control_packet(data)
                    self._handle_control(control)
                else:
                    wrapped = parse_rb_udp_wrapped_packet(data)
                    self._handle_wrapped(wrapped)
            except Exception as exc:
                self._dbg(
                    "marker_retry_parse_fail",
                    packet_len=len(data),
                    error=repr(exc),
                    prefix=data[:32].hex(),
                )
                continue
