from quii_helper.media.fragments.fragmented_media import (
    append_fragmented_media,
    should_start_fragmented_media,
    start_fragmented_media,
)
from quii_helper.preview.fragments.fragment_flow_state import (
    drop_active_fragment_summary,
    fragment_remainder_meta,
    fragment_start_summary,
    has_decoded_media_frames,
    record_fragmented_media_decoded,
    short_fragment_remainder_summary,
)
from quii_helper.preview.processing.packets.flow import (
    fragmented_media_summary,
)
from quii_helper.protocols.quii.blob import decode_quii_blob


class PreviewFragmentFlowMixin:
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
        meta = fragment_remainder_meta(
            meta,
            message_index=self.message_index,
            remainder_len=len(remainder),
        )
        if len(remainder) < 32:
            self.emit(
                short_fragment_remainder_summary(
                    message_index=self.message_index,
                    source=source,
                    blob_len=len(remainder),
                )
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
            fragment_start_summary(
                message_index=self.message_index,
                source=source,
                blob_len=len(blob),
                fragment_key=fragment_key,
                state=state,
                meta=meta,
            )
        )

    def _record_fragmented_media_decoded(
        self, decoded: dict, *, blob_len: int, source: str, meta: dict
    ) -> None:
        record_fragmented_media_decoded(
            decoded_messages=self.decoded_messages,
            media_messages=self.media_messages,
            summary_emitter=self.summary_emitter,
            decoded=decoded,
            message_index=self.message_index,
            blob_len=blob_len,
            source=source,
            meta=meta,
        )

    def fragmented_media_summary(self) -> dict[str, object]:
        return fragmented_media_summary(
            getattr(self, "fragmented_media_stats", None),
            self.fragmented_media_states,
        )

    def _looks_like_new_media_packet(
        self, blob: bytes, *, source: str
    ) -> bool:
        try:
            decoded = decode_quii_blob(blob, self.key, crypto_mode=2)
        except Exception:
            return False
        if should_start_fragmented_media(decoded, source):
            return True
        return bool(
            decoded.get("plausible")
            and decoded.get("is_media")
            and has_decoded_media_frames(decoded)
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
        self.emit(
            drop_active_fragment_summary(
                message_index=self.message_index,
                source=source,
                blob_len=blob_len,
                reason=reason,
                fragment_key=fragment_key,
                state=state,
                meta=meta,
            )
        )
        self.fragmented_media_states.pop(fragment_key, None)

    def _inc_fragmented_media_stat(self, key: str) -> None:
        stats = getattr(self, "fragmented_media_stats", None)
        if not isinstance(stats, dict):
            return
        stats[key] = int(stats.get(key, 0)) + 1
