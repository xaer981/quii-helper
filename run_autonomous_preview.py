import queue
import hashlib
import json
import struct
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from autonomous_client import AutonomousConfig, fetch_runtime_credentials, open_direct_preview
from autonomous_protocol import aes_cbc_crypt
from main import QuiiHeader, parse_quii_media_frame, write_h264_stream


MEDIA_PACKET_TYPES = {0xA0, 0xA1, 0xA2, 0xA3}
VALID_PACKET_TYPES = {0x00, 0x01, 0x0B, 0xFE} | MEDIA_PACKET_TYPES
DIRECT_BLOB_SAMPLE_LIMIT = 16
DIRECT_BLOB_SUMMARY_LIMIT = 16
WRAPPED_TAIL_SAMPLE_LIMIT = 16
FRAGMENT_PARTIAL_SAMPLE_LIMIT = 16
SAVE_DIAGNOSTIC_ARTIFACTS = False
OUTPUT_TIMESTAMP_FORMAT = "%d-%m-%Y_%H-%M-%S"
PREVIEW_CAPTURE_SECONDS = 35.0
MIN_MEDIA_MESSAGES = 12
MAX_MEDIA_MESSAGES = 160
CPACKET_HEADER_LEN = 0x14
CPACKET_START_PREFIX = b"\x00\x00\x01"
CPACKET_START_TYPE_MIN = 0xE0
CPACKET_START_TYPE_MAX = 0xEA
FRAGMENTED_MEDIA_MAX_BODY_LEN = 2 * 1024 * 1024


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="backslashreplace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(errors="backslashreplace")


def _emit(obj: object) -> None:
    if isinstance(obj, (dict, list)):
        print(json.dumps(obj, ensure_ascii=True))
    else:
        print(obj)


def _emit_packet_summary(
    summary: dict,
    *,
    source: str,
    decoded: dict,
    state: dict[str, int],
) -> None:
    if source == "direct_quii_blob" and not decoded.get("plausible"):
        state["implausible_direct_seen"] = state.get("implausible_direct_seen", 0) + 1
        if state["implausible_direct_seen"] > DIRECT_BLOB_SUMMARY_LIMIT:
            state["implausible_direct_suppressed"] = state.get("implausible_direct_suppressed", 0) + 1
            return
    _emit(summary)


def _safe_text_preview(payload: bytes) -> str:
    text = payload.decode("utf-8", errors="ignore").replace("\x00", " ").strip()
    if not text:
        return ""
    return text[:80]


def _media_message_nal_analysis(decoded: dict) -> dict:
    frame = decoded.get("media_frame")
    if not isinstance(frame, dict):
        return {}
    bitstream = frame.get("bitstream", b"")
    nal_offset = int(frame.get("nal_offset", -1))
    if not isinstance(bitstream, bytes) or nal_offset < 0:
        return {}
    return _analyze_annexb_h264(bitstream[nal_offset:])


def _media_collection_summary(media_messages: list[dict]) -> dict:
    counts: dict[str, int] = {}
    has_sps = False
    has_pps = False
    has_idr = False
    has_vcl = False
    keyframes = 0
    nal_samples: list[dict] = []
    for decoded in media_messages:
        frame = decoded.get("media_frame")
        if not isinstance(frame, dict):
            continue
        if int(frame.get("frame_tag", -1)) == 0xE1:
            keyframes += 1
        nal = _media_message_nal_analysis(decoded)
        for name, count in dict(nal.get("counts", {})).items():
            counts[name] = counts.get(name, 0) + int(count)
        has_sps = has_sps or bool(nal.get("has_sps"))
        has_pps = has_pps or bool(nal.get("has_pps"))
        has_idr = has_idr or bool(nal.get("has_idr"))
        has_vcl = has_vcl or bool(nal.get("has_vcl"))
        if nal and len(nal_samples) < 6:
            nal_samples.append(
                {
                    "frame_tag": hex(int(frame.get("frame_tag", 0))),
                    "frame_len": int(frame.get("frame_len", 0)),
                    "nal": {
                        "counts": nal.get("counts", {}),
                        "has_sps": nal.get("has_sps"),
                        "has_pps": nal.get("has_pps"),
                        "has_idr": nal.get("has_idr"),
                        "nal_units": nal.get("nal_units", [])[:3],
                    },
                }
            )
    return {
        "media_messages": len(media_messages),
        "keyframes": keyframes,
        "has_sps": has_sps,
        "has_pps": has_pps,
        "has_idr": has_idr,
        "has_vcl": has_vcl,
        "counts": counts,
        "nal_samples": nal_samples,
        "decodable_h264_context": bool(has_sps and has_pps and has_vcl),
    }


def _should_stop_media_collection(media_messages: list[dict]) -> bool:
    if len(media_messages) >= MAX_MEDIA_MESSAGES:
        return True
    if len(media_messages) < MIN_MEDIA_MESSAGES:
        return False
    return bool(_media_collection_summary(media_messages).get("decodable_h264_context"))


def _is_plausible_quii_header(packet_type: int, payload_size: int, raw_size: int, body_available: int) -> bool:
    if packet_type not in VALID_PACKET_TYPES:
        return False
    if payload_size < 0 or raw_size < 0:
        return False
    if payload_size > body_available:
        return False
    if raw_size > max(payload_size, body_available):
        return False
    return True


def decode_quii_blob(blob: bytes, key: str, *, crypto_mode: int = 2, offset: int = 0) -> dict:
    if len(blob) - offset < 32:
        raise ValueError(f"blob too short for QUII packet: {len(blob)} offset={offset}")

    header_raw = blob[offset : offset + 32]
    header = aes_cbc_crypt(header_raw, key, crypto_mode=crypto_mode, decrypt=True)

    packet_type = header[0]
    command_payload_size = int.from_bytes(header[9:11], "little")
    raw_size = int.from_bytes(header[11:13], "little")
    media_payload_size = int.from_bytes(header[11:15], "little")
    is_media = packet_type in MEDIA_PACKET_TYPES
    read_size = media_payload_size if is_media else command_payload_size
    encrypted_body = blob[offset + 32 : offset + 32 + read_size]
    body_available = max(0, len(blob) - offset - 32)
    plausible = _is_plausible_quii_header(packet_type, command_payload_size, raw_size, body_available)

    if is_media:
        command_part_len = min(command_payload_size, len(encrypted_body))
        command_part = encrypted_body[:command_part_len]
        media_part = encrypted_body[command_part_len:]
        if command_part:
            command_part = aes_cbc_crypt(command_part, key, crypto_mode=crypto_mode, decrypt=True)
        if media_part and header[15] != 0:
            media_part = aes_cbc_crypt(media_part, key, crypto_mode=crypto_mode, decrypt=True)
        payload = command_part + media_part
    else:
        payload = aes_cbc_crypt(encrypted_body, key, crypto_mode=crypto_mode, decrypt=True) if encrypted_body else b""

    header_obj = QuiiHeader(
        packet_type=packet_type,
        payload_size=command_payload_size,
        raw_size=raw_size,
        flag13=header[13],
        flag14=header[14],
        flag15=header[15],
        flag16=header[16],
        flag17=header[17],
        raw=header,
    )
    media_frame = parse_quii_media_frame(payload) if is_media else None
    return {
        "header": header_obj,
        "header_raw": header_raw,
        "payload": payload,
        "payload_raw": encrypted_body,
        "is_media": is_media,
        "media_frame": media_frame,
        "text_preview": _safe_text_preview(payload[:raw_size] if raw_size else payload),
        "plausible": plausible,
        "offset": offset,
        "body_available": body_available,
        "media_payload_size": media_payload_size,
        "read_size": read_size,
    }


def _cframe_total_len(payload: bytes) -> int:
    if len(payload) < CPACKET_HEADER_LEN:
        return 0
    if payload[:3] != CPACKET_START_PREFIX:
        return 0
    if not (CPACKET_START_TYPE_MIN <= payload[3] <= CPACKET_START_TYPE_MAX):
        return 0
    frame_len = int.from_bytes(payload[4:8], "little")
    total_len = frame_len + CPACKET_HEADER_LEN
    if frame_len <= 0 or total_len > FRAGMENTED_MEDIA_MAX_BODY_LEN:
        return 0
    return total_len


def _should_start_fragmented_media(decoded: dict, source: str) -> bool:
    if source != "wrapped_quii":
        return False
    if not decoded.get("is_media"):
        return False
    expected_body_len = int(decoded.get("read_size", 0))
    body = decoded.get("payload_raw", b"")
    payload = decoded.get("payload", b"")
    if expected_body_len <= len(body) or expected_body_len > FRAGMENTED_MEDIA_MAX_BODY_LEN:
        return False
    return _cframe_total_len(payload) == expected_body_len


def _start_fragmented_media(decoded: dict, *, source: str, meta: dict, message_index: int) -> dict:
    header = decoded["header"]
    payload = decoded["payload"]
    expected_body_len = int(decoded["read_size"])
    return {
        "header_raw": decoded["header_raw"],
        "body": bytearray(decoded["payload_raw"]),
        "expected_body_len": expected_body_len,
        "start_msg_index": message_index,
        "source": source,
        "meta": meta,
        "packet_type": header.packet_type,
        "payload_size": header.payload_size,
        "raw_size": header.raw_size,
        "flag15": header.flag15,
        "frame_tag": payload[3],
        "frame_len": int.from_bytes(payload[4:8], "little"),
        "fragments": 1,
    }


