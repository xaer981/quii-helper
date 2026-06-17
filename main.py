import base64
import hashlib
import http.cookiejar
import socket
import ssl
import struct
import subprocess
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from constants import (CLOUD_ACCOUNT, CLOUD_CLIENT_UUID, CLOUD_PASSWORD,
                       DEVICE_ID)

CLOUD_HOST = "r6-5.qvcloud.net"
CLOUD_PORT = 443
CLOUD_SCHEME = "https"
CLOUD_PATH = "/auth/user"
CLOUD_OEM_ID = "G0083"
CLOUD_APP_ID = 4083
CLOUD_CLIENT_TYPE = 3
CLOUD_AUTH_VERSION = "v1.13"
CLOUD_COOKIE = ""
CLOUD_LOGIN_SEQ = 1

HOST = "192.168.1.176"
AUTH_CODE = "135531"
DEVICE_PASSWORD = "135531"
NC = "0123456789abcdef0123456789abcdef"

# Cloud account credentials.
IS_HS_DEVICE = None

# Quii probe defaults. These likely need tuning per device/stream.
QUII_HOST = HOST
QUII_PORT = 34567
QUII_CHANNEL = 1
QUII_STREAM = 2
QUII_AP = 2
QUII_USE_FORWARDED_RELAY = True
QUII_RELAY_HOST = "127.0.0.1"
QUII_RELAY_PORT = 45723
QUII_RELAY_CHANNEL = 1
QUII_RELAY_STREAM = 1
QUII_RELAY_NEWCN = False
QUII_CHANNEL_CANDIDATES = [0, 1, 2, 3]
QUII_STREAM_CANDIDATES = [1, 2, 0]
QUII_USE_INNER = False
QUII_USE_NEWCN = False
QUII_NEWCN_CANDIDATES = [False, True]
QUII_USERNAME = CLOUD_ACCOUNT
QUII_RUN_PROBE = True
QUII_DUMP_FILE = Path("quii_probe_dump.bin")
QUII_NUM_MESSAGES = 80
QUII_EXTRACT_STREAM = True
QUII_RENDER_SNAPSHOT = True
QUII_KEEP_RAW_H264 = False
QUII_PRINT_FULL_PROBE = False
RUN_DEVICE_CGI_PROBES = False
RUN_CLOUD_FLOW = True

LOGIN_REQ_CLASS = "com.quvii.qvweb.userauth.bean.request.LoginReqContent"
DEVICE_TOKEN_REQ_CLASS = "com.quvii.qvweb.userauth.bean.request.DevDynamicPwdGetReqContent"

CLOUD_COOKIE_JAR = http.cookiejar.CookieJar()


@dataclass
class QuiiHeader:
    packet_type: int
    payload_size: int
    raw_size: int
    flag13: int
    flag14: int
    flag15: int
    flag16: int
    flag17: int
    raw: bytes


