from typing import Any

from quii_helper.media.cpacket import (
    CPACKET_MAX_FRAME_LEN,
    cpacket_frame_len,
    find_next_cpacket,
    starts_cpacket,
)
from quii_helper.media.cpacket.constants import CPACKET_HEADER_LEN
from quii_helper.media.frames.cframe_pack_state import (
    append_buffer_bytes,
    cframe_expected_total_len,
    initial_cframe_pack_stats,
)
from quii_helper.media.frames.frame_parsing import parse_quii_media_frame_at


class QuiiCFramePack:
    """
    Stateful CPacket assembler matching liblive_player.so CFramePack.

    Native keeps the current CPacket buffer across media payloads. A new
    CPacket header resets the previous state; otherwise bytes continue the
    current frame until frame_len + 0x14 bytes have arrived.
    """

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._expected_total_len: int | None = None
        self._fragment_count = 0
        self.stats: dict[str, int] = initial_cframe_pack_stats()

    def feed(self, payload: bytes) -> list[dict[str, Any]]:
        frames: list[dict[str, Any]] = []
        offset = 0
        while offset < len(payload):
            if starts_cpacket(payload, offset):
                self._reset_for_new_frame()
            elif not self._buffer:
                next_offset = find_next_cpacket(payload, offset + 1)
                if next_offset < 0:
                    self.stats["dropped_orphan_bytes"] += len(payload) - offset
                    break
                self.stats["dropped_orphan_bytes"] += next_offset - offset
                offset = next_offset
                continue
            elif offset == 0:
                self.stats["continued"] += 1
                self._fragment_count += 1

            if len(self._buffer) < CPACKET_HEADER_LEN:
                offset = self._append_header_bytes(payload, offset)
                if len(self._buffer) < CPACKET_HEADER_LEN:
                    break
                if not self._parse_current_header():
                    self._clear()
                    continue

            if self._expected_total_len is None:
                self._clear()
                continue

            offset = self._append_frame_bytes(payload, offset)
            if len(self._buffer) < self._expected_total_len:
                break

            frame = parse_quii_media_frame_at(bytes(self._buffer), 0)
            if frame is not None:
                frame["cframe_fragments"] = self._fragment_count
                frames.append(frame)
                self.stats["completed"] += 1
            self._clear()

        self.stats["trailing_partial_bytes"] = len(self._buffer)
        return frames

    def _reset_for_new_frame(self) -> None:
        if self._buffer:
            self.stats["reset_incomplete"] += 1
        self._buffer.clear()
        self._expected_total_len = None
        self._fragment_count = 1
        self.stats["started"] += 1

    def _clear(self) -> None:
        self._buffer.clear()
        self._expected_total_len = None
        self._fragment_count = 0

    def _append_header_bytes(self, payload: bytes, offset: int) -> int:
        return append_buffer_bytes(
            self._buffer,
            payload,
            offset,
            target_len=CPACKET_HEADER_LEN,
        )

    def _append_frame_bytes(self, payload: bytes, offset: int) -> int:
        if self._expected_total_len is None:
            return offset
        return append_buffer_bytes(
            self._buffer,
            payload,
            offset,
            target_len=self._expected_total_len,
        )

    def _parse_current_header(self) -> bool:
        if len(self._buffer) < CPACKET_HEADER_LEN:
            return False
        if not starts_cpacket(self._buffer, 0):
            self.stats["invalid_headers"] += 1
            return False
        frame_len = cpacket_frame_len(self._buffer, 0)
        if frame_len is None or frame_len <= 0:
            self.stats["invalid_headers"] += 1
            return False
        if frame_len > CPACKET_MAX_FRAME_LEN:
            self.stats["dropped_oversize_frames"] += 1
            return False
        self._expected_total_len = cframe_expected_total_len(frame_len)
        return True