def _append_fragmented_media(
    state: dict,
    blob: bytes,
    key: str,
    *,
    source: str,
    meta: dict,
    message_index: int,
) -> tuple[dict | None, bytes, dict]:
    body = state["body"]
    expected_body_len = int(state["expected_body_len"])
    remaining = max(0, expected_body_len - len(body))
    take = min(remaining, len(blob))
    if take:
        body.extend(blob[:take])
        state["fragments"] = int(state.get("fragments", 0)) + 1
    complete = len(body) >= expected_body_len
    summary = {
        "msg_index": message_index,
        "source": source,
        "blob_len": len(blob),
        "fragmented_media": "complete" if complete else "append",
        "start_msg_index": state.get("start_msg_index"),
        "fragments": state.get("fragments"),
        "expected_body_len": expected_body_len,
        "have_body_len": len(body),
        "taken_len": take,
        "remainder_len": max(0, len(blob) - take),
        "packet_type": hex(int(state.get("packet_type", 0))),
        "raw_size": state.get("raw_size"),
        "frame_tag": hex(int(state.get("frame_tag", 0))),
        "frame_len": state.get("frame_len"),
    }
    if meta:
        summary["meta"] = meta
    if not complete:
        return None, b"", summary

    full_blob = bytes(state["header_raw"]) + bytes(body[:expected_body_len])
    decoded = decode_quii_blob(full_blob, key, crypto_mode=2)
    decoded["fragmented_media"] = {
        "start_msg_index": state.get("start_msg_index"),
        "end_msg_index": message_index,
        "fragments": state.get("fragments"),
        "expected_body_len": expected_body_len,
    }
    return decoded, blob[take:], summary


def _record_fragmented_media_decoded(
    decoded: dict,
    *,
    message_index: int,
    blob_len: int,
    source: str,
    meta: dict,
    decoded_messages: list[dict],
    media_messages: list[dict],
    summary_emit_state: dict[str, int],
) -> None:
    if decoded["plausible"]:
        decoded_messages.append(decoded)
    header = decoded["header"]
    summary = {
        "msg_index": message_index,
        "source": source,
        "blob_len": blob_len,
        "packet_type": hex(header.packet_type),
        "payload_size": header.payload_size,
        "raw_size": header.raw_size,
        "flag15": header.flag15,
        "flag16": header.flag16,
        "flag17": header.flag17,
        "is_media": decoded["is_media"],
        "plausible": decoded["plausible"],
        "offset": decoded["offset"],
        "payload_prefix": decoded["payload"][:32].hex(),
        "fragmented_media": decoded.get("fragmented_media", {}),
    }
    if meta:
        summary["meta"] = meta
    if decoded["text_preview"]:
        summary["text_preview"] = decoded["text_preview"]
    if decoded["media_frame"] is not None:
        frame = decoded["media_frame"]
        summary["frame_tag"] = hex(frame["frame_tag"])
        summary["frame_len"] = frame["frame_len"]
        summary["frame_stamp"] = frame["frame_stamp"]
        summary["width"] = frame["width"]
        summary["height"] = frame["height"]
        media_messages.append(decoded)
    _emit_packet_summary(
        summary,
        source=source,
        decoded=decoded,
        state=summary_emit_state,
    )


def find_quii_decode_candidates(blob: bytes, key: str, *, crypto_mode: int = 2, max_offsets: int = 32) -> list[dict]:
    candidates: list[dict] = []
    limit = min(max_offsets, max(0, len(blob) - 32) + 1)
    for offset in range(limit):
        try:
            decoded = decode_quii_blob(blob, key, crypto_mode=crypto_mode, offset=offset)
        except Exception:
            continue
        if not decoded["plausible"]:
            continue
        header = decoded["header"]
        candidates.append(
            {
                "offset": offset,
                "packet_type": hex(header.packet_type),
                "payload_size": header.payload_size,
                "raw_size": header.raw_size,
                "flag15": header.flag15,
                "flag16": header.flag16,
                "flag17": header.flag17,
                "is_media": decoded["is_media"],
                "payload_prefix": decoded["payload"][:24].hex(),
                "text_preview": decoded["text_preview"],
            }
        )
    return candidates


def _append_jsonl(path: Path, payload: dict) -> None:
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload, ensure_ascii=True) + "\n")


def _timestamped_output_base(directory: Path | None = None) -> Path:
    directory = directory or Path.cwd()
    stem = datetime.now().strftime(OUTPUT_TIMESTAMP_FORMAT)
    candidate = directory / stem
    suffixes = (".mp4", ".jpg", ".h264")
    if not any(candidate.with_suffix(suffix).exists() for suffix in suffixes):
        return candidate.resolve()
    for index in range(2, 1000):
        candidate = directory / f"{stem}_{index}"
        if not any(candidate.with_suffix(suffix).exists() for suffix in suffixes):
            return candidate.resolve()
    raise RuntimeError(f"could not allocate unique timestamped output name for {stem}")


def analyze_wrapped_quii_tail(blob: bytes, key: str, decoded: dict) -> dict | None:
    header = decoded["header"]
    consumed = 32 + header.payload_size
    if len(blob) <= consumed:
        return None

    tail = blob[consumed:]
    tail_trimmed = tail.rstrip(b"\xBB")
    decryptable_len = len(tail_trimmed) - (len(tail_trimmed) % 16)
    decrypted = b""
    decrypted_text_preview = ""
    h264_start_codes = 0
    annexb_start_codes = 0

    if decryptable_len >= 16:
        try:
            decrypted = aes_cbc_crypt(
                tail_trimmed[:decryptable_len],
                key,
                crypto_mode=2,
                decrypt=True,
            )
        except Exception:
            decrypted = b""

    if decrypted:
        decrypted_text_preview = _safe_text_preview(decrypted[:160])
        h264_start_codes = decrypted.count(b"\x00\x00\x00\x01")
        annexb_start_codes = decrypted.count(b"\x00\x00\x01")
        cpacket_analysis = _analyze_cpacket_stream(decrypted)
        start_code_offsets4 = []
        start_code_offsets3 = []
        cursor = 0
        while len(start_code_offsets4) < 8:
            idx = decrypted.find(b"\x00\x00\x00\x01", cursor)
            if idx < 0:
                break
            start_code_offsets4.append(idx)
            cursor = idx + 4
        cursor = 0
        while len(start_code_offsets3) < 8:
            idx = decrypted.find(b"\x00\x00\x01", cursor)
            if idx < 0:
                break
            if idx == 0 or decrypted[idx - 1] != 0x00:
                start_code_offsets3.append(idx)
            cursor = idx + 3
        if start_code_offsets4:
            first_h264_offset = start_code_offsets4[0]
            pre_start = max(0, first_h264_offset - 16)
            pre_marker = decrypted[pre_start:first_h264_offset]
            post_marker = decrypted[first_h264_offset:first_h264_offset + 32]
            pre_marker_dwords_le = [
                int.from_bytes(pre_marker[i:i + 4], "little")
                for i in range(0, len(pre_marker) - (len(pre_marker) % 4), 4)
            ]
            pre_marker_dwords_be = [
                int.from_bytes(pre_marker[i:i + 4], "big")
                for i in range(0, len(pre_marker) - (len(pre_marker) % 4), 4)
            ]
            pre_marker_tail_hex = pre_marker[-4:].hex() if pre_marker else ""
            container_probe = {
                "first_marker_offset": first_h264_offset,
                "pre_marker_hex": pre_marker.hex(),
                "pre_marker_tail_hex": pre_marker_tail_hex,
                "pre_marker_dwords_le": pre_marker_dwords_le,
                "pre_marker_dwords_be": pre_marker_dwords_be,
                "post_marker_prefix_hex": post_marker.hex(),
                "looks_like_false_h264_container": pre_marker_tail_hex == "c0034002",
            }
        else:
            first_h264_offset = -1
            pre_marker = b""
            post_marker = b""
            pre_marker_dwords_le = []
            pre_marker_dwords_be = []
            pre_marker_tail_hex = ""
            container_probe = {}
    else:
        cpacket_analysis = {}
        start_code_offsets4 = []
        start_code_offsets3 = []
        first_h264_offset = -1
        pre_marker = b""
        post_marker = b""
        pre_marker_dwords_le = []
        pre_marker_dwords_be = []
        pre_marker_tail_hex = ""
        container_probe = {}

    return {
        "packet_type": hex(header.packet_type),
        "payload_size": header.payload_size,
        "raw_size": header.raw_size,
        "blob_len": len(blob),
        "consumed": consumed,
        "tail_len": len(tail),
        "tail_trimmed_len": len(tail_trimmed),
        "tail_bb_suffix_len": len(tail) - len(tail_trimmed),
        "decryptable_len": decryptable_len,
        "tail_prefix": tail[:64].hex(),
        "tail_trimmed_prefix": tail_trimmed[:64].hex(),
        "tail_trimmed_suffix": tail_trimmed[-64:].hex() if tail_trimmed else "",
        "decrypted_prefix": decrypted[:128].hex(),
        "decrypted_text_preview": decrypted_text_preview,
        "h264_start_codes": h264_start_codes,
        "annexb_start_codes": annexb_start_codes,
        "h264_start_offsets": start_code_offsets4,
        "annexb_start_offsets": start_code_offsets3,
        "first_h264_offset": first_h264_offset,
        "pre_h264_prefix_hex": pre_marker.hex(),
        "pre_h264_dwords_le": pre_marker_dwords_le,
        "pre_h264_dwords_be": pre_marker_dwords_be,
        "pre_h264_tail_hex": pre_marker_tail_hex,
        "post_h264_prefix_hex": post_marker.hex(),
        "container_probe": container_probe,
        "cpacket_analysis": cpacket_analysis,
    }


