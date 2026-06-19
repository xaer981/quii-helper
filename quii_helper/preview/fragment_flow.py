from quii_helper.media.fragmented_media import (
    append_fragmented_media,
    should_start_fragmented_media,
    start_fragmented_media,
)
from quii_helper.preview.packet_summary import (
    attach_media_frame_summary,
    build_quii_packet_summary,
)
from quii_helper.protocols.quii.blob import decode_quii_blob


class PreviewFragmentFlowMixin:
    def _fragment_key(self, *, source: str, meta: dict) -> tuple[object, ...]:
        src_id = meta.get("src_id")
        dest_id = meta.get("dest_id")
        if src_id is not None or dest_id is not None:
            return ("rb_data", src_id, dest_id)
        from_msg_index = meta.get("from_msg_index")
        if from_msg_index is not None:
            return ("remainder", from_msg_index)
        return ("global", source)

    def _consume_fragment(
        self,
        blob: bytes,
        *,
        source: str,
        meta: dict,
        phase: str,
        fragment_key: tuple[object, ...],
    ) -> tuple[bytes, str, dict] | None:
        if self._looks_like_new_media_packet(blob, source=source):
            self._drop_fragmented_media(
                reason="interleaved_media_header",
                source=source,
                meta=meta,
                blob_len=len(blob),
                fragment_key=fragment_key,
            )
            return blob, source, meta

        state = self.fragmented_media_states.get(fragment_key)
        if state is None:
            return blob, source, meta
        decoded_fragment, remainder, fragment_summary = (
            append_fragmented_media(
                state,
                blob,
                self.key,
                source=source,
                meta=meta,
                message_index=self.message_index,
            )
        )
        if fragment_summary.get("taken_len", 0):
            self._inc_fragmented_media_stat("appended")
        self.emit(fragment_summary)
        if decoded_fragment is None:
            return None

        self.fragmented_media_states.pop(fragment_key, None)
        self._inc_fragmented_media_stat("completed")
        self._record_fragmented_media_decoded(
            decoded_fragment,
            blob_len=fragment_summary["expected_body_len"] + 32,
            source="wrapped_quii_fragmented_media",
            meta=dict(decoded_fragment.get("fragmented_media", {})),
        )
        if phase == "live" and self.should_stop_media_collection():
            return None
        if not remainder:
            return None

        source = "wrapped_quii_fragmented_remainder"
        meta = {
            **meta,
            "from_msg_index": self.message_index,
            "remainder_len": len(remainder),
        }
        if len(remainder) < 32:
            self.emit(
                {
                    "msg_index": self.message_index,
                    "source": source,
                    "fragmented_media": "drop_short_remainder",
                    "blob_len": len(remainder),
                }
            )
            self._inc_fragmented_media_stat("short_remainders")
            return None
        return remainder, source, meta

    def _start_fragmented_media(
        self,
        decoded: dict,
        *,
        blob: bytes,
        source: str,
        meta: dict,
        fragment_key: tuple[object, ...],
    ) -> None:
        self._inc_fragmented_media_stat("started")
        state = start_fragmented_media(
            decoded,
            source=source,
            meta=meta,
            message_index=self.message_index,
        )
        self.fragmented_media_states[fragment_key] = state
        self.emit(
            {
                "msg_index": self.message_index,
                "source": source,
                "blob_len": len(blob),
                "fragmented_media": "start",
                "fragment_key": fragment_key,
                "expected_body_len": state["expected_body_len"],
                "have_body_len": len(state["body"]),
                "packet_type": hex(state["packet_type"]),
                "raw_size": state["raw_size"],
                "frame_tag": hex(state["frame_tag"]),
                "frame_len": state["frame_len"],
                "meta": meta,
            }
        )

    def _analyze_fragment_partial(
        self, blob: bytes, *, source: str, meta: dict
    ) -> dict | None:
        if source != "wrapped_fragment_partial":
            return None
        return self.fragment_partial_collector.analyze(
            blob,
            source=source,
            meta=meta,
            message_index=self.message_index,
        )

    def _record_fragmented_media_decoded(
        self, decoded: dict, *, blob_len: int, source: str, meta: dict
    ) -> None:
        if decoded["plausible"]:
            self.decoded_messages.append(decoded)
        summary = build_quii_packet_summary(
            decoded,
            message_index=self.message_index,
            source=source,
            blob_len=blob_len,
            meta=meta,
            fragmented_media=decoded.get("fragmented_media", {}),
        )
        if attach_media_frame_summary(summary, decoded):
            self.media_messages.append(decoded)
        self._emit_packet_summary(summary, source=source, decoded=decoded)

    def fragmented_media_summary(self) -> dict[str, object]:
        active = []
        for fragment_key, state in self.fragmented_media_states.items():
            expected_body_len = int(state.get("expected_body_len", 0))
            have_body_len = len(state.get("body", b""))
            active.append(
                {
                    "fragment_key": fragment_key,
                    "start_msg_index": state.get("start_msg_index"),
                    "source": state.get("source"),
                    "fragments": state.get("fragments"),
                    "expected_body_len": expected_body_len,
                    "have_body_len": have_body_len,
                    "missing_body_len": max(
                        0, expected_body_len - have_body_len
                    ),
                    "packet_type": hex(int(state.get("packet_type", 0))),
                    "frame_tag": hex(int(state.get("frame_tag", 0))),
                    "frame_len": state.get("frame_len"),
                }
            )
        return {
            **getattr(self, "fragmented_media_stats", {}),
            "active": active or None,
        }

    def _looks_like_new_media_packet(
        self, blob: bytes, *, source: str
    ) -> bool:
        try:
            decoded = decode_quii_blob(blob, self.key, crypto_mode=2)
        except Exception:
            return False
        if should_start_fragmented_media(decoded, source):
            return True
        frames = decoded.get("media_frames")
        has_frames = (
            bool(frames)
            if isinstance(frames, list)
            else decoded.get("media_frame") is not None
        )
        return bool(
            decoded.get("plausible") and decoded.get("is_media") and has_frames
        )

    def _drop_fragmented_media(
        self,
        *,
        reason: str,
        source: str,
        meta: dict,
        blob_len: int,
        fragment_key: tuple[object, ...],
    ) -> None:
        state = self.fragmented_media_states.get(fragment_key)
        if state is None:
            return
        self._inc_fragmented_media_stat("dropped")
        expected_body_len = int(state.get("expected_body_len", 0))
        have_body_len = len(state.get("body", b""))
        self.emit(
            {
                "msg_index": self.message_index,
                "source": source,
                "blob_len": blob_len,
                "fragmented_media": "drop_active",
                "reason": reason,
                "fragment_key": fragment_key,
                "start_msg_index": state.get("start_msg_index"),
                "state_source": state.get("source"),
                "fragments": state.get("fragments"),
                "expected_body_len": expected_body_len,
                "have_body_len": have_body_len,
                "missing_body_len": max(0, expected_body_len - have_body_len),
                "meta": meta,
            }
        )
        self.fragmented_media_states.pop(fragment_key, None)

    def _inc_fragmented_media_stat(self, key: str) -> None:
        stats = getattr(self, "fragmented_media_stats", None)
        if not isinstance(stats, dict):
            return
        stats[key] = int(stats.get(key, 0)) + 1
