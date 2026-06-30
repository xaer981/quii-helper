from collections.abc import Callable
from typing import Any, Protocol, cast

from quii_helper.media.fragments.fragmented_media import (
    append_fragmented_media,
    should_start_fragmented_media,
)
from quii_helper.media.fragments.fragmented_media import (
    start_fragmented_media as start_fragmented_media_state,
)
from quii_helper.models.packets import DecodedQuiiMessage, PacketMeta
from quii_helper.preview.fragments.fragment_flow_state import (
    drop_active_fragment_summary,
    fragment_remainder_meta,
    fragment_start_summary,
    has_decoded_media_frames,
    short_fragment_remainder_summary,
)
from quii_helper.preview.fragments.fragment_flow_state import (
    record_fragmented_media_decoded as record_fragmented_media_decoded_state,
)
from quii_helper.preview.processing.packets.flow import (
    fragmented_media_summary as build_fragmented_media_summary,
)
from quii_helper.preview.processing.summaries.emitter import (
    PreviewSummaryEmitter,
)
from quii_helper.protocols.quii.blob import decode_quii_blob


class PreviewFragmentFlowOwner(Protocol):
    key: str
    message_index: int
    fragmented_media_states: dict[tuple[object, ...], dict[str, Any]]
    fragmented_media_stats: dict[str, int]
    decoded_messages: list[DecodedQuiiMessage]
    media_messages: list[DecodedQuiiMessage]
    media_message_sink: Callable[[DecodedQuiiMessage], None] | None
    store_media_messages: bool
    summary_emitter: PreviewSummaryEmitter
    emit: Any

    def should_stop_media_collection(self) -> bool: ...


class PreviewFragmentFlow:
    """Handle fragmented media packet continuation for preview captures."""

    def __init__(self, owner: PreviewFragmentFlowOwner) -> None:
        self._owner = owner

    def consume_fragment(
        self,
        blob: bytes,
        *,
        source: str,
        meta: PacketMeta,
        phase: str,
        fragment_key: tuple[object, ...],
    ) -> tuple[bytes, str, PacketMeta] | None:
        owner = self._owner
        if self.looks_like_new_media_packet(blob, source=source):
            self.drop_fragmented_media(
                reason="interleaved_media_header",
                source=source,
                meta=meta,
                blob_len=len(blob),
                fragment_key=fragment_key,
            )
            return blob, source, meta

        state = owner.fragmented_media_states.get(fragment_key)
        if state is None:
            return blob, source, meta
        decoded_fragment, remainder, fragment_summary = (
            append_fragmented_media(
                state,
                blob,
                owner.key,
                source=source,
                meta=cast(dict[Any, Any], meta),
                message_index=owner.message_index,
            )
        )
        if fragment_summary.get("taken_len", 0):
            self.inc_fragmented_media_stat("appended")
        owner.emit(fragment_summary)
        if decoded_fragment is None:
            return None

        owner.fragmented_media_states.pop(fragment_key, None)
        self.inc_fragmented_media_stat("completed")
        self.record_fragmented_media_decoded(
            cast(DecodedQuiiMessage, decoded_fragment),
            blob_len=fragment_summary["expected_body_len"] + 32,
            source="wrapped_quii_fragmented_media",
            meta=cast(
                PacketMeta,
                dict(decoded_fragment.get("fragmented_media", {})),
            ),
        )
        if phase == "live" and owner.should_stop_media_collection():
            return None
        if not remainder:
            return None

        source = "wrapped_quii_fragmented_remainder"
        meta = fragment_remainder_meta(
            meta,
            message_index=owner.message_index,
            remainder_len=len(remainder),
        )
        if len(remainder) < 32:
            owner.emit(
                short_fragment_remainder_summary(
                    message_index=owner.message_index,
                    source=source,
                    blob_len=len(remainder),
                )
            )
            self.inc_fragmented_media_stat("short_remainders")
            return None
        return remainder, source, meta

    def start_fragmented_media(
        self,
        decoded: DecodedQuiiMessage,
        *,
        blob: bytes,
        source: str,
        meta: PacketMeta,
        fragment_key: tuple[object, ...],
    ) -> None:
        owner = self._owner
        self.inc_fragmented_media_stat("started")
        state = start_fragmented_media_state(
            cast(dict[Any, Any], decoded),
            source=source,
            meta=cast(dict[Any, Any], meta),
            message_index=owner.message_index,
        )
        owner.fragmented_media_states[fragment_key] = state
        owner.emit(
            fragment_start_summary(
                message_index=owner.message_index,
                source=source,
                blob_len=len(blob),
                fragment_key=fragment_key,
                state=state,
                meta=meta,
            )
        )

    def record_fragmented_media_decoded(
        self,
        decoded: DecodedQuiiMessage,
        *,
        blob_len: int,
        source: str,
        meta: PacketMeta,
    ) -> None:
        owner = self._owner
        record_fragmented_media_decoded_state(
            decoded_messages=owner.decoded_messages,
            media_messages=owner.media_messages,
            summary_emitter=owner.summary_emitter,
            decoded=decoded,
            message_index=owner.message_index,
            blob_len=blob_len,
            source=source,
            meta=meta,
            media_message_sink=owner.media_message_sink,
            store_media_messages=owner.store_media_messages,
        )

    def fragmented_media_summary(self) -> dict[str, object]:
        owner = self._owner
        return build_fragmented_media_summary(
            owner.fragmented_media_stats,
            owner.fragmented_media_states,
        )

    def looks_like_new_media_packet(self, blob: bytes, *, source: str) -> bool:
        owner = self._owner
        try:
            decoded = cast(
                DecodedQuiiMessage,
                decode_quii_blob(blob, owner.key, crypto_mode=2),
            )
        except Exception:
            return False
        if should_start_fragmented_media(
            cast(dict[Any, Any], decoded), source
        ):
            return True
        return bool(
            decoded.get("plausible")
            and decoded.get("is_media")
            and has_decoded_media_frames(decoded)
        )

    def drop_fragmented_media(
        self,
        *,
        reason: str,
        source: str,
        meta: PacketMeta,
        blob_len: int,
        fragment_key: tuple[object, ...],
    ) -> None:
        owner = self._owner
        state = owner.fragmented_media_states.get(fragment_key)
        if state is None:
            return
        self.inc_fragmented_media_stat("dropped")
        owner.emit(
            drop_active_fragment_summary(
                message_index=owner.message_index,
                source=source,
                blob_len=blob_len,
                reason=reason,
                fragment_key=fragment_key,
                state=state,
                meta=meta,
            )
        )
        owner.fragmented_media_states.pop(fragment_key, None)

    def inc_fragmented_media_stat(self, key: str) -> None:
        stats = self._owner.fragmented_media_stats
        stats[key] = int(stats.get(key, 0)) + 1