def decrypt_wrapped_quii_tail_bytes(blob: bytes, key: str, decoded: dict) -> bytes:
    header = decoded["header"]
    consumed = 32 + header.payload_size
    if len(blob) <= consumed:
        return b""
    tail = blob[consumed:]
    tail_trimmed = tail.rstrip(b"\xBB")
    decryptable_len = len(tail_trimmed) - (len(tail_trimmed) % 16)
    if decryptable_len < 16:
        return b""
    try:
        return aes_cbc_crypt(
            tail_trimmed[:decryptable_len],
            key,
            crypto_mode=2,
            decrypt=True,
        )
    except Exception:
        return b""


def analyze_partial_wrapped_inner(blob: bytes, key: str) -> dict:
    analysis: dict[str, object] = {
        "blob_len": len(blob),
        "blob_prefix": blob[:96].hex(),
    }
    if len(blob) < 0x38 or blob[:4] != b"\xff\xff\xff\xff":
        return analysis

    packet_length = int.from_bytes(blob[0x04:0x08], "little")
    packet_type_flag = int.from_bytes(blob[0x12:0x14], "little")
    command = int.from_bytes(blob[0x14:0x18], "little")
    seq = int.from_bytes(blob[0x18:0x1C], "little")
    payload_length = int.from_bytes(blob[0x24:0x28], "little")
    dest_id = int.from_bytes(blob[0x28:0x2C], "little")
    src_id = int.from_bytes(blob[0x2C:0x30], "little")
    body_length = int.from_bytes(blob[0x30:0x34], "little")
    payload = blob[0x38:]

    analysis.update(
        {
            "packet_length": packet_length,
            "packet_type_flag": packet_type_flag,
            "command": hex(command),
            "seq": seq,
            "payload_length": payload_length,
            "body_length": body_length,
            "dest_id": hex(dest_id),
            "src_id": hex(src_id),
            "partial_payload_len": len(payload),
            "payload_prefix": payload[:96].hex(),
        }
    )

    try:
        decoded = decode_quii_blob(payload, key, crypto_mode=2)
    except Exception as exc:
        analysis["decode_error"] = repr(exc)
        return analysis

    header = decoded["header"]
    analysis["payload_decode"] = {
        "plausible": decoded["plausible"],
        "packet_type": hex(header.packet_type),
        "payload_size": header.payload_size,
        "raw_size": header.raw_size,
        "text_preview": decoded["text_preview"],
        "payload_prefix": decoded["payload"][:64].hex(),
    }
    embedded_probe = _analyze_payload_embedded_probe(decoded["payload"])
    if embedded_probe is not None:
        analysis["payload_embedded_probe"] = embedded_probe
    if not decoded["plausible"]:
        candidates = find_quii_decode_candidates(payload, key, crypto_mode=2)
        if candidates:
            analysis["payload_decode_candidates"] = candidates[:8]
    if decoded["plausible"]:
        tail_analysis = analyze_wrapped_quii_tail(payload, key, decoded)
        if tail_analysis is not None:
            analysis["wrapped_tail_analysis"] = tail_analysis
    return analysis


def _dump_partial_tail_artifacts(
    *,
    blob: bytes,
    key: str,
    decoded: dict,
    dump_dir: Path,
    stem: str,
) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    decrypted_tail = decrypt_wrapped_quii_tail_bytes(blob, key, decoded)
    if not decrypted_tail:
        return artifacts

    dump_dir.mkdir(exist_ok=True)
    tail_path = dump_dir / f"{stem}_tail_decrypted.bin"
    tail_path.write_bytes(decrypted_tail)
    artifacts["decrypted_tail_path"] = str(tail_path)

    cpacket_blob = _candidate_cpacket_from_decrypted_tail(decrypted_tail)
    if cpacket_blob:
        cpacket_path = dump_dir / f"{stem}_tail_from_cpacket.bin"
        cpacket_path.write_bytes(cpacket_blob)
        artifacts["cpacket_probe_path"] = str(cpacket_path)

    start4 = decrypted_tail.find(b"\x00\x00\x00\x01")
    if start4 >= 0:
        false_container_probe = start4 >= 4 and decrypted_tail[start4 - 4:start4] == bytes.fromhex("c0034002")
        if false_container_probe:
            container_start = start4 - 4
            container_path = dump_dir / f"{stem}_tail_from_container_probe.bin"
            container_path.write_bytes(decrypted_tail[container_start:])
            artifacts["container_probe_path"] = str(container_path)
            artifacts["container_probe_offset"] = str(container_start)
        else:
            h264_path = dump_dir / f"{stem}_tail_from_startcode.h264"
            h264_path.write_bytes(decrypted_tail[start4:])
            artifacts["h264_from_startcode_path"] = str(h264_path)
            artifacts["h264_from_startcode_offset"] = str(start4)
    return artifacts


def _candidate_embedded_h264(blob: bytes, key: str, decoded: dict) -> bytes:
    decrypted_tail = decrypt_wrapped_quii_tail_bytes(blob, key, decoded)
    if not decrypted_tail:
        return b""
    start4 = decrypted_tail.find(b"\x00\x00\x00\x01")
    if start4 < 0:
        return b""
    if start4 >= 4 and decrypted_tail[start4 - 4:start4] == bytes.fromhex("c0034002"):
        return b""
    candidate = decrypted_tail[start4:]
    analysis = _analyze_annexb_h264(candidate)
    if analysis.get("false_positive_sps_only"):
        return b""
    return candidate


def _candidate_container_probe(blob: bytes, key: str, decoded: dict) -> bytes:
    decrypted_tail = decrypt_wrapped_quii_tail_bytes(blob, key, decoded)
    if not decrypted_tail:
        return b""
    start4 = decrypted_tail.find(b"\x00\x00\x00\x01")
    if start4 < 4:
        return b""
    if decrypted_tail[start4 - 4:start4] != bytes.fromhex("c0034002"):
        return b""
    return decrypted_tail[start4 - 4:]


def _candidate_cpacket_stream(blob: bytes, key: str, decoded: dict) -> bytes:
    decrypted_tail = decrypt_wrapped_quii_tail_bytes(blob, key, decoded)
    if not decrypted_tail:
        return b""
    return _candidate_cpacket_from_decrypted_tail(decrypted_tail)


def _candidate_cpacket_from_decrypted_tail(decrypted_tail: bytes) -> bytes:
    for offset in _find_cpacket_offsets(decrypted_tail, limit=16):
        parsed = _parse_cpacket_header(decrypted_tail, offset)
        if parsed.get("plausible"):
            return decrypted_tail[offset:]
    return b""


def _candidate_container_probe_from_partial_payload(blob: bytes, key: str) -> bytes:
    try:
        decoded = decode_quii_blob(blob, key, crypto_mode=2)
    except Exception:
        return b""
    candidate = _candidate_container_probe(blob, key, decoded)
    if candidate:
        return candidate
    payload = decoded.get("payload", b"")
    if not payload:
        return b""
    marker = bytes.fromhex("c0034002")
    idx = payload.find(marker)
    if idx < 0:
        return b""
    return payload[idx:]


def _analyze_payload_embedded_probe(payload: bytes) -> dict | None:
    marker = bytes.fromhex("c0034002")
    idx = payload.find(marker)
    if idx < 0:
        return None

    leading = payload[:idx]
    start4 = leading.find(b"\x00\x00\x00\x01")
    start3 = leading.find(b"\x00\x00\x01")
    leading_annexb = {}
    if start4 >= 0:
        leading_annexb = _analyze_annexb_h264(leading[start4:])
    elif start3 >= 0:
        leading_annexb = _analyze_annexb_h264(leading[start3 - 1:] if start3 > 0 and leading[start3 - 1] == 0 else leading[start3:])

    return {
        "marker_offset": idx,
        "payload_len": len(payload),
        "payload_prefix_hex": payload[:64].hex(),
        "leading_len": len(leading),
        "leading_prefix_hex": leading[:64].hex(),
        "leading_suffix_hex": leading[-64:].hex() if leading else "",
        "leading_start_code4_at": start4,
        "leading_start_code3_at": start3,
        "leading_annexb": leading_annexb,
        "leading_cpacket": _analyze_cpacket_stream(leading),
        "payload_cpacket": _analyze_cpacket_stream(payload),
        "probe_prefix_hex": payload[idx:idx + 64].hex(),
    }