class QuiiClient:
    def __init__(self, host: str, port: int, username: str, password: str, path: str, key: str):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.path = path
        self.key = key or ""
        self.sock: socket.socket | None = None
        self.crypto_mode = 0

    def connect(self, timeout: float = 8.0):
        self.sock = socket.create_connection((self.host, self.port), timeout=timeout)
        self.sock.settimeout(timeout)

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def recv_exact(self, size: int) -> bytes:
        if self.sock is None:
            raise RuntimeError("socket is not connected")
        chunks: list[bytes] = []
        remaining = size
        while remaining > 0:
            chunk = self.sock.recv(remaining)
            if not chunk:
                raise RuntimeError(f"socket closed while reading {size} bytes")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def send_setup(self) -> bytes:
        if self.sock is None:
            raise RuntimeError("socket is not connected")
        packet = bytearray(32)
        packet[0] = 0xA9
        packet[31] = 0x00
        self.sock.sendall(packet)
        return bytes(packet)

    def recv_setup(self) -> dict:
        response = self.recv_exact(32)
        status = response[9]
        crypto_mode = response[10]
        self.crypto_mode = crypto_mode if crypto_mode in (0, 1, 2) else 0
        return {
            "raw": response,
            "status": status,
            "crypto_mode": crypto_mode,
        }

    def send_live_open(self, play_param: int = 1, stream_flag: int = 0) -> bytes:
        packet = self.build_live_open_packet(play_param=play_param, stream_flag=stream_flag)
        if self.sock is None:
            raise RuntimeError("socket is not connected")
        self.sock.sendall(packet)
        return packet

    def build_live_open_packet(self, play_param: int = 1, stream_flag: int = 0) -> bytes:
        payload = (
            self.username.encode("utf-8")
            + b"&&"
            + self.password.encode("utf-8")
            + b"\x00"
            + self.path.encode("utf-8")
            + b"\x00"
        )
        raw_size = len(payload)
        payload_with_sha = payload
        header_without_sizes = bytearray(32)
        header_without_sizes[0] = 0x01
        header_without_sizes[1:9] = struct.pack("<Q", int(time.time() * 1000))
        header_without_sizes[13] = 0
        header_without_sizes[14] = 0
        header_without_sizes[15] = play_param & 0xFF
        header_without_sizes[16] = stream_flag & 0xFF
        header_without_sizes[17] = 1 if QUII_USE_INNER else 0

        sha_len = 32
        padded_size = raw_size + sha_len
        if self.crypto_mode in (1, 2):
            block = 16
            padded_size = ((padded_size + block - 1) // block) * block

        header_without_sizes[9:11] = struct.pack("<H", padded_size)
        header_without_sizes[11:13] = struct.pack("<H", raw_size)

        sha = hashlib.sha256(bytes(header_without_sizes) + payload_with_sha).digest()
        body = payload_with_sha + sha
        if len(body) < padded_size:
            body += b"\x00" * (padded_size - len(body))

        if self.crypto_mode == 0:
            return bytes(header_without_sizes) + body

        encrypted_header = self._aes_crypt(bytes(header_without_sizes), decrypt=False, media=False)
        encrypted_body = self._aes_crypt(body, decrypt=False, media=False)
        return encrypted_header + encrypted_body

    def recv_message(self, dump_file: Path | None = None) -> dict:
        header_raw = self.recv_exact(32)
        if self.crypto_mode == 0:
            header = header_raw
        else:
            header = self._aes_crypt(header_raw, decrypt=True, media=False)

        packet_type = header[0]
        command_payload_size = int.from_bytes(header[9:11], "little")
        raw_size = int.from_bytes(header[11:13], "little")
        media_payload_size = int.from_bytes(header[11:15], "little")
        parsed = QuiiHeader(
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

        is_media = packet_type in (0xA0, 0xA1, 0xA2, 0xA3)
        read_size = media_payload_size if is_media else command_payload_size

        payload = b""
        if read_size > 0:
            payload_raw = self.recv_exact(read_size)
            if self.crypto_mode == 0:
                payload = payload_raw
            elif is_media:
                command_part_len = min(command_payload_size, len(payload_raw))
                command_part = payload_raw[:command_part_len]
                media_part = payload_raw[command_part_len:]
                if command_part_len:
                    command_part = self._aes_crypt(command_part, decrypt=True, media=False)
                if media_part and header[15] != 0:
                    media_part = self._aes_crypt(media_part, decrypt=True, media=True)
                payload = command_part + media_part
            else:
                payload = self._aes_crypt(payload_raw, decrypt=True, media=False)
        else:
            payload_raw = b""

        if dump_file is not None:
            with dump_file.open("ab") as fp:
                fp.write(header_raw)
                fp.write(payload_raw)

        return {
            "header": parsed,
            "payload": payload,
            "payload_raw": payload_raw,
        }

    def probe_live(self, dump_file: Path | None = None, num_messages: int = QUII_NUM_MESSAGES, play_param: int = 1) -> dict:
        dump_file = dump_file or QUII_DUMP_FILE
        if dump_file.exists():
            dump_file.unlink()

        self.connect()
        setup_request = self.send_setup()
        setup_response = self.recv_setup()
        open_request = self.send_live_open(play_param=play_param)

        messages = []
        for _ in range(num_messages):
            try:
                messages.append(self.recv_message(dump_file=dump_file))
            except Exception as exc:
                messages.append({"error": str(exc)})
                break

        return {
            "setup_request": setup_request,
            "setup_response": setup_response,
            "open_request": open_request,
            "messages": messages,
            "dump_file": str(dump_file.resolve()),
        }

    def _key_bytes(self) -> bytes:
        if self.crypto_mode == 1:
            return self.key.encode("utf-8")[:16].ljust(16, b"\x00")
        if self.crypto_mode == 2:
            return self.key.encode("utf-8")[:32].ljust(32, b"\x00")
        return b""

    def _aes_crypt(self, data: bytes, *, decrypt: bool, media: bool) -> bytes:
        key = self._key_bytes()
        if not key:
            return data
        iv = b"0" * 16
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        if decrypt:
            ctx = cipher.decryptor()
        else:
            ctx = cipher.encryptor()
        return ctx.update(data) + ctx.finalize()


def encode_device_password(value: str) -> str:
    if value is None or len(value) < 64:
        return hashlib.sha256((value or "").encode("utf-8")).hexdigest()
    return value


def get_encrypt_password(username: str, password: str, nc: str) -> str:
    key = hashlib.sha256(f"{username}:{nc}".encode("utf-8")).digest()
    iv = b"0" * 16

    raw = password.encode("utf-8")
    padded_len = (len(raw) + 15) & ~0x0F
    padded = raw.ljust(padded_len, b"\x00")

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    encrypted = cipher.update(padded) + cipher.finalize()
    return base64.b64encode(encrypted).decode("ascii")


def build_request_xml(
    command: str,
    security: str,
    username: str,
    password: str,
    nc: str | None = None,
    passwordencode: str | None = None,
) -> bytes:
    envelope = ET.Element("envelope")

    body = ET.SubElement(envelope, "body")
    ET.SubElement(body, "command").text = command
    ET.SubElement(body, "content")

    header = ET.SubElement(envelope, "header")
    ET.SubElement(header, "password").text = password
    if passwordencode is not None:
        ET.SubElement(header, "passwordencode").text = passwordencode
    ET.SubElement(header, "security").text = security
    ET.SubElement(header, "username").text = username
    if nc:
        ET.SubElement(header, "nc").text = nc

    return ET.tostring(envelope, encoding="utf-8", xml_declaration=False)


def build_quii_live_path(
    channel: int | None = None,
    stream: int | None = None,
    ap: int = QUII_AP,
    inner: bool = QUII_USE_INNER,
    newcn: bool = QUII_USE_NEWCN,
    connect_mode: int | None = None,
) -> str:
    channel = QUII_CHANNEL if channel is None else channel
    stream = QUII_STREAM if stream is None else stream
    path = f"/mode=real&idc={channel}&ids={stream}"
    if inner:
        path += "&inner=1"
    if newcn:
        path += "&newcn=1"
    if connect_mode is not None:
        path += f"&connect_mode={int(connect_mode)}"
    path += f"&ap={ap}"
    return path


def quii_escape_password(value: str) -> str:
    return value.replace("@", "@@") if value else ""


def build_quii_live_url(
    username: str,
    password: str,
    host: str,
    port: int,
    *,
    channel: int | None = None,
    stream: int | None = None,
) -> str:
    return f"quii://{username}:{quii_escape_password(password)}@{host}:{port}{build_quii_live_path(channel=channel, stream=stream)}"


def parse_quii_media_frame(payload: bytes) -> dict | None:
    if len(payload) < 0x14:
        return None
    if payload[:3] != b"\x00\x00\x01":
        return None

    frame_tag = payload[3]
    frame_len = int.from_bytes(payload[4:8], "little")
    frame_stamp = int.from_bytes(payload[8:12], "little")
    frame_flags = payload[12:16]
    total_len = frame_len + 0x14
    if total_len > len(payload):
        return None

    width = int.from_bytes(payload[16:18], "little")
    height = int.from_bytes(payload[18:20], "little")
    bitstream = payload[0x14:total_len]
    nal_offset = bitstream.find(b"\x00\x00\x00\x01")
    if nal_offset < 0:
        nal_offset = bitstream.find(b"\x00\x00\x01")

    return {
        "frame_tag": frame_tag,
        "frame_len": frame_len,
        "frame_stamp": frame_stamp,
        "frame_flags": frame_flags,
        "total_len": total_len,
        "width": width,
        "height": height,
        "bitstream": bitstream,
        "nal_offset": nal_offset,
    }


def analyze_h264_annexb_stream(stream: bytes) -> dict:
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

    nal_names = {
        1: "non_idr_slice",
        5: "idr_slice",
        6: "sei",
        7: "sps",
        8: "pps",
        9: "aud",
    }
    starts = find_start_codes(stream)
    counts: dict[str, int] = {}
    nal_units: list[dict] = []
    for idx, (start, sc_len) in enumerate(starts):
        payload_start = start + sc_len
        payload_end = starts[idx + 1][0] if idx + 1 < len(starts) else len(stream)
        if payload_start >= payload_end:
            continue
        nal_header = stream[payload_start]
        nal_type = nal_header & 0x1F
        name = nal_names.get(nal_type, f"type_{nal_type}")
        counts[name] = counts.get(name, 0) + 1
        if len(nal_units) < 16:
            nal_units.append(
                {
                    "offset": start,
                    "start_code_len": sc_len,
                    "nal_type": nal_type,
                    "nal_name": name,
                    "payload_len": payload_end - payload_start,
                    "header_byte": hex(nal_header),
                }
            )
    has_sps = bool(counts.get("sps"))
    has_pps = bool(counts.get("pps"))
    has_idr = bool(counts.get("idr_slice"))
    has_vcl = bool(counts.get("idr_slice") or counts.get("non_idr_slice"))
    return {
        "stream_len": len(stream),
        "start_code_count": len(starts),
        "nal_count": sum(counts.values()),
        "counts": counts,
        "has_sps": has_sps,
        "has_pps": has_pps,
        "has_idr": has_idr,
        "has_vcl": has_vcl,
        "decodable_h264_context": bool(has_sps and has_pps and has_vcl),
        "nal_units": nal_units,
    }


def write_h264_stream(base_name: str, messages: list[dict]) -> dict:
    stream_path = Path(f"{base_name}.h264")
    mp4_path = Path(f"{base_name}.mp4")
    snapshot_path = Path(f"{base_name}.jpg")
    parsed_frames = []
    frame_info = []
    access_units = []

    def flush_group(group: list[dict]) -> None:
        if not group:
            return
        video_frames = [
            frame
            for frame in group
            if frame["frame_tag"] in (0xE0, 0xE1) and frame["nal_offset"] >= 0
        ]
        if not video_frames:
            return
        assembled = b"".join(
            frame["bitstream"][frame["nal_offset"]:]
            for frame in video_frames
        )
        if assembled:
            access_units.append(assembled)

    for msg in messages:
        header = msg.get("header")
        if header is None or header.packet_type != 0xA0:
            continue
        frame = parse_quii_media_frame(msg.get("payload", b""))
        if frame is None:
            continue
        parsed_frames.append(frame)
        frame_info.append({
            "frame_tag": hex(frame["frame_tag"]),
            "frame_len": frame["frame_len"],
            "frame_stamp": frame["frame_stamp"],
            "width": frame["width"],
            "height": frame["height"],
            "nal_offset": frame["nal_offset"],
        })

    current_group = []
    current_stamp = None
    for frame in parsed_frames:
        if current_stamp is None or frame["frame_stamp"] == current_stamp:
            current_group.append(frame)
            current_stamp = frame["frame_stamp"]
            continue
        flush_group(current_group)
        current_group = [frame]
        current_stamp = frame["frame_stamp"]
    flush_group(current_group)

    video_frames = [frame for frame in frame_info if frame["frame_tag"] in ("0xe0", "0xe1")]
    e3_frames = [frame for frame in frame_info if frame["frame_tag"] == "0xe3"]
    avg_video_frame_len = int(sum(frame["frame_len"] for frame in video_frames) / len(video_frames)) if video_frames else 0
    max_video_frame_len = max((frame["frame_len"] for frame in video_frames), default=0)
    keyframe_count = sum(1 for frame in frame_info if frame["frame_tag"] == "0xe1")
    summary = {
        "video_frames": len(video_frames),
        "keyframes": keyframe_count,
        "e3_frames": len(e3_frames),
        "assembled_units": len(access_units),
        "avg_video_frame_len": avg_video_frame_len,
        "max_video_frame_len": max_video_frame_len,
        "suspect_black_stream": bool(video_frames) and max_video_frame_len < 1200,
    }

    if not access_units:
        return {
            "stream_path": str(stream_path.resolve()) if QUII_KEEP_RAW_H264 else "",
            "mp4_path": str(mp4_path.resolve()),
            "snapshot_path": str(snapshot_path.resolve()),
            "frames": frame_info,
            "summary": summary,
            "written": False,
            "mp4": False,
            "snapshot": False,
        }

    stream_bytes = b"".join(access_units)
    stream_path.write_bytes(stream_bytes)
    h264_analysis = analyze_h264_annexb_stream(stream_bytes)
    summary["h264_annexb"] = h264_analysis

    mp4_ok = False
    mp4_error = ""
    ffmpeg_skipped_reason = ""
    if not h264_analysis["decodable_h264_context"]:
        ffmpeg_skipped_reason = "missing_sps_pps_or_vcl"
        mp4_error = ffmpeg_skipped_reason
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
            mp4_ok = mp4_path.exists() and mp4_path.stat().st_size > 0
        except subprocess.CalledProcessError as exc:
            mp4_error = (exc.stderr or str(exc)).strip()
        except Exception as exc:
            mp4_error = str(exc)

    snapshot_ok = False
    snapshot_error = ""
    if QUII_RENDER_SNAPSHOT:
        if ffmpeg_skipped_reason:
            snapshot_error = ffmpeg_skipped_reason
        else:
            snapshot_input = mp4_path if mp4_ok else stream_path
            input_args = ["-i", str(snapshot_input)] if mp4_ok else ["-f", "h264", "-i", str(stream_path)]
            try:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-loglevel",
                        "error",
                        *input_args,
                        "-frames:v",
                        "1",
                        str(snapshot_path),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                snapshot_ok = snapshot_path.exists() and snapshot_path.stat().st_size > 0
            except subprocess.CalledProcessError as exc:
                snapshot_error = (exc.stderr or str(exc)).strip()
            except Exception as exc:
                snapshot_error = str(exc)

    if mp4_ok and not QUII_KEEP_RAW_H264:
        try:
            stream_path.unlink(missing_ok=True)
        except Exception:
            pass

    return {
        "stream_path": str(stream_path.resolve()) if QUII_KEEP_RAW_H264 else "",
        "mp4_path": str(mp4_path.resolve()),
        "snapshot_path": str(snapshot_path.resolve()),
        "frames": frame_info,
        "summary": summary,
        "written": True,
        "mp4": mp4_ok,
        "mp4_error": mp4_error,
        "snapshot": snapshot_ok,
        "snapshot_error": snapshot_error,
        "ffmpeg_skipped_reason": ffmpeg_skipped_reason,
    }


def request_cgi(
    command: str,
    host: str,
    port: int,
    username: str,
    password: str,
    *,
    encrypted: bool,
    nc: str | None = None,
    scheme: str = "http",
    passwordencode: str | None = None,
    debug: bool = False,
):
    if encrypted:
        security = "usernametoken"
        request_password = get_encrypt_password(username, password, nc)
    else:
        security = "username"
        request_password = password

    xml_body = build_request_xml(
        command,
        security,
        username,
        request_password,
        nc=nc,
        passwordencode=passwordencode,
    )
    req = urllib.request.Request(
        f"{scheme}://{host}:{port}/tdkcgi",
        data=xml_body,
        headers={"Content-Type": "application/xml"},
        method="POST",
    )

    context = None
    if scheme == "https":
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, timeout=10, context=context) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        data = exc.read()
        if debug:
            print("HTTP status:", exc.code)
            print("Request XML:")
            print(xml_body.decode("utf-8"))
            print("Raw response:")
            print(data.decode("utf-8", errors="replace"))
        raise
    except Exception:
        if debug:
            print("Request XML:")
            print(xml_body.decode("utf-8"))
        raise

    if debug:
        print("Request XML:")
        print(xml_body.decode("utf-8"))
        print("Raw response:")
        print(data.decode("utf-8", errors="replace"))

    root = ET.fromstring(data)
    body = root.find("./body")
    if body is None:
        raise RuntimeError("response body not found")

    error = (body.findtext("error") or "0").strip()
    return {
        "error": error,
        "raw": data.decode("utf-8", errors="replace"),
    }


def request_streamkey(**kwargs):
    result = request_cgi("get.device.streamkey", **kwargs)
    if result["error"] != "0":
        raise RuntimeError(f"device error: {result['error']}")

    root = ET.fromstring(result["raw"].encode("utf-8"))
    body = root.find("./body")
    content = body.find("content") if body is not None else None
    if content is None:
        raise RuntimeError("content not found")

    return {
        "key": (content.findtext("key") or "").strip(),
        "tdc": (content.findtext("tdc") or "").strip(),
        "synctime": (content.findtext("synctime") or "").strip(),
    }


def userauth_password(value: str) -> str:
    if value and len(value) != 64:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
    return value or ""


def build_userauth_xml(
    command: str,
    content_builder,
    *,
    content_class: str | None = None,
    session_id: str | None = None,
    seq: int = 0,
) -> bytes:
    envelope = ET.Element("envelope")

    content_attrs = {"class": content_class} if content_class else {}
    content = ET.SubElement(envelope, "content", content_attrs)
    content_builder(content)

    header = ET.SubElement(envelope, "header")
    client = ET.SubElement(header, "client")
    ET.SubElement(client, "app").text = str(CLOUD_APP_ID)
    ET.SubElement(client, "id").text = f"00{CLOUD_CLIENT_TYPE}-{CLOUD_APP_ID}-{CLOUD_CLIENT_UUID}"
    ET.SubElement(client, "oem").text = CLOUD_OEM_ID
    ET.SubElement(client, "type").text = str(CLOUD_CLIENT_TYPE)
    ET.SubElement(header, "command").text = command
    ET.SubElement(header, "flag").text = "tdkcloud"
    ET.SubElement(header, "seq").text = str(seq)
    if session_id:
        ET.SubElement(header, "session").text = session_id
    ET.SubElement(header, "user-data")
    ET.SubElement(header, "version").text = CLOUD_AUTH_VERSION

    xml = ET.tostring(envelope, encoding="utf-8", xml_declaration=False)
    return b'<?xml version="1.0" encoding="UTF-8"?>' + xml


def build_cloud_opener():
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(CLOUD_COOKIE_JAR),
        urllib.request.HTTPSHandler(context=context),
    )


