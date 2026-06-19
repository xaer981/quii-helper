RBUDP_MARKER = 0xFFABEFC1
RBUDP_DIRECT_STATUS = 0x00001900
RBUDP_STREAM_STATUS = 0x00000500
RBUDP_STATUS_MASK = 0x0000FFFF
RBUDP_DATA_STATUS_FLAG = 0x00001000


class RbUdpIncomingPayloadMixin:
    _direct_data_next_ids: dict[tuple[int, int], int]
    _direct_data_stats: dict[str, int]

    def _handle_rbudp_data_packet(self, data: bytes) -> bool:
        return self._receive_streams.feed(data)

    def _maybe_start_wrapped_fragment(
        self, data: bytes, *, status_word: int, inner_marker: int
    ) -> bool:
        if (
            (status_word & RBUDP_STATUS_MASK) != RBUDP_DIRECT_STATUS
            or inner_marker != 0xFFFFFFFF
            or len(data) < 0x24
        ):
            return False
        inner_total_length = int.from_bytes(data[0x20:0x24], "little")
        direct_end = 0x1C + inner_total_length
        return direct_end > len(data) and self._wrapped_fragments.start(data)

    def _handle_stream_payload_packet(self, data: bytes) -> None:
        payload = data[0x1C:]
        is_filler = bool(payload) and all(byte == 0xBB for byte in payload)
        if not is_filler and self._wrapped_fragments.append(data):
            return

        after_play = self._quii_play_sent.is_set()
        log_label = (
            "recv_stream_payload"
            if after_play
            else "recv_stream_payload_early"
        )
        if is_filler:
            log_label += "_filler"
        self._count_stream_payload(after_play=after_play, is_filler=is_filler)
        self._dbg(
            log_label,
            packet_len=len(data),
            payload_len=len(payload),
            **self._packet_meta(data, payload),
        )
        if after_play and not is_filler:
            self._queue_payload(
                payload,
                source="stream_payload",
                packet_len=len(data),
                payload_len=len(payload),
                **self._packet_meta_raw(data),
            )

    def _handle_direct_quii_blob_packet(self, data: bytes) -> None:
        if self._wrapped_fragments.append(data):
            return
        payload = data[0x1C:]
        self._ack_direct_data_packet(data, payload_len=len(payload))
        after_play = self._quii_play_sent.is_set()
        self._dbg(
            "recv_direct_quii_blob",
            packet_len=len(data),
            payload_len=len(payload),
            **self._packet_meta(data, payload),
        )
        if after_play and payload:
            self._queue_payload(
                payload,
                source="direct_quii_blob",
                packet_len=len(data),
                payload_len=len(payload),
                **self._packet_meta_raw(data),
            )

    def _ack_direct_data_packet(
        self, data: bytes, *, payload_len: int
    ) -> None:
        meta = self._packet_meta_raw(data)
        key = (meta["word4"], meta["word8"])
        previous_next_id = self._direct_data_next_ids.get(key)
        packet_local_id = int(meta["local_id"])
        if previous_next_id is None or packet_local_id == previous_next_id:
            next_id = (packet_local_id + payload_len) & 0xFFFFFFFF
            self._direct_data_next_ids[key] = next_id
        elif packet_local_id < previous_next_id:
            next_id = previous_next_id
            self._direct_data_stats["replayed"] += 1
        else:
            next_id = previous_next_id
            self._direct_data_stats["gaps"] += 1

        lane = self._lane_for_packet_words(
            word4=meta["word4"], word8=meta["word8"]
        )
        if lane is None:
            self._dbg(
                "skip_direct_data_ack_no_lane",
                word4=hex(meta["word4"]),
                word8=hex(meta["word8"]),
                local_id=packet_local_id,
                remote_id=meta["remote_id"],
                next_local_id=next_id,
            )
            return

        self._direct_data_stats["acked"] += 1
        self._send_fragment_ack(
            lane,
            int(meta["remote_id"]),
            next_id,
            word4=meta["word8"],
            word8=meta["word4"],
            log_label="send_control_direct_data_ack",
        )

    def _count_stream_payload(
        self, *, after_play: bool, is_filler: bool
    ) -> None:
        if after_play:
            if is_filler:
                self.stream_payload_filler_count += 1
            else:
                self.stream_payload_count += 1
            return
        if is_filler:
            self.stream_payload_early_filler_count += 1
        else:
            self.stream_payload_early_count += 1

    @staticmethod
    def _packet_meta(data: bytes, payload: bytes) -> dict:
        meta = RbUdpIncomingPayloadMixin._packet_meta_raw(data)
        return {
            "word4": hex(meta["word4"]),
            "word8": hex(meta["word8"]),
            "local_id": meta["local_id"],
            "remote_id": meta["remote_id"],
            "prefix": payload[:32].hex(),
        }

    @staticmethod
    def _packet_meta_raw(data: bytes) -> dict:
        return {
            "word4": int.from_bytes(data[0x04:0x08], "little"),
            "word8": int.from_bytes(data[0x08:0x0C], "little"),
            "local_id": int.from_bytes(data[0x0C:0x10], "little"),
            "remote_id": int.from_bytes(data[0x10:0x14], "little"),
        }