def _analyze_annexb_h264(stream: bytes) -> dict:
    def find_start_codes(buf: bytes) -> list[tuple[int, int]]:
        starts: list[tuple[int, int]] = []
        i = 0
        end = len(buf) - 3
        while i < end:
            if buf[i:i + 4] == b"\x00\x00\x00\x01":
                starts.append((i, 4))
                i += 4
                continue
            if buf[i:i + 3] == b"\x00\x00\x01":
                starts.append((i, 3))
                i += 3
                continue
            i += 1
        return starts

    nal_type_names = {
        1: "non_idr_slice",
        5: "idr_slice",
        6: "sei",
        7: "sps",
        8: "pps",
        9: "aud",
    }
    starts = find_start_codes(stream)
    nal_units: list[dict] = []
    counts: dict[str, int] = {}
    epb_count = sum(
        1
        for i in range(2, len(stream))
        if stream[i] == 0x03 and stream[i - 1] == 0x00 and stream[i - 2] == 0x00
    )
    largest_payload_len = 0
    for idx, (start, sc_len) in enumerate(starts):
        payload_start = start + sc_len
        payload_end = starts[idx + 1][0] if idx + 1 < len(starts) else len(stream)
        if payload_start >= payload_end:
            continue
        nal_header = stream[payload_start]
        nal_type = nal_header & 0x1F
        name = nal_type_names.get(nal_type, f"type_{nal_type}")
        counts[name] = counts.get(name, 0) + 1
        payload_len = payload_end - payload_start
        largest_payload_len = max(largest_payload_len, payload_len)
        if len(nal_units) < 16:
            nal_units.append(
                {
                    "offset": start,
                    "start_code_len": sc_len,
                    "nal_type": nal_type,
                    "nal_name": name,
                    "payload_len": payload_len,
                    "header_byte": hex(nal_header),
                }
            )

    has_vcl = bool(counts.get("idr_slice") or counts.get("non_idr_slice"))
    has_pps = bool(counts.get("pps"))
    has_sei = bool(counts.get("sei"))
    has_sps = bool(counts.get("sps"))
    false_positive_sps_only = (
        has_sps
        and not has_pps
        and not has_sei
        and not has_vcl
        and set(counts.keys()) <= {"sps"}
        and len(starts) <= 2
        and epb_count == 0
        and largest_payload_len >= 512
    )

    return {
        "stream_len": len(stream),
        "start_code_count": len(starts),
        "nal_count": sum(counts.values()),
        "counts": counts,
        "has_vcl": has_vcl,
        "has_idr": bool(counts.get("idr_slice")),
        "has_sps": has_sps,
        "has_pps": has_pps,
        "has_sei": has_sei,
        "epb_count": epb_count,
        "largest_payload_len": largest_payload_len,
        "false_positive_sps_only": false_positive_sps_only,
        "nal_units": nal_units,
    }


def _find_cpacket_offsets(blob: bytes, *, limit: int = 32) -> list[int]:
    offsets: list[int] = []
    cursor = 0
    while len(offsets) < limit:
        idx = blob.find(CPACKET_START_PREFIX, cursor)
        if idx < 0 or idx + 3 >= len(blob):
            break
        marker_type = blob[idx + 3]
        if CPACKET_START_TYPE_MIN <= marker_type <= CPACKET_START_TYPE_MAX:
            offsets.append(idx)
        cursor = idx + 3
    return offsets


def _cpacket_codec_name(codec: int) -> str:
    if codec == 1 or 0x10 <= codec <= 0x1F:
        return "h264"
    if codec == 2 or 0x20 <= codec <= 0x2F:
        return "h265"
    return f"codec_{codec}"


def _parse_cpacket_header(blob: bytes, offset: int = 0) -> dict:
    available = max(0, len(blob) - offset)
    result: dict[str, object] = {
        "offset": offset,
        "available": available,
        "complete_header": available >= CPACKET_HEADER_LEN,
        "plausible": False,
    }
    if available < 4:
        return result

    prefix = blob[offset:offset + 3]
    marker_type = blob[offset + 3]
    frame_type = (marker_type + 0x20) & 0xFF
    result.update(
        {
            "prefix_hex": blob[offset:offset + min(64, available)].hex(),
            "marker_type": hex(marker_type),
            "frame_type": frame_type,
            "starts_with_cpacket_magic": (
                prefix == CPACKET_START_PREFIX
                and CPACKET_START_TYPE_MIN <= marker_type <= CPACKET_START_TYPE_MAX
            ),
        }
    )
    if not result["starts_with_cpacket_magic"] or available < CPACKET_HEADER_LEN:
        return result

    payload_len = int.from_bytes(blob[offset + 4:offset + 8], "little")
    total_len = payload_len + CPACKET_HEADER_LEN
    codec = blob[offset + 0x0E]
    fps_raw = blob[offset + 0x0F]
    width = int.from_bytes(blob[offset + 0x10:offset + 0x12], "little")
    height = int.from_bytes(blob[offset + 0x12:offset + 0x14], "little")
    is_video_type = frame_type in {0, 1, 9, 10}
    is_h264 = codec == 1 or 0x10 <= codec <= 0x1F
    is_h265 = codec == 2 or 0x20 <= codec <= 0x2F
    is_video = is_video_type and (is_h264 or is_h265)
    plausible = 0 <= payload_len <= 64 * 1024 * 1024
    payload_available = max(0, min(payload_len, available - CPACKET_HEADER_LEN))
    payload = blob[offset + CPACKET_HEADER_LEN:offset + CPACKET_HEADER_LEN + payload_available]
    media_analysis: dict[str, object] = {}
    if is_h264 and payload:
        start4 = payload.find(b"\x00\x00\x00\x01")
        start3 = payload.find(b"\x00\x00\x01")
        if start4 >= 0:
            media_analysis = _analyze_annexb_h264(payload[start4:])
        elif start3 >= 0:
            media_analysis = _analyze_annexb_h264(
                payload[start3 - 1:] if start3 > 0 and payload[start3 - 1] == 0 else payload[start3:]
            )

    result.update(
        {
            "payload_len": payload_len,
            "total_len": total_len,
            "complete_frame": available >= total_len,
            "missing_bytes": max(0, total_len - available),
            "payload_available": payload_available,
            "codec": codec,
            "codec_name": _cpacket_codec_name(codec),
            "fps": fps_raw / 4.0,
            "width": width,
            "height": height,
            "is_video_type": is_video_type,
            "is_h264": is_h264,
            "is_h265": is_h265,
            "is_video": is_video,
            "is_key_type": frame_type in {1, 4},
            "plausible": plausible,
            "payload_prefix_hex": payload[:64].hex(),
            "media_analysis": media_analysis,
        }
    )
    return result


def _analyze_cpacket_stream(blob: bytes) -> dict:
    offsets = _find_cpacket_offsets(blob, limit=16)
    frames = [_parse_cpacket_header(blob, offset) for offset in offsets[:8]]
    complete_frames = sum(1 for frame in frames if frame.get("complete_frame"))
    plausible_frames = sum(1 for frame in frames if frame.get("plausible"))
    return {
        "blob_len": len(blob),
        "candidate_count": len(offsets),
        "candidate_offsets": offsets,
        "has_cpacket_header": bool(offsets),
        "plausible_frames": plausible_frames,
        "complete_frames": complete_frames,
        "frames": frames,
    }


def _analyze_container_probe(blob: bytes) -> dict:
    marker = bytes.fromhex("c0034002")
    marker_hits: list[int] = []
    cursor = 0
    while len(marker_hits) < 16:
        idx = blob.find(marker, cursor)
        if idx < 0:
            break
        marker_hits.append(idx)
        cursor = idx + len(marker)

    header0 = blob[:4]
    header1 = blob[4:8]
    nested = blob[4:] if len(blob) >= 4 else b""
    nested_start_code = nested.find(b"\x00\x00\x00\x01") if nested else -1
    nested_annexb = _analyze_annexb_h264(nested) if nested.startswith(b"\x00\x00\x00\x01") else {}
    false_nested_annexb = bool(nested_annexb.get("false_positive_sps_only"))
    cpacket_analysis = _analyze_cpacket_stream(blob)
    return {
        "blob_len": len(blob),
        "classification": "false_nested_annexb_probe" if false_nested_annexb else "unknown_container_probe",
        "prefix_hex": blob[:64].hex(),
        "suffix_hex": blob[-64:].hex() if blob else "",
        "header0_hex": header0.hex(),
        "header1_hex": header1.hex(),
        "header0_le": int.from_bytes(header0, "little") if len(header0) == 4 else None,
        "header0_be": int.from_bytes(header0, "big") if len(header0) == 4 else None,
        "header1_le": int.from_bytes(header1, "little") if len(header1) == 4 else None,
        "header1_be": int.from_bytes(header1, "big") if len(header1) == 4 else None,
        "marker_hits": marker_hits,
        "starts_with_probe_magic": header0 == marker,
        "nested_len": len(nested),
        "nested_start_code_at": nested_start_code,
        "nested_prefix_hex": nested[:64].hex(),
        "nested_annexb": nested_annexb,
        "false_nested_annexb": false_nested_annexb,
        "cpacket_analysis": cpacket_analysis,
    }


def _merge_binary_candidates(blobs: list[bytes]) -> tuple[list[bytes], bytes, str]:
    unique: list[bytes] = []
    seen = set()
    for blob in sorted(blobs, key=len, reverse=True):
        digest = hashlib.sha1(blob).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        unique.append(blob)

    if not unique:
        return [], b"", "none"

    min_overlap = 16
    stream = unique[0]
    strategy = "longest"
    for blob in sorted(unique[1:], key=len, reverse=True):
        if blob == stream or blob in stream or stream.startswith(blob):
            continue
        if stream in blob or blob.startswith(stream):
            stream = blob
            strategy = "right_extends_left"
            continue

        best_overlap = 0
        max_check = min(len(stream), len(blob))
        for k in range(max_check, min_overlap - 1, -1):
            if stream[-k:] == blob[:k]:
                best_overlap = k
                break
        if best_overlap >= min_overlap:
            stream += blob[best_overlap:]
            strategy = f"suffix_prefix_overlap:{best_overlap}"
            continue

        best_overlap = 0
        for k in range(max_check, min_overlap - 1, -1):
            if blob[-k:] == stream[:k]:
                best_overlap = k
                break
        if best_overlap >= min_overlap:
            stream = blob + stream[best_overlap:]
            strategy = f"prefix_suffix_overlap:{best_overlap}"
            continue

    return unique, stream, strategy