def dump_cookie_jar():
    cookies = []
    for cookie in CLOUD_COOKIE_JAR:
        cookies.append(f"{cookie.name}={cookie.value}")
    return cookies


def request_userauth(xml_body: bytes, debug: bool = False):
    headers = {
        "Content-Type": "application/xml",
        "Charset": "utf-8",
        "Accept-Language": "en-US",
        "Accept-Encoding": "gzip, deflate, br",
        "User-Agent": "okhttp/3.12.13",
        "Connection": "close",
    }
    if CLOUD_COOKIE:
        headers["Cookie"] = CLOUD_COOKIE

    req = urllib.request.Request(
        f"{CLOUD_SCHEME}://{CLOUD_HOST}:{CLOUD_PORT}{CLOUD_PATH}",
        data=xml_body,
        headers=headers,
        method="POST",
    )

    opener = build_cloud_opener()

    try:
        with opener.open(req, timeout=15) as resp:
            data = resp.read()
            response_headers = dict(resp.info())
    except urllib.error.HTTPError as exc:
        data = exc.read()
        response_headers = dict(exc.headers.items())
        if debug:
            print("HTTP status:", exc.code)
            print("Request URL:", req.full_url)
            print("Request headers:", dict(req.header_items()))
            print("Cookie jar:", dump_cookie_jar())
            print("Response headers:", response_headers)
            print("Request XML:")
            print(xml_body.decode("utf-8", errors="replace"))
            print("Raw response:")
            print(data.decode("utf-8", errors="replace"))
        raise

    if debug:
        print("Request URL:", req.full_url)
        print("Request headers:", dict(req.header_items()))
        print("Cookie jar:", dump_cookie_jar())
        print("Response headers:", response_headers)
        print("Request XML:")
        print(xml_body.decode("utf-8", errors="replace"))
        print("Raw response:")
        print(data.decode("utf-8", errors="replace"))

    root = ET.fromstring(data)
    return root, data.decode("utf-8", errors="replace")


