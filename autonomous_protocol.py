import ipaddress
import base64
import json
import random
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def create_session_flag(server_ip: str, server_port: int, counter: int, device_id: str, rng: random.Random | None = None) -> str:
    """
    Reimplementation of tdkcloud::P2PManager::CreateSessionFlag().

    Observed behavior from libqv-p2p-v2.so:
    - base = "%8.8x%5.5d%5.5d" % (server_ip_as_u32, server_port, counter)
    - base is right-aligned in a 64-byte string
    - the prefix area is filled with random lowercase letters, except randomly
      chosen unique positions where bytes of device_id[4:] are injected
    """
    if len(device_id) < 4:
        raise ValueError("device_id must be at least 4 characters long")

    rng = rng or random.Random()
    ip_value = int(ipaddress.IPv4Address(server_ip))
    base = f"{ip_value:08x}{server_port:05d}{counter:05d}"
    if len(base) > 64:
        raise ValueError("base session flag seed is unexpectedly longer than 64 bytes")

    prefix_len = 64 - len(base)
    injected = device_id[4:]
    if len(injected) > prefix_len:
        raise ValueError("device_id tail does not fit into session flag prefix")

    chars = ["\x00"] * 64
    chars[prefix_len:] = list(base)
    positions = rng.sample(range(prefix_len), len(injected))
    position_map = dict(zip(positions, injected))

    for index in range(prefix_len):
        chars[index] = position_map.get(index, chr(ord("a") + rng.randrange(26)))

    return "".join(chars)


def create_request_session_id(counter16: int, rng: random.Random | None = None) -> int:
    """
    Reimplementation of the request-session-id composition used by P2PManager::AddPort().

    Native code stores:
    - low  16 bits: incrementing counter
    - high 16 bits: random value
    """
    rng = rng or random.Random()
    return ((rng.randrange(0x10000) & 0xFFFF) << 16) | (counter16 & 0xFFFF)


@dataclass
class KcpParams:
    mode: str = "normal"
    sndwnd: int | None = None
    rcvwnd: int | None = None
    nodelay: int | None = None
    interval: int | None = None
    resend: int | None = None
    nc: int | None = None
    rto: int | None = None
    fastresend: int | None = None
    mtu: int | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"mode": self.mode}
        if self.mode == "custom":
            for key in ("sndwnd", "rcvwnd", "nodelay", "interval", "resend", "nc", "rto", "fastresend", "mtu"):
                value = getattr(self, key)
                if value is not None:
                    data[key] = value
        elif self.mtu is not None:
            data["mtu"] = self.mtu
        return data