def _write_container_probe_summary(base_name: str, probe_blobs: list[bytes]) -> dict | None:
    unique, selected, strategy = _merge_binary_candidates(probe_blobs)
    if not unique:
        return None

    output_path = Path(f"{base_name}_container_probe.bin")
    best_path = Path(f"{base_name}_container_probe_best.bin")
    previous = b""
    if best_path.exists():
        try:
            previous = best_path.read_bytes()
        except Exception:
            previous = b""

    def _probe_family_prefix(blob: bytes) -> bytes:
        return blob[:16] if len(blob) >= 16 else blob

    if previous:
        if len(previous) == len(selected) and previous != selected:
            merged_best = selected
            persistent_strategy = "replace_equal_length_current"
        elif previous[:8] == selected[:8] and _probe_family_prefix(previous) != _probe_family_prefix(selected):
            merged_best = selected
            persistent_strategy = "replace_disjoint_same_header_current"
        else:
            _, merged_best, persistent_strategy = _merge_binary_candidates([previous, selected])
    else:
        merged_best = selected
        persistent_strategy = "right_only"

    output_path.write_bytes(selected)
    best_path.write_bytes(merged_best)
    analysis = _analyze_container_probe(merged_best)
    return {
        "candidate_count": len(unique),
        "candidate_lens": [len(blob) for blob in unique],
        "merge_strategy": strategy,
        "selected_len": len(selected),
        "selected_sha1": hashlib.sha1(selected).hexdigest(),
        "persistent_previous_len": len(previous),
        "persistent_merge_strategy": persistent_strategy,
        "persistent_len": len(merged_best),
        "persistent_sha1": hashlib.sha1(merged_best).hexdigest(),
        "analysis": analysis,
        "stream_path": str(output_path.resolve()),
        "persistent_path": str(best_path.resolve()),
    }


def _write_cpacket_probe_summary(base_name: str, cpacket_blobs: list[bytes]) -> dict | None:
    unique, selected, strategy = _merge_binary_candidates(cpacket_blobs)
    if not unique:
        return None

    output_path = Path(f"{base_name}_cpacket_probe.bin")
    best_path = Path(f"{base_name}_cpacket_probe_best.bin")
    previous = b""
    if best_path.exists():
        try:
            previous = best_path.read_bytes()
        except Exception:
            previous = b""

    if previous:
        _, merged_best, persistent_strategy = _merge_binary_candidates([previous, selected])
    else:
        merged_best = selected
        persistent_strategy = "right_only"

    output_path.write_bytes(selected)
    best_path.write_bytes(merged_best)
    analysis = _analyze_cpacket_stream(merged_best)
    return {
        "candidate_count": len(unique),
        "candidate_lens": [len(blob) for blob in unique],
        "merge_strategy": strategy,
        "selected_len": len(selected),
        "selected_sha1": hashlib.sha1(selected).hexdigest(),
        "persistent_previous_len": len(previous),
        "persistent_merge_strategy": persistent_strategy,
        "persistent_len": len(merged_best),
        "persistent_sha1": hashlib.sha1(merged_best).hexdigest(),
        "analysis": analysis,
        "stream_path": str(output_path.resolve()),
        "persistent_path": str(best_path.resolve()),
    }