def login_cloud(account: str, password: str, *, ip_region_id: int = 6, debug: bool = False):
    hashed_password = userauth_password(password)

    def content_builder(content: ET.Element):
        ET.SubElement(content, "account").text = account
        ET.SubElement(content, "auth-code").text = ""
        ET.SubElement(content, "ip-region-id").text = str(ip_region_id)
        ET.SubElement(content, "password").text = hashed_password
        ET.SubElement(content, "auth-type").text = "0"

    xml_body = build_userauth_xml(
        "login",
        content_builder,
        content_class=LOGIN_REQ_CLASS,
        session_id=None,
        seq=CLOUD_LOGIN_SEQ,
    )
    root, raw = request_userauth(xml_body, debug=debug)

    header = root.find("./header")
    if header is None:
        raise RuntimeError("login response header not found")

    result = (header.findtext("result") or "").strip()
    if result and result != "0":
        raise RuntimeError(f"cloud login result: {result}")

    session_id = (header.findtext("./session/id") or header.findtext("session") or "").strip()
    account_id = (root.findtext("./content/account-id") or "").strip()
    token = (root.findtext("./content/token") or "").strip()
    expire = (root.findtext("./content/expire") or "").strip()

    return {
        "session_id": session_id,
        "account_id": account_id,
        "token": token,
        "expire": expire,
        "raw": raw,
    }