@dataclass
class P2PConnectRequest:
    client_id: str
    client_type: str | int
    oem: str
    app: str | int
    device_id: str
    session_flag: str
    request_session_id: int
    mon_channel: int
    force_trans: int = 0
    version: str = "v3.2.0"
    command: str = "p2pconnect"
    flag: str = "tdkcloud"
    dev_type: str | None = None
    dev_sub_state: str | None = None
    seq: int | None = None
    session: str | None = None
    userdata: str | None = None
    kcp_params: KcpParams = field(default_factory=KcpParams)

    def to_dict(self) -> dict[str, Any]:
        header: dict[str, Any] = {
            "flag": self.flag,
            "version": self.version,
            "command": self.command,
            "client": {
                "id": self.client_id,
                "type": str(self.client_type),
                "oem": self.oem,
                "app": str(self.app),
            },
        }
        if self.seq is not None:
            header["seq"] = self.seq
        if self.session:
            header["session"] = self.session
        if self.userdata:
            header["userdata"] = self.userdata

        content: dict[str, Any] = {
            "devid": self.device_id,
            "session-flag": self.session_flag,
            "requ-session-id": self.request_session_id,
            "force-trans": self.force_trans,
            "kcpParam": self.kcp_params.to_dict(),
            "devTrans": {
                "monChn": self.mon_channel,
            },
        }
        if self.dev_type:
            content["devType"] = self.dev_type
        if self.dev_sub_state:
            content["devSubState"] = self.dev_sub_state

        return {
            "header": header,
            "content": content,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"), ensure_ascii=False)


@dataclass
class ParsedMqttUrl:
    scheme: str
    host: str
    port: int
    username: str | None
    password: str | None
    default_topic: str
    params: dict[str, str]

    @property
    def pubtopic(self) -> str | None:
        return self.params.get("pubtopic")

    @property
    def mqtt_username(self) -> str | None:
        return self.params.get("username") or self.username

    @property
    def mqtt_password(self) -> str | None:
        return self.params.get("password") or self.password

    @property
    def subtopic(self) -> str | None:
        return self.params.get("subtopic")

    @property
    def subtopic2(self) -> str | None:
        return self.params.get("subtopic2")

    @property
    def willtopic(self) -> str | None:
        return self.params.get("willtopic")

    @property
    def willmsg(self) -> str | None:
        return self.params.get("willmsg")

    @property
    def pubmsg(self) -> str | None:
        return self.params.get("pubmsg")

    @property
    def srcid(self) -> str | None:
        return self.params.get("srcid")

    @property
    def sver(self) -> str | None:
        return self.params.get("sVer")


def parse_mqtt_url(url: str) -> ParsedMqttUrl:
    parsed = urlparse(url)
    params: dict[str, str] = {}
    if parsed.query:
        for item in parsed.query.split("&"):
            if not item:
                continue
            key, _, value = item.partition("=")
            params[unquote(key)] = unquote(value)
    default_topic = parsed.path.lstrip("/").rstrip("/")
    return ParsedMqttUrl(
        scheme=parsed.scheme,
        host=parsed.hostname or "",
        port=parsed.port or 0,
        username=parsed.username,
        password=parsed.password,
        default_topic=default_topic,
        params=params,
    )


def build_ust_register_request(
    *,
    client_id: str,
    client_type: str | int,
    oem: str,
    app: str | int,
    version: str = "v3.2.0",
    flag: str = "tdkcloud",
    userdata: str | None = None,
    seq: str | None = None,
    session: str | None = None,
) -> str:
    """
    Reimplementation of AppClientUst::CreateRegisterMsg() +
    RequMsgHeader::BuildJson().

    Native shape:
    {
      "header": {
        "flag": "tdkcloud",
        "version": "v3.2.0",
        "command": "register",
        ["seq": "..."],
        ["session": "..."],
        ["userdata": "..."],
        "client": {
          "id": "...",
          ["type": "..."],
          ["oem": "..."],
          ["app": "..."]
        }
      }
    }
    """
    header: dict[str, Any] = {
        "flag": flag,
        "version": version,
        "command": "register",
        "client": {
            "id": client_id,
            "type": str(client_type),
            "oem": oem,
            "app": str(app),
        },
    }
    if seq:
        header["seq"] = seq
    if session:
        header["session"] = session
    if userdata:
        header["userdata"] = userdata
    return json.dumps({"header": header}, separators=(",", ":"), ensure_ascii=False)


def build_ust_unregister_request(
    *,
    client_id: str,
    version: str = "v3.2.0",
    flag: str = "tdkcloud",
    userdata: str | None = None,
) -> str:
    header: dict[str, Any] = {
        "flag": flag,
        "version": version,
        "command": "unregister",
        "client": {
            "id": client_id,
        },
    }
    if userdata:
        header["userdata"] = userdata
    return json.dumps({"header": header}, separators=(",", ":"), ensure_ascii=False)


def build_ust_sub_device_state_request(
    *,
    client_id: str,
    client_type: str | int,
    oem: str,
    app: str | int,
    device_ids: list[str],
    version: str = "v3.2.0",
    flag: str = "tdkcloud",
    userdata: str | None = None,
) -> str:
    header: dict[str, Any] = {
        "flag": flag,
        "version": version,
        "command": "sub-device-state",
        "client": {
            "id": client_id,
            "type": str(client_type),
            "oem": oem,
            "app": str(app),
        },
    }
    if userdata:
        header["userdata"] = userdata
    payload = {
        "header": header,
        "content": {
            "devid": device_ids,
        },
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def build_ust_update_netinfo_request(
    *,
    client_id: str,
    client_type: str | int,
    oem: str,
    app: str | int,
    public_ip: str,
    public_udp_port: int,
    local_ips: list[str],
    local_udp_port: int,
    nettype: int = 4,
    netsubtype: int = 0,
    version: str = "v3.2.0",
    flag: str = "tdkcloud",
    userdata: str | None = None,
) -> str:
    header: dict[str, Any] = {
        "flag": flag,
        "version": version,
        "command": "update-netinfo",
        "client": {
            "id": client_id,
            "type": str(client_type),
            "oem": oem,
            "app": str(app),
        },
    }
    if userdata:
        header["userdata"] = userdata
    payload = {
        "header": header,
        "content": {
            "nettype": nettype,
            "netsubtype": netsubtype,
            "pub-ip": public_ip,
            "pub-udpport": public_udp_port,
            "loc-ip": local_ips,
            "loc-udp-port": local_udp_port,
        },
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


P2P_SO_CANDIDATES = (
    Path(r"D:\apk\vhome\vhome_clear\lib\arm64-v8a\libqv-p2p-v2.so"),
    Path(r"D:\apk\vhome\vhome_clear\lib\armeabi-v7a\libqv-p2p-v2.so"),
)
P2P_TABLE1_FILE_OFFSET = 0x6A5C27
P2P_TABLE2_FILE_OFFSET = 0x6A6C27
P2P_TABLE3_FILE_OFFSET = 0x6A7C27
P2P_TABLE_SIZE = 0x1000
UST_AES_IV = b"0" * 16


def _append_zero_to_32(text: str) -> bytes:
    raw = text.encode("utf-8")
    if len(raw) > 32:
        raw = raw[:32]
    if len(raw) < 32:
        raw += b"0" * (32 - len(raw))
    return raw


def _gmult(a: int, b: int) -> int:
    p = 0
    a &= 0xFF
    b &= 0xFF
    for _ in range(8):
        if b & 1:
            p ^= a
        hi = a & 0x80
        a = (a << 1) & 0xFF
        if hi:
            a ^= 0x1B
        b >>= 1
    return p & 0xFF


def _rcon(index: int) -> bytes:
    if index == 0:
        return b"\x00\x00\x00\x00"
    value = 1
    for _ in range(index - 1):
        value = _gmult(value, 2)
    return bytes((value, 0, 0, 0))


def _rot_word(word: bytes) -> bytes:
    return word[1:] + word[:1]


def _sub_word(word: bytes, sbox: bytes) -> bytes:
    return bytes(sbox[b] for b in word)


def _load_p2p_crypto_tables(so_path: str | Path | None = None) -> tuple[bytes, bytes, bytes]:
    candidates = [Path(so_path)] if so_path is not None else list(P2P_SO_CANDIDATES)
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            blob = Path(candidate).read_bytes()
            return (
                blob[P2P_TABLE1_FILE_OFFSET : P2P_TABLE1_FILE_OFFSET + P2P_TABLE_SIZE],
                blob[P2P_TABLE2_FILE_OFFSET : P2P_TABLE2_FILE_OFFSET + P2P_TABLE_SIZE],
                blob[P2P_TABLE3_FILE_OFFSET : P2P_TABLE3_FILE_OFFSET + P2P_TABLE_SIZE],
            )
        except Exception as exc:
            last_error = exc
    raise FileNotFoundError(f"unable to load libqv-p2p-v2.so tables from candidates={candidates!r}; last_error={last_error}")


def generate_ust_seed_and_sbox(srcid: str, *, so_path: str | Path | None = None) -> tuple[bytes, bytes]:
    data1, data2, data3 = _load_p2p_crypto_tables(so_path)

    seed = bytearray(32)
    seed[0] = data2[data1[1]]
    for index in range(1, 32):
        prev = seed[index - 1]
        seed[index] = data2[((prev % 0x10) * prev) & 0xFFF]

    srcid_padded = _append_zero_to_32(srcid)
    for index in range(32):
        seed[index] = (seed[index] + srcid_padded[index]) & 0xFF

    sbox = bytearray(256)
    sbox[0] = data3[seed[0]]
    for index in range(1, 256):
        prev = sbox[index - 1]
        sbox[index] = data3[((prev % 0x10) * prev) & 0xFFF]

    return bytes(seed), bytes(sbox)


def derive_ust_aes_key(srcid: str, *, sver: str = "1.0.0", so_path: str | Path | None = None) -> bytes:
    if sver != "1.0.0":
        raise ValueError(f"unsupported sVer for UST AES key derivation: {sver!r}")

    seed, sbox = generate_ust_seed_and_sbox(srcid, so_path=so_path)
    words = [bytearray(seed[index : index + 4]) for index in range(0, 32, 4)]
    nk = 8
    nb = 4
    nr = 14

    for index in range(nk, nb * (nr + 1)):
        temp = bytes(words[index - 1])
        if index % nk == 0:
            temp = bytes(a ^ b for a, b in zip(_sub_word(_rot_word(temp), sbox), _rcon(index // nk)))
        elif index % nk == 4:
            temp = _sub_word(temp, sbox)
        next_word = bytes(a ^ b for a, b in zip(words[index - nk], temp))
        words.append(bytearray(next_word))

    expanded = b"".join(bytes(word) for word in words)
    return expanded[8:40]


def decrypt_ust_ciphertext(ciphertext_b64: str, *, srcid: str, sver: str = "1.0.0", so_path: str | Path | None = None) -> bytes:
    key = derive_ust_aes_key(srcid, sver=sver, so_path=so_path)
    ciphertext = base64.b64decode(ciphertext_b64)
    if len(ciphertext) % 16 != 0:
        raise ValueError("UST ciphertext is not aligned to AES-CBC block size")
    cipher = Cipher(algorithms.AES(key), modes.CBC(UST_AES_IV))
    decryptor = cipher.decryptor()
    return decryptor.update(ciphertext) + decryptor.finalize()


def decode_ust_mqtt_credentials(
    parsed: ParsedMqttUrl,
    *,
    srcid: str,
    so_path: str | Path | None = None,
) -> tuple[str | None, str | None]:
    username = parsed.mqtt_username
    password = parsed.mqtt_password
    sver = parsed.sver or "1.0.0"

    decoded_user: str | None = username
    decoded_pass: str | None = password

    if username:
        decoded_user = decrypt_ust_ciphertext(username, srcid=srcid, sver=sver, so_path=so_path).rstrip(b"\x00").decode("utf-8", errors="ignore")
    if password:
        decoded_pass = decrypt_ust_ciphertext(password, srcid=srcid, sver=sver, so_path=so_path).rstrip(b"\x00").decode("utf-8", errors="ignore")
    return decoded_user, decoded_pass


@dataclass
class ParsedKcpParams:
    mode: str = "normal"
    sndwnd: int | None = None
    rcvwnd: int | None = None
    nodelay: int | None = None
    interval: int | None = None
    resend: int | None = None
    nc: int | None = None
    rto: int | None = None
    fastresend: int | None = None
    mtu: int | None = None


@dataclass
class P2PConnectResponse:
    result_code: str | None = None
    result_message: str | None = None
    device_id: str | None = None
    session_flag: str | None = None
    response_session_id: int | None = None
    nettype: int | None = None
    netsubtype: int | None = None
    public_ip: str | None = None
    public_udp_port: int | None = None
    local_udp_port: int | None = None
    local_ips: list[str] = field(default_factory=list)
    utd_public_ip: str | None = None
    utd_public_udp_port: int | None = None
    kcp_params: ParsedKcpParams = field(default_factory=ParsedKcpParams)

    @property
    def supports_p2p_test(self) -> bool:
        return bool(self.public_ip and self.public_udp_port)

    @property
    def supports_trans_test(self) -> bool:
        return bool(self.utd_public_ip and self.utd_public_udp_port)


@dataclass
class ParsedSubDeviceState:
    device_ids: list[str] = field(default_factory=list)
    registered: list[str] = field(default_factory=list)
    unregistered: list[str] = field(default_factory=list)
    online: list[str] = field(default_factory=list)
    offline: list[str] = field(default_factory=list)
    usrkey: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class P2PTestTarget:
    kind: str
    host: str
    port: int
    mode: int
    reliable_hint: bool


@dataclass
class ParsedP2PTestResponse:
    result_code: int
    session_flag: str
    address: str
    port: int
    status_code: int
    test_id: int

    @property
    def ok(self) -> bool:
        return self.result_code == 0 and self.status_code == 0


@dataclass
class ParsedP2PTransportFrame:
    marker: int
    packet_type_flag: int
    command: int
    seq: int
    session_flag: str
    remote_ip: str
    remote_port: int
    tail_code: int

    @property
    def is_request(self) -> bool:
        return self.packet_type_flag == 0

    @property
    def is_response(self) -> bool:
        return self.packet_type_flag == 1


@dataclass
class ParsedKcpConnectResponse:
    packet_length: int
    packet_type_flag: int
    command: int
    result_code: int
    payload_length: int
    connect_id: int
    dest_id: int

    @property
    def ok(self) -> bool:
        return self.packet_type_flag == 1 and self.result_code == 0


@dataclass
class ParsedRbDataPacket:
    packet_length: int
    packet_type_flag: int
    command: int
    seq: int
    payload_length: int
    dest_id: int
    src_id: int
    body_length_field: int
    payload: bytes

    @property
    def is_ack(self) -> bool:
        return self.packet_type_flag == 1


@dataclass
class ParsedPacketFrame:
    command: int
    raw: bytes


@dataclass
class ParsedPacketDispatch:
    connect: ParsedKcpConnectResponse | None = None
    disconnect: ParsedPacketFrame | None = None
    data: ParsedRbDataPacket | None = None


@dataclass
class ParsedRbUdpControlPacket:
    marker: int
    word4: int
    word8: int
    local_id: int
    remote_id: int
    status_word: int
    rand16: int
    packet_len16: int


@dataclass
class ParsedRbUdpWrappedPacket:
    marker: int
    word4: int
    word8: int
    local_id: int
    remote_id: int
    status_word: int
    rand16: int
    packet_len16: int
    inner_total_length: int
    tag8: bytes
    inner_packet: bytes


def _maybe_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        return int(text, 10)
    raise TypeError(f"unsupported integer value type: {type(value)!r}")


def parse_p2pconnect_response(data: dict[str, Any] | str) -> P2PConnectResponse:
    """
    Parse the P2P connect response content handled by
    RespMsgContentP2PConnect::ParseJson().

    The native parser accepts the already-selected JSON content object, not the
    full MQTT envelope. This helper accepts either that object directly or a
    larger object containing a nested `content` member.
    """
    if isinstance(data, str):
        data = json.loads(data)

    content = data.get("content", data)
    result = content.get("result") or {}
    kcp_raw = content.get("kcpParam") or {}

    local_ips = content.get("loc-ip") or []
    if not isinstance(local_ips, list):
        local_ips = [local_ips]

    return P2PConnectResponse(
        result_code=str(result.get("code")) if result.get("code") is not None else None,
        result_message=result.get("msg") or result.get("message"),
        device_id=content.get("devid"),
        session_flag=content.get("session-flag"),
        response_session_id=_maybe_int(content.get("resp-session-id")),
        nettype=_maybe_int(content.get("nettype")),
        netsubtype=_maybe_int(content.get("netsubtype")),
        public_ip=content.get("pub-ip"),
        public_udp_port=_maybe_int(content.get("pub-udpport")),
        local_udp_port=_maybe_int(content.get("loc-udpport")),
        local_ips=[str(value) for value in local_ips if value is not None],
        utd_public_ip=content.get("utd-pub-ip"),
        utd_public_udp_port=_maybe_int(content.get("utd-pub-udpport")),
        kcp_params=ParsedKcpParams(
            mode=str(kcp_raw.get("mode", "normal")).replace("nomal", "normal"),
            sndwnd=_maybe_int(kcp_raw.get("sndwnd")),
            rcvwnd=_maybe_int(kcp_raw.get("rcvwnd")),
            nodelay=_maybe_int(kcp_raw.get("nodelay")),
            interval=_maybe_int(kcp_raw.get("interval")),
            resend=_maybe_int(kcp_raw.get("resend")),
            nc=_maybe_int(kcp_raw.get("nc")),
            rto=_maybe_int(kcp_raw.get("rto")),
            fastresend=_maybe_int(kcp_raw.get("fastresend")),
            mtu=_maybe_int(kcp_raw.get("mtu")),
        ),
    )


def parse_sub_device_state_response(data: dict[str, Any] | str) -> ParsedSubDeviceState:
    if isinstance(data, str):
        data = json.loads(data)

    content = data.get("content", data)
    if not isinstance(content, dict):
        raise ValueError("sub-device-state payload does not contain content object")

    state_r = content.get("state-r") or {}
    state_s = content.get("state-s") or {}

    def _as_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value]
        return [str(value)]

    usrkeys = _as_list(state_r.get("usrkey"))
    return ParsedSubDeviceState(
        device_ids=_as_list(content.get("devices")),
        registered=_as_list(state_r.get("register")),
        unregistered=_as_list(state_r.get("unregister")),
        online=_as_list(state_s.get("aonline")),
        offline=_as_list(state_s.get("aoffline")),
        usrkey=usrkeys[0] if usrkeys else None,
        raw=data,
    )


def iter_p2p_test_targets(response: P2PConnectResponse, *, force_trans: int = 0, trans_reliable_hint: bool = False) -> list[P2PTestTarget]:
    """
    Reproduce the decision tree from P2PTest::OnSendTest(),
    OnSendTestP2P(), and OnSendTestTrans().

    Notes:
    - Native app also performs a LAN probe against `loc-ip/loc-udpport` before
      the public/trans probes. Empirically this is required to ever get LAN
      RB-UDP responses on some peers.
    - `nettype` bit 0 suppresses public P2P probing.
    - `nettype` bit 1 suppresses UTD/trans probing.
    """
    targets: list[P2PTestTarget] = []
    nettype = response.nettype or 0

    for candidate in response.local_ips:
        try:
            ip = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if ip.is_private and response.local_udp_port:
            targets.append(
                P2PTestTarget(
                    kind="lan",
                    host=candidate,
                    port=int(response.local_udp_port),
                    mode=0,
                    reliable_hint=True,
                )
            )
            break

    if force_trans == 0 and (nettype & 0x1) == 0 and response.supports_p2p_test:
        targets.append(
            P2PTestTarget(
                kind="p2p",
                host=response.public_ip or "",
                port=int(response.public_udp_port or 0),
                mode=0,
                reliable_hint=False,
            )
        )

    if (nettype & 0x2) == 0 and response.supports_trans_test:
        targets.append(
            P2PTestTarget(
                kind="trans",
                host=response.utd_public_ip or "",
                port=int(response.utd_public_udp_port or 0),
                mode=1,
                reliable_hint=trans_reliable_hint,
            )
        )

    return targets


def build_live_setup_packet() -> bytes:
    packet = bytearray(32)
    packet[0] = 0xA9
    return bytes(packet)


def parse_p2p_test_response(packet: bytes) -> ParsedP2PTestResponse:
    """
    Parse the fields used by P2PTest::OnRespMsg() from a returned KcpLinkPacket.

    Observed offsets:
    - 0x20: int32 result
    - 0x28: NUL-terminated session-flag string
    - 0x70: NUL-terminated address string
    - 0x80: uint16 port
    - 0x82: uint16 status
    - 0x84: uint32 test_id / connection type
    """
    if len(packet) >= 0xA4 and struct.unpack_from("<I", packet, 0x30)[0] == 0x00120002:
        def read_cstr(offset: int, size: int) -> str:
            raw = packet[offset : offset + size]
            return raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")

        packet_type_flag = struct.unpack_from("<H", packet, 0x2E)[0]
        return ParsedP2PTestResponse(
            result_code=0 if packet_type_flag == 1 else 1,
            session_flag=read_cstr(0x44, 0x40),
            address=read_cstr(0x8C, 0x10),
            port=struct.unpack_from("<H", packet, 0x9C)[0],
            status_code=0 if packet_type_flag == 1 else packet_type_flag,
            test_id=struct.unpack_from("<I", packet, 0xA0)[0],
        )

    if len(packet) < 0x88:
        raise ValueError("packet too short for P2P test response")

    def read_cstr(offset: int, size: int) -> str:
        raw = packet[offset : offset + size]
        return raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")

    return ParsedP2PTestResponse(
        result_code=struct.unpack_from("<I", packet, 0x20)[0],
        session_flag=read_cstr(0x28, 0x40),
        address=read_cstr(0x70, 0x10),
        port=struct.unpack_from("<H", packet, 0x80)[0],
        status_code=struct.unpack_from("<H", packet, 0x82)[0],
        test_id=struct.unpack_from("<I", packet, 0x84)[0],
    )


def parse_p2p_transport_frame(packet: bytes) -> ParsedP2PTransportFrame:
    if len(packet) < 0xA4:
        raise ValueError("packet too short for P2P transport frame")
    if struct.unpack_from("<I", packet, 0x30)[0] != 0x00120002:
        raise ValueError("packet is not a P2P transport/test frame")

    def read_cstr(offset: int, size: int) -> str:
        raw = packet[offset : offset + size]
        return raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")

    return ParsedP2PTransportFrame(
        marker=struct.unpack_from("<I", packet, 0x00)[0],
        packet_type_flag=struct.unpack_from("<H", packet, 0x2E)[0],
        command=struct.unpack_from("<I", packet, 0x30)[0],
        seq=struct.unpack_from("<I", packet, 0x38)[0],
        session_flag=read_cstr(0x44, 0x40),
        remote_ip=read_cstr(0x8C, 0x10),
        remote_port=struct.unpack_from("<H", packet, 0x9C)[0],
        tail_code=struct.unpack_from("<I", packet, 0xA0)[0],
    )


def build_p2p_transport_packet(
    *,
    session_flag: str,
    seq: int,
    local_udp_port: int,
    remote_ip: str,
    remote_port: int,
    tail_code: int,
    packet_type_flag: int = 0,
    rand16: int | None = None,
) -> bytes:
    packet = bytearray(0xA4)
    struct.pack_into("<I", packet, 0x00, 0xFFABEFC1)
    struct.pack_into("<H", packet, 0x1A, 0x00A4)
    struct.pack_into("<I", packet, 0x1C, 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x20, 0x88)
    struct.pack_into("<H", packet, 0x2A, (rand16 if rand16 is not None else random.randrange(0x10000)) & 0xFFFF)
    struct.pack_into("<H", packet, 0x2C, 0x0100)
    struct.pack_into("<H", packet, 0x2E, packet_type_flag & 0xFFFF)
    struct.pack_into("<I", packet, 0x30, 0x00120002)
    struct.pack_into("<I", packet, 0x38, seq & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x40, 0x60)

    session_flag_bytes = session_flag.encode("utf-8")
    packet[0x44 : 0x44 + len(session_flag_bytes)] = session_flag_bytes

    struct.pack_into("<H", packet, 0x84, 0)
    struct.pack_into("<H", packet, 0x86, local_udp_port & 0xFFFF)
    struct.pack_into("<H", packet, 0x88, 0)
    struct.pack_into("<H", packet, 0x8A, local_udp_port & 0xFFFF)

    remote_ip_bytes = remote_ip.encode("utf-8")
    packet[0x8C : 0x8C + len(remote_ip_bytes)] = remote_ip_bytes
    struct.pack_into("<H", packet, 0x9C, remote_port & 0xFFFF)
    struct.pack_into("<I", packet, 0xA0, tail_code & 0xFFFFFFFF)
    return bytes(packet)


def build_p2p_active_packet(
    *,
    session_flag: str,
    seq: int,
    local_udp_port: int,
    tail_code: int,
) -> bytes:
    return build_p2p_transport_packet(
        session_flag=session_flag,
        seq=seq,
        local_udp_port=local_udp_port,
        remote_ip="",
        remote_port=0,
        tail_code=tail_code,
        packet_type_flag=0,
    )


def build_p2p_transport_ack(frame: ParsedP2PTransportFrame, *, local_udp_port: int) -> bytes:
    return build_p2p_transport_packet(
        session_flag=frame.session_flag,
        seq=frame.seq,
        local_udp_port=local_udp_port,
        remote_ip=frame.remote_ip,
        remote_port=frame.remote_port,
        tail_code=frame.tail_code,
        packet_type_flag=1,
    )


def build_kcp_conv(app_session: int, response_session_id: int) -> int:
    """
    Reproduce the conv composition from P2PTest::OnRespMsg():
    conv = (app_session << 16) | (response_session_id & 0xffff)
    """
    return ((app_session & 0xFFFF) << 16) | (response_session_id & 0xFFFF)


def build_kcp_connect_packet(*, src_id: int, channel: int, conn_type: int = 0) -> bytes:
    """
    Reimplementation of KcpLinkClient::OnConnect().

    Observed fixed layout:
    - total len: 0x4c
    - command: 0x120101
    - payload len field at 0x24: 0x24
    - connect id / src id at 0x28
    - flags byte at 0x40:
      - bit 3 = conn_type & 1
      - high nibble = channel
    """
    packet = bytearray(0x4C)
    struct.pack_into("<I", packet, 0x00, 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x04, 0x4C)
    struct.pack_into("<H", packet, 0x10, 0x0100)
    struct.pack_into("<H", packet, 0x12, 0x0000)
    struct.pack_into("<I", packet, 0x14, 0x00120101)
    struct.pack_into("<I", packet, 0x24, 0x24)
    struct.pack_into("<I", packet, 0x28, src_id & 0xFFFFFFFF)
    packet[0x40] = ((channel & 0x0F) << 4) | ((conn_type & 0x01) << 3)
    return bytes(packet)


def parse_kcp_connect_response(packet: bytes) -> ParsedKcpConnectResponse:
    """
    Parse the fields consumed by KcpLinkClient::OnP2PRequConnect().

    Observed layouts:
    - legacy assumption:
      - packet_type at 0x12
      - result code at 0x10
      - connect id at 0x18
      - dest id at 0x38
    - live 0x4c packets seen on the wire:
      - packet_type at 0x12
      - status/result low word at 0x10
      - connect id at 0x28
      - destination id in the last dword
    """
    if len(packet) < 0x3C:
        raise ValueError("packet too short for KCP connect response")
    packet_length = struct.unpack_from("<I", packet, 0x04)[0]
    packet_type_flag = struct.unpack_from("<H", packet, 0x12)[0]
    command = struct.unpack_from("<I", packet, 0x14)[0]
    payload_length = struct.unpack_from("<I", packet, 0x24)[0]

    if packet_length >= 0x4C and len(packet) >= packet_length:
        return ParsedKcpConnectResponse(
            packet_length=packet_length,
            packet_type_flag=packet_type_flag,
            command=command,
            result_code=struct.unpack_from("<H", packet, 0x10)[0],
            payload_length=payload_length,
            connect_id=struct.unpack_from("<I", packet, 0x28)[0],
            dest_id=struct.unpack_from("<I", packet, packet_length - 4)[0],
        )

    return ParsedKcpConnectResponse(
        packet_length=packet_length,
        packet_type_flag=packet_type_flag,
        command=command,
        result_code=struct.unpack_from("<I", packet, 0x10)[0],
        payload_length=payload_length,
        connect_id=struct.unpack_from("<I", packet, 0x18)[0],
        dest_id=struct.unpack_from("<I", packet, 0x38)[0],
    )


def build_kcp_disconnect_packet(*, src_id: int, dest_id: int) -> bytes:
    """
    Reimplementation of KcpLinkClient::OnClose().
    """
    packet = bytearray(0x30)
    struct.pack_into("<I", packet, 0x00, 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x04, 0x30)
    struct.pack_into("<H", packet, 0x10, 0x0100)
    struct.pack_into("<H", packet, 0x12, 0x0000)
    struct.pack_into("<I", packet, 0x14, 0x00120102)
    struct.pack_into("<I", packet, 0x24, 0x08)
    struct.pack_into("<I", packet, 0x28, dest_id & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x2C, src_id & 0xFFFFFFFF)
    return bytes(packet)


def build_rb_data_packet(*, payload: bytes, src_id: int, dest_id: int, seq: int) -> bytes:
    """
    Reimplementation of BuildRbRespHead() as used by KcpLinkConn::Send().

    Naming in the binary is confusing: this is the ordinary data packet sent
    over an established logical KCP/RB channel, not only a response helper.
    """
    total_len = 0x38 + len(payload)
    packet = bytearray(total_len)
    struct.pack_into("<I", packet, 0x00, 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x04, total_len)
    struct.pack_into("<H", packet, 0x10, 0x0100)
    struct.pack_into("<H", packet, 0x12, 0x0000)
    struct.pack_into("<I", packet, 0x14, 0x00120103)
    struct.pack_into("<I", packet, 0x18, seq & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x24, total_len - 0x28)
    struct.pack_into("<I", packet, 0x28, dest_id & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x2C, src_id & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x30, (total_len - 0x28) - 0x10)
    packet[0x38:] = payload
    return bytes(packet)


def build_rb_data_ack_packet(*, payload_length: int, seq: int, src_id: int, dest_id: int) -> bytes:
    """
    Reimplementation of BuildRbResp() as used by KcpLinkServer::OnP2PRequData().

    This is the 0x38-byte ACK/control frame sent in response to a received
    data frame. It does not echo the payload, only the metadata.
    """
    packet = bytearray(0x38)
    struct.pack_into("<I", packet, 0x00, 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x04, 0x38)
    struct.pack_into("<H", packet, 0x10, 0x0100)
    struct.pack_into("<H", packet, 0x12, 0x0001)
    struct.pack_into("<I", packet, 0x14, 0x00120103)
    struct.pack_into("<I", packet, 0x18, seq & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x24, 0x10)
    struct.pack_into("<I", packet, 0x28, dest_id & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x2C, src_id & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x30, payload_length & 0xFFFFFFFF)
    return bytes(packet)


def parse_rb_data_packet(packet: bytes) -> ParsedRbDataPacket:
    """
    Parse both ordinary RB data packets and their ACK-only counterparts.

    Fields consumed by the native code:
    - packet_type_flag @ 0x12
    - command          @ 0x14 (0x120103)
    - seq              @ 0x18
    - payload_length   @ 0x24
    - dest_id          @ 0x28
    - src_id           @ 0x2c
    - body_length      @ 0x30
    """
    if len(packet) < 0x38:
        raise ValueError("packet too short for RB data packet")

    packet_length = struct.unpack_from("<I", packet, 0x04)[0]
    payload = packet[0x38:packet_length]
    return ParsedRbDataPacket(
        packet_length=packet_length,
        packet_type_flag=struct.unpack_from("<H", packet, 0x12)[0],
        command=struct.unpack_from("<I", packet, 0x14)[0],
        seq=struct.unpack_from("<I", packet, 0x18)[0],
        payload_length=struct.unpack_from("<I", packet, 0x24)[0],
        dest_id=struct.unpack_from("<I", packet, 0x28)[0],
        src_id=struct.unpack_from("<I", packet, 0x2C)[0],
        body_length_field=struct.unpack_from("<I", packet, 0x30)[0],
        payload=payload,
    )


def iter_kcp_packet_frames(buffer: bytes) -> list[ParsedPacketFrame]:
    """
    Reimplementation of KcpLinkClient::DoRecvData().

    A single KCP delivery may contain multiple concatenated RB packets.
    Each packet starts with:
    - 0x00: 0xffffffff
    - 0x04: total packet length
    - 0x14: command
    """
    frames: list[ParsedPacketFrame] = []
    offset = 0
    total = len(buffer)

    while offset < total:
        if total - offset < 0x10:
            raise ValueError("trailing partial packet header in KCP buffer")
        if struct.unpack_from("<I", buffer, offset)[0] != 0xFFFFFFFF:
            raise ValueError(f"invalid packet marker at offset {offset:#x}")

        packet_len = struct.unpack_from("<I", buffer, offset + 0x04)[0]
        if packet_len == 0:
            raise ValueError(f"zero packet length at offset {offset:#x}")
        if packet_len > 20 * 1024 * 1024:
            raise ValueError(f"unreasonable packet length {packet_len} at offset {offset:#x}")
        end = offset + packet_len
        if end > total:
            raise ValueError("truncated RB packet in KCP buffer")

        raw = buffer[offset:end]
        command = struct.unpack_from("<I", raw, 0x14)[0]
        frames.append(ParsedPacketFrame(command=command, raw=raw))
        offset = end

    return frames


def parse_kcp_packet_frame(frame: ParsedPacketFrame | bytes) -> ParsedPacketDispatch:
    if isinstance(frame, bytes):
        frame = ParsedPacketFrame(command=struct.unpack_from("<I", frame, 0x14)[0], raw=frame)

    if frame.command == 0x120101:
        return ParsedPacketDispatch(connect=parse_kcp_connect_response(frame.raw))
    if frame.command == 0x120102:
        return ParsedPacketDispatch(disconnect=frame)
    if frame.command == 0x120103:
        return ParsedPacketDispatch(data=parse_rb_data_packet(frame.raw))
    raise ValueError(f"unsupported KCP/RB command: {frame.command:#x}")


def parse_rb_udp_control_packet(packet: bytes) -> ParsedRbUdpControlPacket:
    """
    Parse the fixed 28-byte RB-UDP control/ack frames seen after P2P transport.

    Observed layout:
    - 0x00: marker 0xFFABEFC1
    - 0x04: state/command word
    - 0x08: peer state/command word
    - 0x0c: local logical id
    - 0x10: remote logical id
    - 0x14: status/tail word
    - 0x18: random/counter u16
    - 0x1a: packet length u16
    """
    if len(packet) != 28:
        raise ValueError("RB UDP control packet must be exactly 28 bytes")
    marker = struct.unpack_from("<I", packet, 0x00)[0]
    if marker != 0xFFABEFC1:
        raise ValueError("invalid RB UDP control marker")
    return ParsedRbUdpControlPacket(
        marker=marker,
        word4=struct.unpack_from("<I", packet, 0x04)[0],
        word8=struct.unpack_from("<I", packet, 0x08)[0],
        local_id=struct.unpack_from("<I", packet, 0x0C)[0],
        remote_id=struct.unpack_from("<I", packet, 0x10)[0],
        status_word=struct.unpack_from("<I", packet, 0x14)[0],
        rand16=struct.unpack_from("<H", packet, 0x18)[0],
        packet_len16=struct.unpack_from("<H", packet, 0x1A)[0],
    )


def build_rb_udp_control_packet(
    *,
    word4: int,
    word8: int,
    local_id: int,
    remote_id: int,
    status_word: int,
    nonce: int,
) -> bytes:
    packet = bytearray(28)
    struct.pack_into("<I", packet, 0x00, 0xFFABEFC1)
    struct.pack_into("<I", packet, 0x04, word4 & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x08, word8 & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x0C, local_id & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x10, remote_id & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x14, status_word & 0xFFFFFFFF)
    struct.pack_into("<H", packet, 0x1A, len(packet))
    words_sum = sum(struct.unpack_from("<H", packet, off)[0] for off in range(0, 0x18, 2)) & 0xFFFF
    checksum16 = (0xFFFF - words_sum - 0x1F) & 0xFFFF
    struct.pack_into("<H", packet, 0x18, checksum16)
    return bytes(packet)


def parse_rb_udp_wrapped_packet(packet: bytes) -> ParsedRbUdpWrappedPacket:
    """
    Parse RB-UDP packets that wrap an inner logical packet.

    Observed in native traffic:
    - total packet len 104/148 bytes
    - 0x00: outer marker 0xFFABEFC1
    - 0x20: original inner packet full length
    - 0x24..0x2b: 8-byte tag
    - 0x2c..  : inner packet bytes starting from offset 0x10

    The native wrapper therefore reconstructs as:
      wrapped = outer_header(0x24) + tag8 + inner_packet[0x10:]

    Newer captures also show a direct-inner variant:
    - the outer header is still 28 bytes
    - the logical RB packet starts immediately at 0x1c with 0xffffffff
    - there is no extra 8-byte tag before the inner packet
    """
    if len(packet) < 0x1C:
        raise ValueError("packet too short for RB UDP wrapped packet")
    marker = struct.unpack_from("<I", packet, 0x00)[0]
    if marker != 0xFFABEFC1:
        raise ValueError("invalid RB UDP wrapped marker")
    if len(packet) >= 0x24 and struct.unpack_from("<I", packet, 0x1C)[0] == 0xFFFFFFFF:
        inner_total_length = struct.unpack_from("<I", packet, 0x20)[0]
        if inner_total_length < 0x10:
            raise ValueError("inner packet length too small")
        direct_end = 0x1C + inner_total_length
        if direct_end > len(packet):
            raise ValueError("direct wrapped payload size does not match inner length")
        return ParsedRbUdpWrappedPacket(
            marker=marker,
            word4=struct.unpack_from("<I", packet, 0x04)[0],
            word8=struct.unpack_from("<I", packet, 0x08)[0],
            local_id=struct.unpack_from("<I", packet, 0x0C)[0],
            remote_id=struct.unpack_from("<I", packet, 0x10)[0],
            status_word=struct.unpack_from("<I", packet, 0x14)[0],
            rand16=struct.unpack_from("<H", packet, 0x18)[0],
            packet_len16=struct.unpack_from("<H", packet, 0x1A)[0],
            inner_total_length=inner_total_length,
            tag8=b"",
            inner_packet=packet[0x1C:direct_end],
        )
    if len(packet) < 0x24 + 8:
        raise ValueError("packet too short for tagged RB UDP wrapped packet")
    inner_total_length = struct.unpack_from("<I", packet, 0x20)[0]
    if inner_total_length < 0x10:
        raise ValueError("inner packet length too small")
    payload = packet[0x24:]
    if len(payload) != 8 + (inner_total_length - 0x10):
        raise ValueError("wrapped payload size does not match inner length")
    tag8 = payload[:8]
    inner_packet = bytearray(inner_total_length)
    struct.pack_into("<I", inner_packet, 0x00, 0xFFFFFFFF)
    struct.pack_into("<I", inner_packet, 0x04, inner_total_length)
    inner_packet[0x10:] = payload[8:]
    return ParsedRbUdpWrappedPacket(
        marker=marker,
        word4=struct.unpack_from("<I", packet, 0x04)[0],
        word8=struct.unpack_from("<I", packet, 0x08)[0],
        local_id=struct.unpack_from("<I", packet, 0x0C)[0],
        remote_id=struct.unpack_from("<I", packet, 0x10)[0],
        status_word=struct.unpack_from("<I", packet, 0x14)[0],
        rand16=struct.unpack_from("<H", packet, 0x18)[0],
        packet_len16=struct.unpack_from("<H", packet, 0x1A)[0],
        inner_total_length=inner_total_length,
        tag8=tag8,
        inner_packet=bytes(inner_packet),
    )


def build_rb_udp_wrapped_packet(
    inner_packet: bytes,
    *,
    word4: int,
    word8: int,
    local_id: int,
    remote_id: int,
    status_word: int,
    nonce: int,
    tag8: bytes,
) -> bytes:
    """
    Build the RB-UDP wrapper used around logical packets after the P2P stage.

    `tag8` is the 8-byte label observed before the inner packet tail. We keep
    it explicit because the exact semantics are not fully reversed yet.
    """
    if len(tag8) != 8:
        raise ValueError("tag8 must be exactly 8 bytes")
    if len(inner_packet) < 0x10:
        raise ValueError("inner packet too short for RB UDP wrapping")
    total = 0x24 + 8 + (len(inner_packet) - 0x10)
    packet = bytearray(total)
    struct.pack_into("<I", packet, 0x00, 0xFFABEFC1)
    struct.pack_into("<I", packet, 0x04, word4 & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x08, word8 & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x0C, local_id & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x10, remote_id & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x14, status_word & 0xFFFFFFFF)
    struct.pack_into("<H", packet, 0x1A, total & 0xFFFF)
    header = bytearray(packet[:0x1C])
    header[0x18] = 0
    header[0x19] = 0
    checksum16 = 0
    for off in range(0, len(header), 2):
        checksum16 += struct.unpack_from("<H", header, off)[0]
        checksum16 = (checksum16 & 0xFFFF) + (checksum16 >> 16)
    checksum16 = (~checksum16) & 0xFFFF
    struct.pack_into("<H", packet, 0x18, checksum16)
    struct.pack_into("<I", packet, 0x1C, 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x20, len(inner_packet) & 0xFFFFFFFF)
    packet[0x24:0x2C] = tag8
    packet[0x2C:] = inner_packet[0x10:]
    return bytes(packet)


def classify_rb_udp_packet(packet: bytes) -> str:
    if len(packet) == 28:
        return "control28"
    if len(packet) >= 0x24 and struct.unpack_from("<I", packet, 0x00)[0] == 0xFFABEFC1:
        if struct.unpack_from("<I", packet, 0x1C)[0] == 0xFFFFFFFF:
            inner_len = struct.unpack_from("<I", packet, 0x20)[0]
            if len(packet) >= 0x1C + inner_len:
                return "wrapped_direct"
    if len(packet) >= 0x24 + 8 and struct.unpack_from("<I", packet, 0x00)[0] == 0xFFABEFC1:
        inner_len = struct.unpack_from("<I", packet, 0x20)[0]
        if len(packet) == 0x24 + 8 + max(0, inner_len - 0x10):
            return "wrapped"
    return "unknown"


def build_direct_quii_setup_rb(*, src_id: int, dest_id: int, seq: int) -> bytes:
    """
    Wrap the 32-byte QUII live setup packet into a direct RB data frame.
    """
    return build_rb_data_packet(
        payload=build_live_setup_packet(),
        src_id=src_id,
        dest_id=dest_id,
        seq=seq,
    )


def build_direct_quii_play_rb(
    username: str,
    password: str,
    path: str,
    *,
    src_id: int,
    dest_id: int,
    seq: int,
    timestamp_ms: int | None = None,
    ext_len_low: int = 0,
    ext_len_high: int = 0,
    play_param: int = 1,
    stream_flag: int = 0,
    inner: bool = False,
    packet_type: int = 0x01,
    crypto_mode: int = 0,
    sha_mode: int = 1,
    key: bytes | str | None = None,
    encrypt: bool = False,
) -> bytes:
    """
    Build a direct KCP/RB tunnel packet carrying the QUII play/open message.
    """
    _header, _body, payload = build_live_play_packet(
        username,
        password,
        path,
        timestamp_ms=timestamp_ms,
        ext_len_low=ext_len_low,
        ext_len_high=ext_len_high,
        play_param=play_param,
        stream_flag=stream_flag,
        inner=inner,
        packet_type=packet_type,
        crypto_mode=crypto_mode,
        sha_mode=sha_mode,
        key=key,
        encrypt=encrypt,
    )
    return build_rb_data_packet(payload=payload, src_id=src_id, dest_id=dest_id, seq=seq)


def build_direct_quii_play_oem_rb(
    username: str,
    password: str,
    oem: str,
    *,
    src_id: int,
    dest_id: int,
    seq: int,
    timestamp_ms: int | None = None,
    ext_len_low: int = 0,
    ext_len_high: int = 0,
    play_param: int = 1,
    stream_flag: int = 0,
    inner: bool = False,
    packet_type: int = 0x01,
    crypto_mode: int = 0,
    sha_mode: int = 1,
    key: bytes | str | None = None,
    encrypt: bool = False,
) -> bytes:
    """
    Build the app-observed encrypted QUII play packet body:
      username&&dynamic_password\\0OEM\\0
    """
    _header, _body, payload = build_live_play_oem_packet(
        username,
        password,
        oem,
        timestamp_ms=timestamp_ms,
        ext_len_low=ext_len_low,
        ext_len_high=ext_len_high,
        play_param=play_param,
        stream_flag=stream_flag,
        inner=inner,
        packet_type=packet_type,
        crypto_mode=crypto_mode,
        sha_mode=sha_mode,
        key=key,
        encrypt=encrypt,
    )
    return build_rb_data_packet(payload=payload, src_id=src_id, dest_id=dest_id, seq=seq)


def get_sha_len(sha_mode: int = 1) -> int:
    return 32 if sha_mode == 1 else 0


def get_encrypt_mod(crypto_mode: int) -> int:
    return 1 if crypto_mode == 0 else 16


def get_key_len_bits(crypto_mode: int) -> int:
    if crypto_mode == 1:
        return 128
    if crypto_mode == 2:
        return 256
    return 0


def make_ivec() -> bytes:
    return b"0" * 16


def compute_ext_data_len(payload_len: int, *, crypto_mode: int, sha_mode: int = 1, include_sha: bool = True) -> tuple[int, int]:
    total = payload_len
    if include_sha:
        total += get_sha_len(sha_mode)
    padded = total
    if total and crypto_mode != 0:
        block = get_encrypt_mod(crypto_mode)
        padded = ((total + block - 1) // block) * block
    return total, padded


def sha_bytes(data: bytes, sha_mode: int = 1) -> bytes:
    if sha_mode == 1:
        import hashlib

        return hashlib.sha256(data).digest()
    return b""


def aes_cbc_crypt(data: bytes, key: bytes | str, *, crypto_mode: int, decrypt: bool = False) -> bytes:
    if crypto_mode == 0:
        return data

    if isinstance(key, str):
        key = key.encode("utf-8")

    needed = get_key_len_bits(crypto_mode) // 8
    if len(key) < needed:
        raise ValueError(f"key must be at least {needed} bytes for crypto_mode={crypto_mode}")
    key = key[:needed]

    cipher = Cipher(algorithms.AES(key), modes.CBC(make_ivec()))
    if decrypt:
        return cipher.decryptor().update(data) + cipher.decryptor().finalize()
    return cipher.encryptor().update(data) + cipher.encryptor().finalize()


def _build_live_play_packet_from_body(
    body: bytes,
    *,
    timestamp_ms: int | None = None,
    ext_len_low: int = 0,
    ext_len_high: int = 0,
    play_param: int = 1,
    stream_flag: int = 0,
    inner: bool = False,
    packet_type: int = 0x01,
    crypto_mode: int = 0,
    sha_mode: int = 1,
    key: bytes | str | None = None,
    encrypt: bool = False,
) -> tuple[bytes, bytes, bytes]:
    # App packets use Unix time in seconds here, not milliseconds.
    timestamp_ms = int(time.time()) if timestamp_ms is None else timestamp_ms
    raw_len = len(body)
    _ext_len, padded_len = compute_ext_data_len(raw_len, crypto_mode=crypto_mode, sha_mode=sha_mode, include_sha=True)

    header = bytearray(32)
    header[0] = packet_type & 0xFF
    header[1:9] = struct.pack("<Q", timestamp_ms)
    header[9:11] = struct.pack("<H", padded_len)
    header[11:13] = struct.pack("<H", raw_len)
    header[0x0D] = ext_len_low & 0xFF
    header[0x0E] = ext_len_high & 0xFF
    header[0x0F] = play_param & 0xFF
    header[0x10] = stream_flag & 0xFF
    if inner:
        header[0x11] = 1

    trailer = sha_bytes(bytes(header) + body, sha_mode=sha_mode)
    plain = bytes(header) + body + trailer

    if encrypt and crypto_mode != 0:
        if key is None:
            raise ValueError("key is required when encrypt=True and crypto_mode != 0")

        body_plus_sha = body + trailer
        if len(body_plus_sha) < padded_len:
            body_plus_sha += b"\x00" * (padded_len - len(body_plus_sha))
        encrypted_header = aes_cbc_crypt(bytes(header), key, crypto_mode=crypto_mode, decrypt=False)
        encrypted_body = aes_cbc_crypt(body_plus_sha, key, crypto_mode=crypto_mode, decrypt=False)
        return bytes(header), body, encrypted_header + encrypted_body

    return bytes(header), body, plain


def build_live_play_packet(
    username: str,
    password: str,
    path: str,
    *,
    timestamp_ms: int | None = None,
    ext_len_low: int = 0,
    ext_len_high: int = 0,
    play_param: int = 1,
    stream_flag: int = 0,
    inner: bool = False,
    packet_type: int = 0x01,
    crypto_mode: int = 0,
    sha_mode: int = 1,
    key: bytes | str | None = None,
    encrypt: bool = False,
) -> tuple[bytes, bytes, bytes]:
    """
    Reimplementation of CQUIIStreamLive::OnSendPlay / SendFastPlay payload builder.

    Returns:
    - header (plain 32-byte header)
    - body_without_sha
    - full packet (plain or encrypted depending on `encrypt`)

    Unresolved native fields are exposed explicitly:
    - ext_len_low  -> header[0x0d]
    - ext_len_high -> header[0x0e]
    - stream_flag  -> header[0x10]
    """
    body = username.encode("utf-8") + b"&&" + password.encode("utf-8") + b"\x00" + path.encode("utf-8") + b"\x00"
    return _build_live_play_packet_from_body(
        body,
        timestamp_ms=timestamp_ms,
        ext_len_low=ext_len_low,
        ext_len_high=ext_len_high,
        play_param=play_param,
        stream_flag=stream_flag,
        inner=inner,
        packet_type=packet_type,
        crypto_mode=crypto_mode,
        sha_mode=sha_mode,
        key=key,
        encrypt=encrypt,
    )


def build_live_play_oem_packet(
    username: str,
    password: str,
    oem: str,
    *,
    timestamp_ms: int | None = None,
    ext_len_low: int = 0,
    ext_len_high: int = 0,
    play_param: int = 1,
    stream_flag: int = 0,
    inner: bool = False,
    packet_type: int = 0x01,
    crypto_mode: int = 0,
    sha_mode: int = 1,
    key: bytes | str | None = None,
    encrypt: bool = False,
) -> tuple[bytes, bytes, bytes]:
    """
    Build the app-observed live play packet body:
      username&&password\\0OEM\\0
    """
    body = username.encode("utf-8") + b"&&" + password.encode("utf-8") + b"\x00" + oem.encode("utf-8") + b"\x00"
    return _build_live_play_packet_from_body(
        body,
        timestamp_ms=timestamp_ms,
        ext_len_low=ext_len_low,
        ext_len_high=ext_len_high,
        play_param=play_param,
        stream_flag=stream_flag,
        inner=inner,
        packet_type=packet_type,
        crypto_mode=crypto_mode,
        sha_mode=sha_mode,
        key=key,
        encrypt=encrypt,
    )


def build_live_fastplay_packet(
    username: str,
    password: str,
    path: str,
    *,
    timestamp_ms: int | None = None,
    ext_len_low: int = 0,
    ext_len_high: int = 0,
    stream_flag: int = 0,
    inner: bool = False,
    crypto_mode: int = 2,
    sha_mode: int = 1,
    key: bytes | str | None = None,
    encrypt: bool = False,
) -> tuple[bytes, bytes, bytes]:
    return build_live_play_packet(
        username,
        password,
        path,
        timestamp_ms=timestamp_ms,
        ext_len_low=ext_len_low,
        ext_len_high=ext_len_high,
        play_param=1,
        stream_flag=stream_flag,
        inner=inner,
        packet_type=0xAA,
        crypto_mode=crypto_mode,
        sha_mode=sha_mode,
        key=key,
        encrypt=encrypt,
    )


def build_p2p_test_packet(
    *,
    rb_seq: int,
    probe_seq: int,
    session_flag: str,
    response_session_id: int,
    local_udp_port: int,
    target_ip: str,
    target_udp_port: int,
    test_mode: int,
    rand16: int | None = None,
) -> bytes:
    """
    Reimplementation of P2PTest::SendTestMsg() payload builder.

    Native uses the same 0xA4 transport frame shape as later OnRequMsg /
    SendActiveMsg packets, but with filled remote-ip/remote-port/tail fields.
    """
    if len(session_flag.encode("utf-8")) > 0x40:
        raise ValueError("session_flag must fit into 0x40 bytes")
    if len(target_ip.encode("utf-8")) >= 0x10:
        raise ValueError("target_ip must fit into 0x10 bytes including NUL")

    packet = bytearray(0xA4)

    # Minimal observed RB header footprint from native P2PTest::SendTestMsg().
    struct.pack_into("<I", packet, 0x00, 0xFFABEFC1)
    struct.pack_into("<H", packet, 0x1A, 0x00A4)
    struct.pack_into("<I", packet, 0x1C, 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x20, 0x88)
    struct.pack_into("<H", packet, 0x2A, (rand16 if rand16 is not None else random.randrange(0x10000)) & 0xFFFF)
    struct.pack_into("<H", packet, 0x2C, 0x100)
    struct.pack_into("<H", packet, 0x2E, 0x0000)
    struct.pack_into("<I", packet, 0x30, 0x120002)
    struct.pack_into("<I", packet, 0x38, probe_seq & 0xFFFFFFFF)
    struct.pack_into("<I", packet, 0x40, 0x60)

    session_flag_bytes = session_flag.encode("utf-8")
    packet[0x44 : 0x44 + len(session_flag_bytes)] = session_flag_bytes

    struct.pack_into("<H", packet, 0x84, 0)
    struct.pack_into("<H", packet, 0x86, local_udp_port & 0xFFFF)
    struct.pack_into("<H", packet, 0x88, 0)
    struct.pack_into("<H", packet, 0x8A, local_udp_port & 0xFFFF)

    target_ip_bytes = target_ip.encode("utf-8")
    packet[0x8C : 0x8C + len(target_ip_bytes)] = target_ip_bytes

    struct.pack_into("<H", packet, 0x9C, target_udp_port & 0xFFFF)
    struct.pack_into("<I", packet, 0xA0, test_mode & 0xFFFFFFFF)
    return bytes(packet)