def _write_embedded_h264_fallback(base_name: str, annexb_blobs: list[bytes]) -> dict:
    stream_path = Path(f"{base_name}_embedded.h264")
    mp4_path = Path(f"{base_name}_embedded.mp4")
    snapshot_path = Path(f"{base_name}_embedded.jpg")
    persistent_path = Path(f"{base_name}_embedded_best.h264")

    def merge_candidates(blobs: list[bytes]) -> tuple[list[bytes], bytes, str]:
        unique: list[bytes] = []
        seen = set()
        for blob in sorted(blobs, key=len, reverse=True):
            digest = hashlib.sha1(blob).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            unique.append(blob)

        if not unique:
            return [], b"", "none"

        stream = unique[0]
        merged = False
        for blob in sorted(unique[1:], key=len, reverse=True):
            if blob == stream:
                continue
            if blob in stream:
                continue
            if stream.startswith(blob):
                continue
            if blob.startswith(stream):
                stream = blob
                continue

            best_overlap = 0
            max_check = min(len(stream), len(blob))
            for k in range(max_check, 0, -1):
                if stream[-k:] == blob[:k]:
                    best_overlap = k
                    break
            if best_overlap > 0:
                stream += blob[best_overlap:]
                merged = True
                continue

            stream += blob
            merged = True
        return unique, stream, ("merged" if merged else "longest")

    def merge_two_streams(left: bytes, right: bytes) -> tuple[bytes, str]:
        min_overlap = 16
        if not left:
            return right, "right_only"
        if not right:
            return left, "left_only"
        if left == right:
            return left, "same"
        left_nal = _analyze_annexb_h264(left)
        right_nal = _analyze_annexb_h264(right)
        left_counts = left_nal.get("counts", {})
        right_counts = right_nal.get("counts", {})

        def is_sps_only(analysis: dict) -> bool:
            counts = analysis.get("counts", {})
            return (
                not analysis.get("has_vcl")
                and not analysis.get("has_pps")
                and set(counts.keys()) <= {"sps"}
                and sum(counts.values()) > 0
            )

        def is_degraded_sps_only(analysis: dict) -> bool:
            return is_sps_only(analysis) and int(analysis.get("counts", {}).get("sps", 0)) > 1

        def is_false_positive_sps_only(analysis: dict) -> bool:
            return bool(analysis.get("false_positive_sps_only"))

        if is_false_positive_sps_only(left_nal) and is_false_positive_sps_only(right_nal):
            return right, "replace_false_positive_with_current"

        if is_degraded_sps_only(left_nal) and is_sps_only(right_nal):
            return right, "replace_degraded_persistent_sps_only"
        if is_degraded_sps_only(right_nal) and is_sps_only(left_nal):
            return left, "keep_non_degraded_left_sps_only"
        if is_false_positive_sps_only(left_nal) and not is_false_positive_sps_only(right_nal):
            return right, "replace_false_positive_persistent"
        if is_false_positive_sps_only(right_nal) and not is_false_positive_sps_only(left_nal):
            return left, "keep_non_false_positive_left"

        if right in left or left.startswith(right):
            return left, "left_contains_right"
        if left in right or right.startswith(left):
            return right, "right_extends_left"

        best_overlap = 0
        max_check = min(len(left), len(right))
        for k in range(max_check, 0, -1):
            if left[-k:] == right[:k]:
                best_overlap = k
                break
        if best_overlap >= min_overlap:
            return left + right[best_overlap:], f"suffix_prefix_overlap:{best_overlap}"

        best_overlap = 0
        for k in range(max_check, 0, -1):
            if right[-k:] == left[:k]:
                best_overlap = k
                break
        if best_overlap >= min_overlap:
            return right + left[best_overlap:], f"prefix_suffix_overlap:{best_overlap}"

        # Two SPS-only streams without meaningful overlap should not be concatenated.
        if (
            is_sps_only(left_nal)
            and is_sps_only(right_nal)
        ):
            return right if len(right) >= len(left) else left, "prefer_longer_sps_only"

        return right, "replace_with_current_disjoint"

    unique, selected, strategy = merge_candidates(annexb_blobs)
    persistent_before = b""
    if persistent_path.exists():
        try:
            persistent_before = persistent_path.read_bytes()
        except Exception:
            persistent_before = b""
    selected, persistent_strategy = merge_two_streams(persistent_before, selected)

    if not unique:
        return {
            "candidate_count": 0,
            "merge_strategy": "none",
            "persistent_merge_strategy": "none",
            "candidate_lens": [],
            "persistent_previous_len": len(persistent_before),
            "selected_len": 0,
            "written": False,
            "mp4": False,
            "snapshot": False,
            "stream_path": str(stream_path.resolve()),
            "mp4_path": str(mp4_path.resolve()),
            "snapshot_path": str(snapshot_path.resolve()),
            "persistent_path": str(persistent_path.resolve()),
        }

    nal_analysis = _analyze_annexb_h264(selected)
    stream_path.write_bytes(selected)

    persistent_written = False
    if not nal_analysis.get("false_positive_sps_only"):
        try:
            persistent_path.write_bytes(selected)
            persistent_written = True
        except Exception:
            persistent_written = False

    mp4_ok = False
    mp4_error = ""
    ffmpeg_skipped_reason = ""
    if nal_analysis.get("false_positive_sps_only"):
        ffmpeg_skipped_reason = "single_sps_without_pps_vcl_or_epb"
    else:
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-loglevel",
                    "error",
                    "-f",
                    "h264",
                    "-i",
                    str(stream_path),
                    "-c:v",
                    "copy",
                    str(mp4_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            mp4_ok = mp4_path.exists()
        except Exception as exc:
            mp4_error = str(exc)

    snapshot_ok = False
    snapshot_error = ""
    if ffmpeg_skipped_reason:
        snapshot_error = ffmpeg_skipped_reason
    else:
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-loglevel",
                    "error",
                    "-f",
                    "h264",
                    "-i",
                    str(stream_path),
                    "-frames:v",
                    "1",
                    str(snapshot_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            snapshot_ok = snapshot_path.exists()
        except Exception as exc:
            snapshot_error = str(exc)

    return {
        "candidate_count": len(unique),
        "merge_strategy": strategy,
        "persistent_merge_strategy": persistent_strategy,
        "candidate_lens": [len(blob) for blob in unique],
        "persistent_previous_len": len(persistent_before),
        "selected_len": len(selected),
        "selected_sha1": hashlib.sha1(selected).hexdigest(),
        "nal_analysis": nal_analysis,
        "written": True,
        "persistent_written": persistent_written,
        "mp4": mp4_ok,
        "mp4_error": mp4_error,
        "snapshot": snapshot_ok,
        "snapshot_error": snapshot_error,
        "ffmpeg_skipped_reason": ffmpeg_skipped_reason,
        "stream_path": str(stream_path.resolve()),
        "mp4_path": str(mp4_path.resolve()),
        "snapshot_path": str(snapshot_path.resolve()),
        "persistent_path": str(persistent_path.resolve()),
    }


def main() -> None:
    config = AutonomousConfig()
    print("=== autonomous_preview ===")
    print(f"device_id={config.device_id} channel={config.channel} stream={config.stream}")

    credentials = fetch_runtime_credentials(config.device_id, ip_region_id=config.ip_region_id)
    print("fetched runtime credentials")

    credentials, response, test_response, tunnel = open_direct_preview(config, credentials=credentials)
    print("p2pconnect ok")
    _emit(
        {
            "public_ip": response.public_ip,
            "public_udp_port": response.public_udp_port,
            "utd_public_ip": response.utd_public_ip,
            "utd_public_udp_port": response.utd_public_udp_port,
            "response_local_ips": response.local_ips,
            "response_local_udp_port": response.local_udp_port,
            "test_peer": f"{test_response.address}:{test_response.port}",
            "test_id": test_response.test_id,
            "transport_peer": f"{tunnel.transport_peer_addr[0]}:{tunnel.transport_peer_addr[1]}",
            "logic_peer": f"{tunnel.peer_addr[0]}:{tunnel.peer_addr[1]}",
            "rbudp_local_id": tunnel.local_id,
            "rbudp_remote_id": tunnel.remote_id,
            "rbudp_word4": hex(tunnel.word4),
            "rbudp_word8": hex(tunnel.word8),
            "dest_id": tunnel.dest_id,
        }
    )

    tunnel.send_quii_setup(seq=0)
    print("sent quii setup")
    setup_acked = tunnel.wait_quii_setup_ack(timeout=3.0)
    _emit({"quii_setup_acked": setup_acked})
    tunnel.send_quii_play(credentials, seq=1)
    print("sent quii play")

    decoded_messages: list[dict] = []
    media_messages: list[dict] = []
    direct_blob_sample_path = Path("autonomous_direct_blob_samples.jsonl").resolve()
    wrapped_tail_sample_path = Path("autonomous_wrapped_quii_tail_samples.jsonl").resolve()
    fragment_partial_sample_path = Path("autonomous_fragment_partial_samples.jsonl").resolve()
    wrapped_tail_dump_dir = Path("autonomous_wrapped_quii_tail_bins").resolve()
    fragment_tail_dump_dir = Path("autonomous_fragment_tail_bins").resolve()
    if SAVE_DIAGNOSTIC_ARTIFACTS:
        wrapped_tail_dump_dir.mkdir(exist_ok=True)
        fragment_tail_dump_dir.mkdir(exist_ok=True)
    seen_direct_blob_hashes: set[str] = set()
    seen_wrapped_tail_hashes: set[str] = set()
    seen_fragment_partial_hashes: set[str] = set()
    embedded_h264_candidates: list[bytes] = []
    container_probe_candidates: list[bytes] = []
    cpacket_candidates: list[bytes] = []
    deadline = time.time() + PREVIEW_CAPTURE_SECONDS
    message_index = 0
    tunnel_closed = False
    summary_emit_state: dict[str, int] = {}
    fragmented_media_state: dict | None = None

    try:
        while time.time() < deadline:
            try:
                packet = tunnel.recv_packet(timeout=5.0)
            except queue.Empty:
                continue
            blob = bytes(packet["payload"])
            source = str(packet.get("source", "unknown"))
            meta = dict(packet.get("meta", {}))
            message_index += 1
            if fragmented_media_state is not None:
                decoded_fragment, remainder, fragment_summary = _append_fragmented_media(
                    fragmented_media_state,
                    blob,
                    credentials.data_encode_key,
                    source=source,
                    meta=meta,
                    message_index=message_index,
                )
                _emit(fragment_summary)
                if decoded_fragment is None:
                    continue
                fragmented_media_state = None
                _record_fragmented_media_decoded(
                    decoded_fragment,
                    message_index=message_index,
                    blob_len=fragment_summary["expected_body_len"] + 32,
                    source="wrapped_quii_fragmented_media",
                    meta=dict(decoded_fragment.get("fragmented_media", {})),
                    decoded_messages=decoded_messages,
                    media_messages=media_messages,
                    summary_emit_state=summary_emit_state,
                )
                if _should_stop_media_collection(media_messages):
                    break
                if not remainder:
                    continue
                blob = remainder
                source = "wrapped_quii_fragmented_remainder"
                meta = {"from_msg_index": message_index, "remainder_len": len(remainder)}
                if len(blob) < 32:
                    _emit(
                        {
                            "msg_index": message_index,
                            "source": source,
                            "fragmented_media": "drop_short_remainder",
                            "blob_len": len(blob),
                        }
                    )
                    continue
            decoded = decode_quii_blob(blob, credentials.data_encode_key, crypto_mode=2)
            if _should_start_fragmented_media(decoded, source):
                fragmented_media_state = _start_fragmented_media(
                    decoded,
                    source=source,
                    meta=meta,
                    message_index=message_index,
                )
                _emit(
                    {
                        "msg_index": message_index,
                        "source": source,
                        "blob_len": len(blob),
                        "fragmented_media": "start",
                        "expected_body_len": fragmented_media_state["expected_body_len"],
                        "have_body_len": len(fragmented_media_state["body"]),
                        "packet_type": hex(fragmented_media_state["packet_type"]),
                        "raw_size": fragmented_media_state["raw_size"],
                        "frame_tag": hex(fragmented_media_state["frame_tag"]),
                        "frame_len": fragmented_media_state["frame_len"],
                        "meta": meta,
                    }
                )
                continue
            candidates: list[dict] = []
            if source == "direct_quii_blob" and not decoded["plausible"]:
                candidates = find_quii_decode_candidates(blob, credentials.data_encode_key, crypto_mode=2)
                blob_hash = hashlib.sha1(blob).hexdigest()
                if blob_hash not in seen_direct_blob_hashes and len(seen_direct_blob_hashes) < DIRECT_BLOB_SAMPLE_LIMIT:
                    seen_direct_blob_hashes.add(blob_hash)
                    if SAVE_DIAGNOSTIC_ARTIFACTS:
                        _append_jsonl(
                            direct_blob_sample_path,
                            {
                                "sha1": blob_hash,
                                "msg_index": message_index,
                                "source": source,
                                "meta": meta,
                                "blob_len": len(blob),
                                "blob_hex": blob.hex(),
                                "candidates": candidates,
                            },
                        )
            fragment_partial_analysis = None
            if source == "wrapped_fragment_partial":
                fragment_partial_analysis = analyze_partial_wrapped_inner(blob, credentials.data_encode_key)
                payload_dec = fragment_partial_analysis.get("payload_decode")
                if isinstance(payload_dec, dict) and payload_dec.get("plausible"):
                    decoded_for_dump = decode_quii_blob(blob[0x38:], credentials.data_encode_key, crypto_mode=2)
                    embedded_h264 = _candidate_embedded_h264(blob[0x38:], credentials.data_encode_key, decoded_for_dump)
                    if embedded_h264:
                        embedded_h264_candidates.append(embedded_h264)
                    container_probe_blob = _candidate_container_probe(
                        blob[0x38:], credentials.data_encode_key, decoded_for_dump
                    )
                    if container_probe_blob:
                        container_probe_candidates.append(container_probe_blob)
                    cpacket_blob = _candidate_cpacket_stream(
                        blob[0x38:], credentials.data_encode_key, decoded_for_dump
                    )
                    if cpacket_blob:
                        cpacket_candidates.append(cpacket_blob)
                    if SAVE_DIAGNOSTIC_ARTIFACTS:
                        fragment_partial_analysis.update(
                            _dump_partial_tail_artifacts(
                                blob=blob[0x38:],
                                key=credentials.data_encode_key,
                                decoded=decoded_for_dump,
                                dump_dir=fragment_tail_dump_dir,
                                stem=f"msg_{message_index:03d}_{source}",
                            )
                        )
                else:
                    payload_probe = _candidate_container_probe_from_partial_payload(
                        blob[0x38:], credentials.data_encode_key
                    )
                    if payload_probe:
                        container_probe_candidates.append(payload_probe)
                blob_hash = hashlib.sha1(blob).hexdigest()
                if (
                    blob_hash not in seen_fragment_partial_hashes
                    and len(seen_fragment_partial_hashes) < FRAGMENT_PARTIAL_SAMPLE_LIMIT
                ):
                    seen_fragment_partial_hashes.add(blob_hash)
                    if SAVE_DIAGNOSTIC_ARTIFACTS:
                        _append_jsonl(
                            fragment_partial_sample_path,
                            {
                                "sha1": blob_hash,
                                "msg_index": message_index,
                                "source": source,
                                "meta": meta,
                                "analysis": fragment_partial_analysis,
                            },
                        )
            if decoded["plausible"]:
                decoded_messages.append(decoded)
            header = decoded["header"]
            wrapped_tail_analysis = None
            if source == "wrapped_quii" and decoded["plausible"]:
                wrapped_tail_analysis = analyze_wrapped_quii_tail(
                    blob,
                    credentials.data_encode_key,
                    decoded,
                )
                if wrapped_tail_analysis is not None:
                    decrypted_tail = decrypt_wrapped_quii_tail_bytes(
                        blob,
                        credentials.data_encode_key,
                        decoded,
                    )
                    if SAVE_DIAGNOSTIC_ARTIFACTS and decrypted_tail:
                        dump_path = wrapped_tail_dump_dir / f"msg_{message_index:03d}_{source}.bin"
                        dump_path.write_bytes(decrypted_tail)
                        wrapped_tail_analysis["decrypted_dump_path"] = str(dump_path)
                    tail_hash = hashlib.sha1(blob).hexdigest()
                    if (
                        tail_hash not in seen_wrapped_tail_hashes
                        and len(seen_wrapped_tail_hashes) < WRAPPED_TAIL_SAMPLE_LIMIT
                    ):
                        seen_wrapped_tail_hashes.add(tail_hash)
                        if SAVE_DIAGNOSTIC_ARTIFACTS:
                            _append_jsonl(
                                wrapped_tail_sample_path,
                                {
                                    "sha1": tail_hash,
                                    "msg_index": message_index,
                                    "source": source,
                                    "meta": meta,
                                    "analysis": wrapped_tail_analysis,
                                    "blob_len": len(blob),
                                    "blob_prefix": blob[:128].hex(),
                                },
                            )
            summary = {
                "msg_index": message_index,
                "source": source,
                "blob_len": len(blob),
                "packet_type": hex(header.packet_type),
                "payload_size": header.payload_size,
                "raw_size": header.raw_size,
                "flag15": header.flag15,
                "flag16": header.flag16,
                "flag17": header.flag17,
                "is_media": decoded["is_media"],
                "plausible": decoded["plausible"],
                "offset": decoded["offset"],
                "payload_prefix": decoded["payload"][:32].hex(),
            }
            if meta:
                summary["meta"] = meta
            if decoded["text_preview"]:
                summary["text_preview"] = decoded["text_preview"]
            if candidates:
                summary["decode_candidates"] = candidates[:6]
            if wrapped_tail_analysis is not None:
                summary["wrapped_tail_analysis"] = wrapped_tail_analysis
            if fragment_partial_analysis is not None:
                summary["fragment_partial_analysis"] = fragment_partial_analysis
            if decoded["media_frame"] is not None:
                frame = decoded["media_frame"]
                summary["frame_tag"] = hex(frame["frame_tag"])
                summary["frame_len"] = frame["frame_len"]
                summary["frame_stamp"] = frame["frame_stamp"]
                summary["width"] = frame["width"]
                summary["height"] = frame["height"]
                media_messages.append(decoded)
            _emit_packet_summary(
                summary,
                source=source,
                decoded=decoded,
                state=summary_emit_state,
            )
            if _should_stop_media_collection(media_messages):
                break

        tunnel.flush_fragment_partials()
        flush_deadline = time.time() + 1.0
        while time.time() < flush_deadline:
            try:
                packet = tunnel.recv_packet(timeout=0.1)
            except queue.Empty:
                break
            blob = bytes(packet["payload"])
            source = str(packet.get("source", "unknown"))
            meta = dict(packet.get("meta", {}))
            message_index += 1
            if fragmented_media_state is not None:
                decoded_fragment, remainder, fragment_summary = _append_fragmented_media(
                    fragmented_media_state,
                    blob,
                    credentials.data_encode_key,
                    source=source,
                    meta=meta,
                    message_index=message_index,
                )
                _emit(fragment_summary)
                if decoded_fragment is None:
                    continue
                fragmented_media_state = None
                _record_fragmented_media_decoded(
                    decoded_fragment,
                    message_index=message_index,
                    blob_len=fragment_summary["expected_body_len"] + 32,
                    source="wrapped_quii_fragmented_media",
                    meta=dict(decoded_fragment.get("fragmented_media", {})),
                    decoded_messages=decoded_messages,
                    media_messages=media_messages,
                    summary_emit_state=summary_emit_state,
                )
                if not remainder:
                    continue
                blob = remainder
                source = "wrapped_quii_fragmented_remainder"
                meta = {"from_msg_index": message_index, "remainder_len": len(remainder)}
                if len(blob) < 32:
                    _emit(
                        {
                            "msg_index": message_index,
                            "source": source,
                            "fragmented_media": "drop_short_remainder",
                            "blob_len": len(blob),
                        }
                    )
                    continue
            decoded = decode_quii_blob(blob, credentials.data_encode_key, crypto_mode=2)
            if _should_start_fragmented_media(decoded, source):
                fragmented_media_state = _start_fragmented_media(
                    decoded,
                    source=source,
                    meta=meta,
                    message_index=message_index,
                )
                _emit(
                    {
                        "msg_index": message_index,
                        "source": source,
                        "blob_len": len(blob),
                        "fragmented_media": "start",
                        "expected_body_len": fragmented_media_state["expected_body_len"],
                        "have_body_len": len(fragmented_media_state["body"]),
                        "packet_type": hex(fragmented_media_state["packet_type"]),
                        "raw_size": fragmented_media_state["raw_size"],
                        "frame_tag": hex(fragmented_media_state["frame_tag"]),
                        "frame_len": fragmented_media_state["frame_len"],
                        "meta": meta,
                    }
                )
                continue
            candidates: list[dict] = []
            if source == "direct_quii_blob" and not decoded["plausible"]:
                candidates = find_quii_decode_candidates(blob, credentials.data_encode_key, crypto_mode=2)
            fragment_partial_analysis = None
            if source == "wrapped_fragment_partial":
                fragment_partial_analysis = analyze_partial_wrapped_inner(blob, credentials.data_encode_key)
                payload_dec = fragment_partial_analysis.get("payload_decode")
                if isinstance(payload_dec, dict) and payload_dec.get("plausible"):
                    decoded_for_dump = decode_quii_blob(blob[0x38:], credentials.data_encode_key, crypto_mode=2)
                    embedded_h264 = _candidate_embedded_h264(blob[0x38:], credentials.data_encode_key, decoded_for_dump)
                    if embedded_h264:
                        embedded_h264_candidates.append(embedded_h264)
                    container_probe_blob = _candidate_container_probe(
                        blob[0x38:], credentials.data_encode_key, decoded_for_dump
                    )
                    if container_probe_blob:
                        container_probe_candidates.append(container_probe_blob)
                    cpacket_blob = _candidate_cpacket_stream(
                        blob[0x38:], credentials.data_encode_key, decoded_for_dump
                    )
                    if cpacket_blob:
                        cpacket_candidates.append(cpacket_blob)
                    if SAVE_DIAGNOSTIC_ARTIFACTS:
                        fragment_partial_analysis.update(
                            _dump_partial_tail_artifacts(
                                blob=blob[0x38:],
                                key=credentials.data_encode_key,
                                decoded=decoded_for_dump,
                                dump_dir=fragment_tail_dump_dir,
                                stem=f"msg_{message_index:03d}_{source}",
                            )
                        )
                else:
                    payload_probe = _candidate_container_probe_from_partial_payload(
                        blob[0x38:], credentials.data_encode_key
                    )
                    if payload_probe:
                        container_probe_candidates.append(payload_probe)
                blob_hash = hashlib.sha1(blob).hexdigest()
                if (
                    blob_hash not in seen_fragment_partial_hashes
                    and len(seen_fragment_partial_hashes) < FRAGMENT_PARTIAL_SAMPLE_LIMIT
                ):
                    seen_fragment_partial_hashes.add(blob_hash)
                    if SAVE_DIAGNOSTIC_ARTIFACTS:
                        _append_jsonl(
                            fragment_partial_sample_path,
                            {
                                "sha1": blob_hash,
                                "msg_index": message_index,
                                "source": source,
                                "meta": meta,
                                "analysis": fragment_partial_analysis,
                            },
                        )
            if decoded["plausible"]:
                decoded_messages.append(decoded)
            header = decoded["header"]
            summary = {
                "msg_index": message_index,
                "source": source,
                "blob_len": len(blob),
                "packet_type": hex(header.packet_type),
                "payload_size": header.payload_size,
                "raw_size": header.raw_size,
                "flag15": header.flag15,
                "flag16": header.flag16,
                "flag17": header.flag17,
                "is_media": decoded["is_media"],
                "plausible": decoded["plausible"],
                "offset": decoded["offset"],
                "payload_prefix": decoded["payload"][:32].hex(),
            }
            if meta:
                summary["meta"] = meta
            if candidates:
                summary["decode_candidates"] = candidates[:6]
            if fragment_partial_analysis is not None:
                summary["fragment_partial_analysis"] = fragment_partial_analysis
            if decoded["text_preview"]:
                summary["text_preview"] = decoded["text_preview"]
            _emit_packet_summary(
                summary,
                source=source,
                decoded=decoded,
                state=summary_emit_state,
            )

        tunnel.close()
        tunnel_closed = True

        close_drain_deadline = time.time() + 0.5
        while time.time() < close_drain_deadline:
            try:
                packet = tunnel.recv_packet(timeout=0.05)
            except queue.Empty:
                break
            blob = bytes(packet["payload"])
            source = str(packet.get("source", "unknown"))
            meta = dict(packet.get("meta", {}))
            message_index += 1
            if fragmented_media_state is not None:
                decoded_fragment, remainder, fragment_summary = _append_fragmented_media(
                    fragmented_media_state,
                    blob,
                    credentials.data_encode_key,
                    source=source,
                    meta=meta,
                    message_index=message_index,
                )
                _emit(fragment_summary)
                if decoded_fragment is None:
                    continue
                fragmented_media_state = None
                _record_fragmented_media_decoded(
                    decoded_fragment,
                    message_index=message_index,
                    blob_len=fragment_summary["expected_body_len"] + 32,
                    source="wrapped_quii_fragmented_media",
                    meta=dict(decoded_fragment.get("fragmented_media", {})),
                    decoded_messages=decoded_messages,
                    media_messages=media_messages,
                    summary_emit_state=summary_emit_state,
                )
                if not remainder:
                    continue
                blob = remainder
                source = "wrapped_quii_fragmented_remainder"
                meta = {"from_msg_index": message_index, "remainder_len": len(remainder)}
                if len(blob) < 32:
                    _emit(
                        {
                            "msg_index": message_index,
                            "source": source,
                            "fragmented_media": "drop_short_remainder",
                            "blob_len": len(blob),
                        }
                    )
                    continue
            decoded = decode_quii_blob(blob, credentials.data_encode_key, crypto_mode=2)
            if _should_start_fragmented_media(decoded, source):
                fragmented_media_state = _start_fragmented_media(
                    decoded,
                    source=source,
                    meta=meta,
                    message_index=message_index,
                )
                _emit(
                    {
                        "msg_index": message_index,
                        "source": source,
                        "blob_len": len(blob),
                        "fragmented_media": "start",
                        "expected_body_len": fragmented_media_state["expected_body_len"],
                        "have_body_len": len(fragmented_media_state["body"]),
                        "packet_type": hex(fragmented_media_state["packet_type"]),
                        "raw_size": fragmented_media_state["raw_size"],
                        "frame_tag": hex(fragmented_media_state["frame_tag"]),
                        "frame_len": fragmented_media_state["frame_len"],
                        "meta": meta,
                    }
                )
                continue
            fragment_partial_analysis = None
            if source == "wrapped_fragment_partial":
                fragment_partial_analysis = analyze_partial_wrapped_inner(blob, credentials.data_encode_key)
                payload_dec = fragment_partial_analysis.get("payload_decode")
                if isinstance(payload_dec, dict) and payload_dec.get("plausible"):
                    decoded_for_dump = decode_quii_blob(blob[0x38:], credentials.data_encode_key, crypto_mode=2)
                    embedded_h264 = _candidate_embedded_h264(blob[0x38:], credentials.data_encode_key, decoded_for_dump)
                    if embedded_h264:
                        embedded_h264_candidates.append(embedded_h264)
                    container_probe_blob = _candidate_container_probe(
                        blob[0x38:], credentials.data_encode_key, decoded_for_dump
                    )
                    if container_probe_blob:
                        container_probe_candidates.append(container_probe_blob)
                    cpacket_blob = _candidate_cpacket_stream(
                        blob[0x38:], credentials.data_encode_key, decoded_for_dump
                    )
                    if cpacket_blob:
                        cpacket_candidates.append(cpacket_blob)
                    if SAVE_DIAGNOSTIC_ARTIFACTS:
                        fragment_partial_analysis.update(
                            _dump_partial_tail_artifacts(
                                blob=blob[0x38:],
                                key=credentials.data_encode_key,
                                decoded=decoded_for_dump,
                                dump_dir=fragment_tail_dump_dir,
                                stem=f"msg_{message_index:03d}_{source}",
                            )
                        )
                else:
                    payload_probe = _candidate_container_probe_from_partial_payload(
                        blob[0x38:], credentials.data_encode_key
                    )
                    if payload_probe:
                        container_probe_candidates.append(payload_probe)
                blob_hash = hashlib.sha1(blob).hexdigest()
                if (
                    blob_hash not in seen_fragment_partial_hashes
                    and len(seen_fragment_partial_hashes) < FRAGMENT_PARTIAL_SAMPLE_LIMIT
                ):
                    seen_fragment_partial_hashes.add(blob_hash)
                    if SAVE_DIAGNOSTIC_ARTIFACTS:
                        _append_jsonl(
                            fragment_partial_sample_path,
                            {
                                "sha1": blob_hash,
                                "msg_index": message_index,
                                "source": source,
                                "meta": meta,
                                "analysis": fragment_partial_analysis,
                            },
                        )
            if decoded["plausible"]:
                decoded_messages.append(decoded)
            summary = {
                "msg_index": message_index,
                "source": source,
                "blob_len": len(blob),
                "packet_type": hex(decoded["header"].packet_type),
                "payload_size": decoded["header"].payload_size,
                "raw_size": decoded["header"].raw_size,
                "flag15": decoded["header"].flag15,
                "flag16": decoded["header"].flag16,
                "flag17": decoded["header"].flag17,
                "is_media": decoded["is_media"],
                "plausible": decoded["plausible"],
                "offset": decoded["offset"],
                "payload_prefix": decoded["payload"][:32].hex(),
            }
            if meta:
                summary["meta"] = meta
            if fragment_partial_analysis is not None:
                summary["fragment_partial_analysis"] = fragment_partial_analysis
            if decoded["text_preview"]:
                summary["text_preview"] = decoded["text_preview"]
            _emit_packet_summary(
                summary,
                source=source,
                decoded=decoded,
                state=summary_emit_state,
            )

        if decoded_messages:
            output_base = str(_timestamped_output_base())
            media_result = write_h264_stream(output_base, decoded_messages)
            container_probe_summary = None
            if SAVE_DIAGNOSTIC_ARTIFACTS and container_probe_candidates:
                container_probe_summary = _write_container_probe_summary(
                    output_base,
                    container_probe_candidates,
                )
            cpacket_probe_summary = None
            if SAVE_DIAGNOSTIC_ARTIFACTS and cpacket_candidates:
                cpacket_probe_summary = _write_cpacket_probe_summary(
                    output_base,
                    cpacket_candidates,
                )
            if (
                SAVE_DIAGNOSTIC_ARTIFACTS
                and
                media_result.get("summary", {}).get("assembled_units", 0) == 0
                and embedded_h264_candidates
            ):
                media_result["embedded_fallback"] = _write_embedded_h264_fallback(
                    output_base,
                    embedded_h264_candidates,
                )
            _emit(
                {
                    "decoded_messages": len(decoded_messages),
                    "media_messages": len(media_messages),
                    "media_collection": _media_collection_summary(media_messages),
                    "implausible_direct_suppressed": summary_emit_state.get(
                        "implausible_direct_suppressed", 0
                    ),
                    "stream_payload_count": tunnel.stream_payload_count,
                    "stream_payload_filler_count": tunnel.stream_payload_filler_count,
                    "diagnostic_artifacts_saved": SAVE_DIAGNOSTIC_ARTIFACTS,
                    "media_result": media_result,
                    "container_probe_summary": container_probe_summary,
                    "cpacket_probe_summary": cpacket_probe_summary,
                }
            )
        else:
            embedded_fallback = None
            output_base = str(_timestamped_output_base())
            container_probe_summary = None
            if SAVE_DIAGNOSTIC_ARTIFACTS and container_probe_candidates:
                container_probe_summary = _write_container_probe_summary(
                    output_base,
                    container_probe_candidates,
                )
            cpacket_probe_summary = None
            if SAVE_DIAGNOSTIC_ARTIFACTS and cpacket_candidates:
                cpacket_probe_summary = _write_cpacket_probe_summary(
                    output_base,
                    cpacket_candidates,
                )
            if SAVE_DIAGNOSTIC_ARTIFACTS and embedded_h264_candidates:
                embedded_fallback = _write_embedded_h264_fallback(
                    output_base,
                    embedded_h264_candidates,
                )
            _emit(
                {
                    "decoded_messages": 0,
                    "media_collection": _media_collection_summary(media_messages),
                    "implausible_direct_suppressed": summary_emit_state.get(
                        "implausible_direct_suppressed", 0
                    ),
                    "stream_payload_count": tunnel.stream_payload_count,
                    "stream_payload_filler_count": tunnel.stream_payload_filler_count,
                    "stream_payload_early_count": tunnel.stream_payload_early_count,
                    "stream_payload_early_filler_count": tunnel.stream_payload_early_filler_count,
                    "diagnostic_artifacts_saved": SAVE_DIAGNOSTIC_ARTIFACTS,
                    "embedded_fallback": embedded_fallback,
                    "container_probe_summary": container_probe_summary,
                    "cpacket_probe_summary": cpacket_probe_summary,
                }
            )
    finally:
        if not tunnel_closed:
            tunnel.close()


if __name__ == "__main__":
    main()