def get_device_token(session_id: str, device_id: str, *, is_hs_device=None, debug: bool = False):
    def content_builder(content: ET.Element):
        ET.SubElement(content, "device-id").text = device_id
        if is_hs_device is not None:
            ET.SubElement(content, "is-hs-device").text = str(is_hs_device)

    xml_body = build_userauth_xml(
        "get-device-token",
        content_builder,
        content_class=DEVICE_TOKEN_REQ_CLASS,
        session_id=session_id,
        seq=0,
    )
    root, raw = request_userauth(xml_body, debug=debug)

    header = root.find("./header")
    if header is None:
        raise RuntimeError("device-token response header not found")

    result = (header.findtext("result") or "").strip()
    if result and result != "0":
        raise RuntimeError(f"device-token result: {result}")

    content = root.find("./content")
    if content is None:
        raise RuntimeError("device-token response content not found")

    return {
        "device_id": (content.findtext("deviceid") or content.findtext("device-id") or "").strip(),
        "data_encode_key": (content.findtext("dataEncodeKey") or content.findtext("data-encode-key") or "").strip(),
        "dynamic_password": (content.findtext("dynamicPassword") or content.findtext("dynamic-password") or "").strip(),
        "pwd_expired": (content.findtext("pwdExpired") or content.findtext("password-expired") or "").strip(),
        "transparent_basedata": (content.findtext("transparentBasedata") or content.findtext("transparent-basedata") or "").strip(),
        "auth_code": (content.findtext("authCode") or content.findtext("out-auth-code") or content.findtext("auth-code") or "").strip(),
        "default_out_auth_code": (content.findtext("defaultOutAuthCode") or content.findtext("default-out-auth-code") or "").strip(),
        "raw": raw,
    }


