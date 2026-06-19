from quii_helper.media.cpacket_constants import (
    CPACKET_HEADER_LEN,
    CPACKET_START_PREFIX,
    CPACKET_START_TYPE_MAX,
    CPACKET_START_TYPE_MIN,
)

CPACKET_MAX_FRAME_LEN = 64 * 1024 * 1024


def parse_quii_media_frame(payload: bytes) -> dict | None:
    frames = iter_quii_media_frames(payload)
    return frames[0] if frames else None


def iter_quii_media_frames(payload: bytes) -> list[dict]:
    frames: list[dict] = []
    offset = 0
    while offset + CPACKET_HEADER_LEN <= len(payload):
        if payload[offset : offset + 3] != CPACKET_START_PREFIX:
            next_offset = payload.find(CPACKET_START_PREFIX, offset + 1)
            if next_offset < 0:
                break
            offset = next_offset
            continue

        frame = _parse_quii_media_frame_at(payload, offset)
        if frame is None:
            break
        frames.append(frame)
        offset = int(frame["payload_offset"]) + int(frame["total_len"])
    return frames


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
        self.stats: dict[str, int] = {
            "started": 0,
            "continued": 0,
            "completed": 0,
            "reset_incomplete": 0,
            "invalid_headers": 0,
            "dropped_orphan_bytes": 0,
            "dropped_oversize_frames": 0,
            "trailing_partial_bytes": 0,
        }

    def feed(self, payload: bytes) -> list[dict]:
        frames: list[dict] = []
        offset = 0
        while offset < len(payload):
            if _starts_cpacket(payload, offset):
                self._reset_for_new_frame()
            elif not self._buffer:
                next_offset = _find_next_cpacket(payload, offset + 1)
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

            frame = _parse_quii_media_frame_at(bytes(self._buffer), 0)
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
        take = min(
            CPACKET_HEADER_LEN - len(self._buffer),
            len(payload) - offset,
        )
        if take > 0:
            self._buffer.extend(payload[offset : offset + take])
            offset += take
        return offset

    def _append_frame_bytes(self, payload: bytes, offset: int) -> int:
        if self._expected_total_len is None:
            return offset
        take = min(
            self._expected_total_len - len(self._buffer),
            len(payload) - offset,
        )
        if take > 0:
            self._buffer.extend(payload[offset : offset + take])
            offset += take
        return offset

    def _parse_current_header(self) -> bool:
        if len(self._buffer) < CPACKET_HEADER_LEN:
            return False
        if not _starts_cpacket(self._buffer, 0):
            self.stats["invalid_headers"] += 1
            return False
        frame_len = int.from_bytes(self._buffer[4:8], "little")
        if frame_len <= 0:
            self.stats["invalid_headers"] += 1
            return False
        if frame_len > CPACKET_MAX_FRAME_LEN:
            self.stats["dropped_oversize_frames"] += 1
            return False
        self._expected_total_len = frame_len + CPACKET_HEADER_LEN
        return True


def _parse_quii_media_frame_at(payload: bytes, offset: int) -> dict | None:
    if len(payload) - offset < CPACKET_HEADER_LEN:
        return None
    if not _starts_cpacket(payload, offset):
        return None

    frame_tag = payload[offset + 3]
    frame_type = (frame_tag + 0x20) & 0xFF
    frame_len = int.from_bytes(payload[offset + 4 : offset + 8], "little")
    frame_stamp = int.from_bytes(payload[offset + 8 : offset + 12], "little")
    frame_flags = payload[offset + 12 : offset + 16]
    codec = payload[offset + 0x0E]
    fps_raw = payload[offset + 0x0F]
    total_len = frame_len + CPACKET_HEADER_LEN
    if frame_len <= 0 or offset + total_len > len(payload):
        return None

    width = int.from_bytes(payload[offset + 16 : offset + 18], "little")
    height = int.from_bytes(payload[offset + 18 : offset + 20], "little")
    bitstream = payload[offset + CPACKET_HEADER_LEN : offset + total_len]
    nal_offset = bitstream.find(b"\x00\x00\x00\x01")
    if nal_offset < 0:
        nal_offset = bitstream.find(b"\x00\x00\x01")

    return {
        "payload_offset": offset,
        "frame_tag": frame_tag,
        "frame_type": frame_type,
        "frame_len": frame_len,
        "frame_stamp": frame_stamp,
        "frame_flags": frame_flags,
        "codec": codec,
        "fps_raw": fps_raw,
        "fps": fps_raw / 4.0,
        "total_len": total_len,
        "width": width,
        "height": height,
        "bitstream": bitstream,
        "nal_offset": nal_offset,
    }


def _starts_cpacket(payload: bytes | bytearray, offset: int) -> bool:
    return (
        offset + 4 <= len(payload)
        and payload[offset : offset + 3] == CPACKET_START_PREFIX
        and CPACKET_START_TYPE_MIN
        <= payload[offset + 3]
        <= CPACKET_START_TYPE_MAX
    )


def _find_next_cpacket(payload: bytes, offset: int) -> int:
    cursor = max(0, offset)
    while cursor < len(payload):
        candidate = payload.find(CPACKET_START_PREFIX, cursor)
        if candidate < 0:
            return -1
        if _starts_cpacket(payload, candidate):
            return candidate
        cursor = candidate + 1
    return -1