def run_quii_probe(token_result: dict):
    if QUII_USE_FORWARDED_RELAY:
        credential_candidates = [
            {
                "username": "adminapp",
                "password": token_result.get("dynamic_password", ""),
                "label": "adminapp_dynamic_password",
            }
        ]
        combo_candidates = [
            {
                "channel": QUII_RELAY_CHANNEL,
                "stream": QUII_RELAY_STREAM,
                "newcn": QUII_RELAY_NEWCN,
                "path": build_quii_live_path(
                    channel=QUII_RELAY_CHANNEL,
                    stream=QUII_RELAY_STREAM,
                    newcn=QUII_RELAY_NEWCN,
                ),
            }
        ]
        probe_host = QUII_RELAY_HOST
        probe_port = QUII_RELAY_PORT
    else:
        # Keep only combinations that have already reached media packets in prior probes.
        credential_candidates = [
            {
                "username": "adminapp",
                "password": token_result.get("dynamic_password", ""),
                "label": "adminapp_dynamic_password",
            },
            {
                "username": "adminapp2",
                "password": token_result.get("auth_code", ""),
                "label": "adminapp2_auth_code_hash",
            },
            {
                "username": "adminapp2",
                "password": AUTH_CODE,
                "label": "adminapp2_auth_code_raw",
            },
        ]
        combo_candidates = [
            {
                "channel": channel,
                "stream": stream,
                "newcn": newcn,
                "path": build_quii_live_path(channel=channel, stream=stream, newcn=newcn),
            }
            for channel in QUII_CHANNEL_CANDIDATES
            for stream in QUII_STREAM_CANDIDATES
            for newcn in QUII_NEWCN_CANDIDATES
        ]
        probe_host = QUII_HOST
        probe_port = QUII_PORT

    credential_candidates = [c for c in credential_candidates if c["username"] and c["password"]]

    print("\n=== quii_config ===")
    print(
        {
            "host": probe_host,
            "port": probe_port,
            "use_forwarded_relay": QUII_USE_FORWARDED_RELAY,
            "ap": QUII_AP,
            "combo_candidates": combo_candidates,
            "key_len": len(token_result["data_encode_key"]),
            "credential_candidates": [
                {
                    "username": item["username"],
                    "password_len": len(item["password"]),
                    "label": item["label"],
                }
                for item in credential_candidates
            ],
            "example_url": build_quii_live_url(
                credential_candidates[0]["username"],
                credential_candidates[0]["password"],
                probe_host,
                probe_port,
                channel=combo_candidates[0]["channel"],
                stream=combo_candidates[0]["stream"],
            ) if credential_candidates and combo_candidates else "",
            "play_param": 1,
        }
    )

    if not QUII_RUN_PROBE:
        print("SKIPPED: set QUII_RUN_PROBE = True to attempt direct quii TCP probe")
        return

    attempts = []
    compact_summary = []
    for combo in combo_candidates:
        for credential in credential_candidates:
            username = credential["username"]
            password = credential["password"]
            client = QuiiClient(
                probe_host,
                probe_port,
                username,
                password,
                combo["path"],
                token_result["data_encode_key"],
            )
            dump_name = f"quii_probe_ch{combo['channel']}_st{combo['stream']}_nc{int(combo['newcn'])}_{credential['label']}.bin"
            dump_file = Path(dump_name.replace("@", "_"))
            try:
                result = client.probe_live(dump_file=dump_file, num_messages=QUII_NUM_MESSAGES, play_param=1)
                message_summaries = [
                    {
                        "type": msg["header"].packet_type,
                        "payload_size": msg["header"].payload_size,
                        "raw_size": msg["header"].raw_size,
                        "status_b": msg["header"].raw[11],
                        "state_c": msg["header"].raw[12],
                        "flag13": msg["header"].flag13,
                        "flag14": msg["header"].flag14,
                        "flag15": msg["header"].flag15,
                        "flag16": msg["header"].flag16,
                        "flag17": msg["header"].flag17,
                        "payload_preview": msg["payload"][:32].hex(),
                        "media_len32": int.from_bytes(msg["header"].raw[11:15], "little"),
                        "start_code_at": msg["payload"].find(b"\x00\x00\x01"),
                    }
                    if "header" in msg
                    else msg
                    for msg in result["messages"]
                ]
                extracted = None
                if QUII_EXTRACT_STREAM:
                    extracted = write_h264_stream(
                        f"quii_stream_ch{combo['channel']}_st{combo['stream']}_nc{int(combo['newcn'])}_{credential['label']}".replace("@", "_"),
                        result["messages"],
                    )

                attempts.append(
                    {
                        "channel": combo["channel"],
                        "stream": combo["stream"],
                        "username": username,
                        "password_len": len(password),
                        "newcn": combo["newcn"],
                        "credential_label": credential["label"],
                        "setup_status": result["setup_response"]["status"],
                        "setup_crypto_mode": result["setup_response"]["crypto_mode"],
                        "dump_file": result["dump_file"],
                        "messages": message_summaries,
                        "extracted": extracted,
                    }
                )
                compact_summary.append(
                    {
                        "channel": combo["channel"],
                        "stream": combo["stream"],
                        "newcn": combo["newcn"],
                        "credential_label": credential["label"],
                        "setup_status": result["setup_response"]["status"],
                        "crypto_mode": result["setup_response"]["crypto_mode"],
                        "media_packets": sum(1 for msg in result["messages"] if msg.get("header") and msg["header"].packet_type == 0xA0),
                        "summary": extracted["summary"] if extracted else {},
                        "mp4": extracted["mp4"] if extracted else False,
                        "snapshot": extracted["snapshot"] if extracted else False,
                        "mp4_path": extracted["mp4_path"] if extracted else "",
                        "snapshot_path": extracted["snapshot_path"] if extracted else "",
                    }
                )
            except Exception as exc:
                attempts.append(
                    {
                        "channel": combo["channel"],
                        "stream": combo["stream"],
                        "username": username,
                        "password_len": len(password),
                        "credential_label": credential["label"],
                        "error": str(exc),
                    }
                )
                compact_summary.append(
                    {
                        "channel": combo["channel"],
                        "stream": combo["stream"],
                        "credential_label": credential["label"],
                        "error": str(exc),
                    }
                )
            finally:
                client.close()

    compact_summary.sort(
        key=lambda item: (
            0 if item.get("error") else 1,
            item.get("summary", {}).get("max_video_frame_len", 0),
            item.get("summary", {}).get("avg_video_frame_len", 0),
            item.get("summary", {}).get("video_frames", 0),
        ),
        reverse=True,
    )

    print("\n=== quii_summary ===")
    print(compact_summary)
    if QUII_PRINT_FULL_PROBE:
        print("\n=== quii_probe ===")
        print(attempts)

def try_mode(name: str, **kwargs):
    print(f"\n=== {name} ===")
    try:
        secret = request_streamkey(debug=True, **kwargs)
        print("SUCCESS:", secret)
        return True
    except Exception as exc:
        print("FAILED:", exc)
        return False


def probe_mode(name: str, command: str, **kwargs):
    print(f"\n=== {name} ===")
    try:
        result = request_cgi(command=command, debug=True, **kwargs)
        print("RESULT ERROR:", result["error"])
        return True
    except Exception as exc:
        print("FAILED:", exc)
        return False


def run_cloud_flow():
    if not CLOUD_ACCOUNT or not CLOUD_PASSWORD:
        print("\n=== cloud_login ===")
        print("SKIPPED: fill CLOUD_ACCOUNT and CLOUD_PASSWORD first")
        return

    login_result = login_cloud(CLOUD_ACCOUNT, CLOUD_PASSWORD, debug=True)
    print("\n=== cloud_login_parsed ===")
    print({k: v for k, v in login_result.items() if k != "raw"})

    if not login_result["session_id"]:
        print("SKIPPED: session_id is empty")
        return

    if not DEVICE_ID:
        print("\n=== get_device_token ===")
        print("SKIPPED: fill DEVICE_ID first")
        return

    token_result = get_device_token(
        login_result["session_id"],
        DEVICE_ID,
        is_hs_device=IS_HS_DEVICE,
        debug=True,
    )
    print("\n=== get_device_token_parsed ===")
    print({k: v for k, v in token_result.items() if k != "raw"})

    run_quii_probe(token_result)


if __name__ == "__main__":
    if RUN_DEVICE_CGI_PROBES:
        probe_mode(
            "probe_device_status_lan",
            command="get.device.status",
            host=HOST,
            port=80,
            username="adminapp2",
            password=encode_device_password(AUTH_CODE),
            encrypted=False,
            scheme="http",
            passwordencode="1",
        )

        if not try_mode(
            "lan_authcode_http",
            host=HOST,
            port=80,
            username="adminapp2",
            password=encode_device_password(AUTH_CODE),
            encrypted=False,
            scheme="http",
            passwordencode="1",
        ):
            try_mode(
                "lan_authcode_http_no_flag",
                host=HOST,
                port=80,
                username="adminapp2",
                password=encode_device_password(AUTH_CODE),
                encrypted=False,
                scheme="http",
                passwordencode=None,
            )

            try_mode(
                "lan_authcode_http_raw",
                host=HOST,
                port=80,
                username="adminapp2",
                password=AUTH_CODE,
                encrypted=False,
                scheme="http",
                passwordencode=None,
            )

            try_mode(
                "device_plain_http",
                host=HOST,
                port=80,
                username="adminapp",
                password=DEVICE_PASSWORD,
                encrypted=False,
                scheme="http",
                passwordencode=None,
            )

            try_mode(
                "device_plain_http_encoded",
                host=HOST,
                port=80,
                username="adminapp",
                password=DEVICE_PASSWORD,
                encrypted=False,
                scheme="http",
                passwordencode="1",
            )

            try_mode(
                "device_plain_http_hashed",
                host=HOST,
                port=80,
                username="adminapp",
                password=encode_device_password(DEVICE_PASSWORD),
                encrypted=False,
                scheme="http",
                passwordencode="1",
            )

            try_mode(
                "device_token_https",
                host=HOST,
                port=443,
                username="adminapp",
                password=DEVICE_PASSWORD,
                encrypted=True,
                nc=NC,
                scheme="https",
                passwordencode=None,
            )

            try_mode(
                "lan_token_https",
                host=HOST,
                port=443,
                username="adminapp2",
                password=DEVICE_PASSWORD,
                encrypted=True,
                nc=NC,
                scheme="https",
                passwordencode=None,
            )

    if RUN_CLOUD_FLOW:
        run_cloud_flow()
