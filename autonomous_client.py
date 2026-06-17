import json
import queue
import random
import socket
import threading
import time
import xml.etree.ElementTree as ET
import ipaddress
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import urllib.request

from kcp.client import KCPClientSync
import paho.mqtt.client as mqtt

from autonomous_protocol import (
    P2PConnectRequest,
    P2PConnectResponse,
    ParsedP2PTransportFrame,
    ParsedP2PTestResponse,
    ParsedRbUdpControlPacket,
    ParsedSubDeviceState,
    ParsedRbUdpWrappedPacket,
    build_p2p_active_packet,
    build_p2p_transport_ack,
    build_rb_udp_control_packet,
    build_rb_udp_wrapped_packet,
    build_ust_register_request,
    build_ust_sub_device_state_request,
    build_ust_unregister_request,
    build_ust_update_netinfo_request,
    build_direct_quii_play_rb,
    build_direct_quii_play_oem_rb,
    build_direct_quii_setup_rb,
    build_kcp_connect_packet,
    build_kcp_conv,
    build_p2p_test_packet,
    build_live_setup_packet,
    build_rb_data_packet,
    create_request_session_id,
    create_session_flag,
    decode_ust_mqtt_credentials,
    iter_kcp_packet_frames,
    iter_p2p_test_targets,
    parse_kcp_packet_frame,
    parse_mqtt_url,
    parse_p2p_transport_frame,
    parse_rb_data_packet,
    parse_rb_udp_control_packet,
    parse_rb_udp_wrapped_packet,
    parse_p2p_test_response,
    parse_sub_device_state_response,
    parse_p2pconnect_response,
)
from constants import CLOUD_ACCOUNT, CLOUD_CLIENT_UUID, CLOUD_PASSWORD, DEVICE_ID
from main import build_quii_live_path, get_device_token, login_cloud


DEFAULT_SERVICE_URL = "https://tantos.qvcloud.net:443"
DEFAULT_OEM = "G0083"
DEFAULT_APP_ID = 4083
DEFAULT_CLIENT_TYPE = 3
DEFAULT_SERVICE_QUERY_PATH = "/mst/query"


@dataclass
class RuntimeCredentials:
    session_id: str
    dynamic_password: str
    data_encode_key: str
    auth_code: str
    transparent_basedata: str
    raw: dict[str, Any]


@dataclass
class ServiceEntry:
    server_type: str
    query_result: int
    region_id: int
    url: str
    uri: str = ""
    param: str = ""


@dataclass
class ServiceQueryResponse:
    seq: int
    timestamp: int
    result: int
    client_region_id: int
    re_maxtime: int
    ip_validity: int
    servers: list[ServiceEntry]

    def find(self, server_type: str) -> ServiceEntry | None:
        for entry in self.servers:
            if entry.server_type == server_type:
                return entry
        return None


@dataclass
class AutonomousConfig:
    device_id: str = DEVICE_ID
    channel: int = 1
    stream: int = 1
    connect_mode: int = -1
    service_url: str = DEFAULT_SERVICE_URL
    oem: str = DEFAULT_OEM
    app_id: int = DEFAULT_APP_ID
    client_type: int = DEFAULT_CLIENT_TYPE
    client_id: str = CLOUD_CLIENT_UUID
    force_trans: int = 0
    ust_address: str = ""
    ust_test_address: str = ""
    ca_path: Path = Path(r"D:\apk\vhome\vhome_clear\assets\ca.pem")
    cert_path: Path = Path(r"D:\apk\vhome\vhome_clear\assets\client.pem")
    key_path: Path = Path(r"D:\apk\vhome\vhome_clear\assets\client.txt")
    ip_region_id: int = 6
    mqtt_timeout: float = 20.0
    prewarm_timeout: float = 12.0
    prewarm_retry_interval: float = 2.0
    preconnect_settle_delay: float = 4.0
    preconnect_mode: bool = True
    udp_timeout: float = 5.0
    connect_timeout: float = 15.0
    p2pconnect_retries: int = 4
    logical_channel: int = 0
    logical_conn_type: int = 0
    logical_src_id_base: int = 0x04000006
    logical_src_id_count: int = 2
    rng_seed: int | None = None
    session_flag_server_ip: str | None = None
    session_flag_server_port: int | None = None
    mqtt_userdata: str | None = None
    mqtt_client_id: str | None = None
    mqtt_will_topic: str | None = None
    mqtt_will_message: str | None = None
    log_peer_diagnostics: bool = True


def _format_peer(peer: tuple[str, int] | None) -> str:
    if peer is None:
        return "None"
    return f"{peer[0]}:{peer[1]}"


def _format_probe_targets(response: P2PConnectResponse) -> list[str]:
    items: list[str] = []
    for target in iter_p2p_test_targets(response, force_trans=0):
        items.append(
            f"{target.kind}:{target.host}:{target.port}:mode={target.mode}:reliable={int(target.reliable_hint)}"
        )
    return items


def _format_logic_peer_candidates(response: P2PConnectResponse) -> list[str]:
    items: list[str] = []
    for candidate in response.local_ips:
        try:
            ip = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if ip.is_private and response.local_udp_port:
            items.append(f"{candidate}:{response.local_udp_port}")
    return items


def _has_probe_targets(response: P2PConnectResponse) -> bool:
    return bool(_format_probe_targets(response))


def ensure_mqtt_runtime(config: AutonomousConfig) -> None:
    if not config.mqtt_userdata:
        rng = random.Random(config.rng_seed if config.rng_seed is not None else int(time.time() * 1000))
        config.mqtt_userdata = str(rng.randrange(10_000_000_000, 99_999_999_999))
    if not config.mqtt_client_id:
        config.mqtt_client_id = f"app_{config.client_id}_{config.mqtt_userdata}_"
    if not config.mqtt_will_topic:
        config.mqtt_will_topic = f"app/ust/json/{config.client_id}"
    if not config.mqtt_will_message:
        config.mqtt_will_message = json.dumps(
            {
                "header": {
                    "flag": "tdkcloud",
                    "version": "v3.2.0",
                    "command": "unregister",
                    "userdata": config.mqtt_userdata,
                    "client": {
                        "id": config.client_id,
                    },
                }
            },
            separators=(",", ":"),
            ensure_ascii=False,
        )


def reset_mqtt_runtime(config: AutonomousConfig) -> None:
    config.mqtt_userdata = None
    config.mqtt_client_id = None
    config.mqtt_will_topic = None
    config.mqtt_will_message = None


def discover_local_ips() -> list[str]:
    """
    Report only the primary routed IPv4 address when possible.

    The Android app appears to advertise a single LAN/Wi‑Fi address to UST.
    Sending every host-side adapter (VPN, WSL, Hyper-V, etc.) makes the peer
    choose the wrong local path much more often.
    """
    primary_ip: str | None = None
    discovered: list[str] = []

    probe: socket.socket | None = None
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))
        ip = probe.getsockname()[0]
        if ip and not ip.startswith("127."):
            primary_ip = ip
    except OSError:
        pass
    finally:
        if probe is not None:
            try:
                probe.close()
            except Exception:
                pass

    try:
        host_name = socket.gethostname()
        for _family, _type, _proto, _canon, sockaddr in socket.getaddrinfo(host_name, None, socket.AF_INET):
            ip = sockaddr[0]
            if not ip or ip.startswith("127."):
                continue
            if ip not in discovered:
                discovered.append(ip)
    except OSError:
        pass

    if primary_ip:
        return [primary_ip]

    return discovered or ["127.0.0.1"]


def discover_public_ip(timeout: float = 5.0) -> str:
    candidates = (
        "https://api.ipify.org",
        "https://ipv4.icanhazip.com",
    )
    for url in candidates:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                value = resp.read().decode("utf-8", errors="ignore").strip()
            socket.inet_aton(value)
            return value
        except Exception:
            continue
    return "0.0.0.0"


def make_dualstack_udp_socket() -> socket.socket:
    try:
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        except OSError:
            pass
        sock.bind(("::", 0))
        return sock
    except OSError:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", 0))
        return sock


def udp_target_tuple(sock: socket.socket, host: str, port: int):
    if sock.family == socket.AF_INET6:
        return (f"::ffff:{host}", port, 0, 0)
    return (host, port)


def is_private_ipv4(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private


def to_signed_i32(value: int) -> int:
    value &= 0xFFFFFFFF
    if value >= 0x80000000:
        return value - 0x100000000
    return value


def query_service_addresses(
    config: AutonomousConfig,
    *,
    seq: int = 1,
    server_types: tuple[str, ...] = ("p2papp", "natcheck", "appinfo"),
) -> ServiceQueryResponse:
    import ssl

    service_url = config.service_url.rstrip("/")
    request_url = f"{service_url}{DEFAULT_SERVICE_QUERY_PATH}"
    xml_body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<envelope><header>"
        "<flag>tdkcloud</flag>"
        "<command>query-hlrv2</command>"
        f"<seq>{seq}</seq>"
        "</header><content>"
        f"<server-type>{','.join(server_types)}</server-type>"
        f"<oem>{config.oem}</oem>"
        "<devid></devid>"
        "<public-ip></public-ip>"
        f"<client-id>{config.client_id}</client-id>"
        f"<regionid>{config.ip_region_id}</regionid>"
        "<version>4456</version>"
        "</content></envelope>"
    ).encode("utf-8")

    ctx = ssl.create_default_context(cafile=str(config.ca_path))
    ctx.check_hostname = False
    ctx.load_cert_chain(certfile=str(config.cert_path), keyfile=str(config.key_path))
    req = urllib.request.Request(
        request_url,
        data=xml_body,
        method="GET",
        headers={
            "Content-Type": "application/xml;charset=utf-8",
            "Host": urlparse(config.service_url).hostname or "",
        },
    )
    with urllib.request.urlopen(req, context=ctx, timeout=config.connect_timeout) as resp:
        xml_text = resp.read().decode("utf-8", errors="ignore")

    root = ET.fromstring(xml_text)
    header = root.find("header")
    content = root.find("content")
    if header is None or content is None:
        raise RuntimeError(f"unexpected query-hlrv2 response: {xml_text[:400]}")

    servers: list[ServiceEntry] = []
    for server in content.findall("server"):
        servers.append(
            ServiceEntry(
                server_type=(server.findtext("server-type") or "").strip(),
                query_result=int(server.findtext("query-result") or "0"),
                region_id=int(server.findtext("regionid") or "0"),
                url=(server.findtext("url") or "").strip(),
                uri=(server.findtext("uri") or "").strip(),
                param=(server.findtext("param") or "").strip(),
            )
        )

    return ServiceQueryResponse(
        seq=int(header.findtext("seq") or "0"),
        timestamp=int(header.findtext("timestamp") or "0"),
        result=int(header.findtext("result") or "-1"),
        client_region_id=int(content.findtext("client-regionid") or "0"),
        re_maxtime=int(content.findtext("re-maxtime") or "0"),
        ip_validity=int(content.findtext("ip-validity") or "0"),
        servers=servers,
    )


def fetch_runtime_credentials(device_id: str = DEVICE_ID, *, ip_region_id: int = 6) -> RuntimeCredentials:
    login = login_cloud(CLOUD_ACCOUNT, CLOUD_PASSWORD, ip_region_id=ip_region_id, debug=False)
    token = get_device_token(login["session_id"], device_id, debug=False)
    return RuntimeCredentials(
        session_id=login["session_id"],
        dynamic_password=token["dynamic_password"],
        data_encode_key=token["data_encode_key"],
        auth_code=token["auth_code"],
        transparent_basedata=token["transparent_basedata"],
        raw={"login": login, "token": token},
    )


def populate_discovered_services(config: AutonomousConfig) -> ServiceQueryResponse:
    response = query_service_addresses(config)
    p2papp = response.find("p2papp")
    natcheck = response.find("natcheck")
    if p2papp is None or not p2papp.url:
        raise RuntimeError("query-hlrv2 did not return p2papp")
    if natcheck is None or not natcheck.url:
        raise RuntimeError("query-hlrv2 did not return natcheck")

    config.ust_address = f"{p2papp.url}{p2papp.uri}/?{p2papp.param}" if p2papp.param else f"{p2papp.url}{p2papp.uri}"
    config.ust_test_address = natcheck.url

    parsed = urlparse(p2papp.url)
    if not config.session_flag_server_ip and parsed.hostname:
        config.session_flag_server_ip = socket.gethostbyname(parsed.hostname)
    if config.session_flag_server_port is None:
        config.session_flag_server_port = parsed.port or 0
    return response


class MqttP2PBootstrap:
    def __init__(self, config: AutonomousConfig):
        self.config = config
        ensure_mqtt_runtime(self.config)
        self.parsed = parse_mqtt_url(config.ust_address)
        self._connected = threading.Event()
        self._messages: "queue.Queue[dict[str, Any]]" = queue.Queue()
        self._all_messages: "queue.Queue[tuple[str, dict[str, Any]]]" = queue.Queue()
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.config.mqtt_client_id or "",
        )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            return
        topics = [
            f"{self.config.client_id}/ust/json",
            self.parsed.subtopic,
            self.parsed.subtopic2,
        ]
        seen: set[str] = set()
        for topic in topics:
            if topic and topic not in seen:
                client.subscribe(topic)
                seen.add(topic)
        self._connected.set()

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        self._connected.clear()

    def _on_message(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode("utf-8", errors="ignore"))
        except Exception:
            return
        self._all_messages.put((message.topic, payload))
        self._messages.put(payload)

    def connect(self):
        self._client.tls_set(
            ca_certs=str(self.config.ca_path),
            certfile=str(self.config.cert_path),
            keyfile=str(self.config.key_path),
        )
        self._client.tls_insecure_set(True)
        if self.config.mqtt_will_topic and self.config.mqtt_will_message:
            self._client.will_set(self.config.mqtt_will_topic, self.config.mqtt_will_message, qos=0, retain=False)
        mqtt_username, mqtt_password = decode_ust_mqtt_credentials(self.parsed, srcid=self.config.client_id)
        if mqtt_username or mqtt_password:
            self._client.username_pw_set(mqtt_username, mqtt_password)
        self._client.connect(self.parsed.host, self.parsed.port, keepalive=30)
        self._client.loop_start()
        if not self._connected.wait(self.config.mqtt_timeout):
            raise TimeoutError("MQTT connect timeout")

    def publish_register(self):
        topic = f"app/ust/json/{self.config.client_id}"
        payload = build_ust_register_request(
            client_id=self.config.client_id,
            client_type=self.config.client_type,
            oem=self.config.oem,
            app=self.config.app_id,
            userdata=self.config.mqtt_userdata,
        )
        self._client.publish(topic, payload.encode("utf-8"), qos=0)

    def publish_unregister(self):
        topic = f"app/ust/json/{self.config.client_id}"
        payload = build_ust_unregister_request(client_id=self.config.client_id)
        self._client.publish(topic, payload.encode("utf-8"), qos=0)

    def publish_sub_device_state(self):
        topic = f"app/ust/json/{self.config.client_id}"
        payload = build_ust_sub_device_state_request(
            client_id=self.config.client_id,
            client_type=self.config.client_type,
            oem=self.config.oem,
            app=self.config.app_id,
            device_ids=[self.config.device_id],
            userdata=self.config.mqtt_userdata,
        )
        self._client.publish(topic, payload.encode("utf-8"), qos=0)

    def wait_for_command(self, command: str, timeout: float) -> tuple[str, dict[str, Any]]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            remaining = max(0.1, deadline - time.time())
            try:
                topic, payload = self._all_messages.get(timeout=remaining)
            except queue.Empty:
                continue
            header = payload.get("header") or {}
            if header.get("command") == command:
                return topic, payload
        raise TimeoutError(f"timed out waiting for MQTT command={command!r}")

    def wait_for_sub_device_state(self, timeout: float) -> ParsedSubDeviceState:
        _topic, payload = self.wait_for_command("sub-device-state", timeout)
        return parse_sub_device_state_response(payload)

    def wait_for_device_online(
        self,
        device_id: str,
        *,
        timeout: float,
        retry_interval: float,
    ) -> ParsedSubDeviceState:
        deadline = time.time() + timeout
        next_retry_at = 0.0
        latest: ParsedSubDeviceState | None = None
        while time.time() < deadline:
            now = time.time()
            if now >= next_retry_at:
                self.publish_sub_device_state()
                next_retry_at = now + retry_interval
            remaining = min(max(0.1, deadline - now), retry_interval)
            try:
                state = self.wait_for_sub_device_state(remaining)
            except TimeoutError:
                continue
            latest = state
            if device_id in state.online:
                return state
        if latest is None:
            raise TimeoutError("timed out waiting for sub-device-state response")
        raise TimeoutError(f"device did not transition to online state; offline={latest.offline!r} online={latest.online!r}")

    def collect_messages(self, duration: float) -> list[tuple[str, dict[str, Any]]]:
        deadline = time.time() + duration
        out: list[tuple[str, dict[str, Any]]] = []
        while time.time() < deadline:
            remaining = max(0.05, deadline - time.time())
            try:
                out.append(self._all_messages.get(timeout=remaining))
            except queue.Empty:
                break
        return out

    def close(self):
        try:
            self._client.loop_stop()
        finally:
            self._client.disconnect()

    def publish_p2pconnect(self, request: P2PConnectRequest):
        topic = f"app/ust/json/{self.config.client_id}"
        self._client.publish(topic, request.to_json().encode("utf-8"), qos=0)

    def publish_update_netinfo(self, *, public_ip: str, public_udp_port: int, local_ips: list[str], local_udp_port: int):
        topic = f"app/ust/json/{self.config.client_id}"
        payload = build_ust_update_netinfo_request(
            client_id=self.config.client_id,
            client_type=self.config.client_type,
            oem=self.config.oem,
            app=self.config.app_id,
            public_ip=public_ip,
            public_udp_port=public_udp_port,
            local_ips=local_ips,
            local_udp_port=local_udp_port,
            userdata=self.config.mqtt_userdata,
        )
        self._client.publish(topic, payload.encode("utf-8"), qos=0)

    def wait_p2pconnect_response(self, session_flag: str, timeout: float) -> P2PConnectResponse:
        deadline = time.time() + timeout
        while time.time() < deadline:
            remaining = max(0.1, deadline - time.time())
            try:
                payload = self._messages.get(timeout=remaining)
            except queue.Empty:
                continue
            try:
                parsed = parse_p2pconnect_response(payload)
            except Exception:
                continue
            if parsed.session_flag == session_flag or parsed.device_id == self.config.device_id:
                return parsed
        raise TimeoutError("timed out waiting for p2pconnect response")


def run_udp_probe(
    *,
    sock: socket.socket,
    response: P2PConnectResponse,
    request_session_id: int,
    target_session_flag: str,
    ust_test_address: str,
    timeout: float,
    rng: random.Random,
    attempts_per_target: int = 3,
) -> ParsedP2PTestResponse:
    targets = iter_p2p_test_targets(response, force_trans=0)
    if not targets:
        raise RuntimeError("no p2p test targets in response")

    probe_seq_by_kind = {
        "lan": 0,
        "p2p": 1,
        "trans": 2,
    }
    local_udp_port = sock.getsockname()[1]
    sock.settimeout(timeout)
    best_response: ParsedP2PTestResponse | None = None
    best_rank = -1

    def rank_response(parsed: ParsedP2PTestResponse) -> int:
        try:
            ip = ipaddress.ip_address(parsed.address)
        except ValueError:
            return 0
        if ip.is_private:
            return 3
        if ip.is_loopback:
            return 2
        return 1

    for target in targets:
        print(
            f"[UDPProbe] target kind={target.kind} host={target.host}:{target.port} "
            f"mode={target.mode} local_udp_port={local_udp_port}"
        )
        for _attempt in range(attempts_per_target):
            packet = build_p2p_test_packet(
                rb_seq=0,
                probe_seq=probe_seq_by_kind.get(target.kind, 0),
                session_flag=target_session_flag,
                response_session_id=response.response_session_id or 0,
                local_udp_port=local_udp_port,
                target_ip=target.host,
                target_udp_port=target.port,
                test_mode=target.mode,
            )
            sock.sendto(packet, udp_target_tuple(sock, target.host, target.port))
            try:
                data, _addr = sock.recvfrom(4096)
            except TimeoutError:
                continue
            parsed = parse_p2p_test_response(data)
            print(
                f"[UDPProbe] response kind={target.kind} from={parsed.address}:{parsed.port} "
                f"result={parsed.result_code} status={parsed.status_code} test_id={parsed.test_id}"
            )
            if parsed.ok:
                rank = rank_response(parsed)
                if best_response is None or rank > best_rank:
                    best_response = parsed
                    best_rank = rank
                if rank >= 3:
                    return parsed
                break
    if best_response is None:
        raise TimeoutError("no successful UDP P2P test response")
    return best_response


def run_p2p_active_handshake(
    *,
    sock: socket.socket,
    session_flag: str,
    timeout: float,
    rng: random.Random,
    peer_hint: tuple[str, int] | None = None,
) -> tuple[tuple[str, int], list[ParsedP2PTransportFrame]]:
    local_udp_port = sock.getsockname()[1]
    sock.settimeout(min(timeout, 0.5))
    seen_requests: list[ParsedP2PTransportFrame] = []
    peer: tuple[str, int] | None = None
    deadline = time.time() + timeout
    active_sent = False

    def send_active(peer_addr: tuple[str, int]) -> None:
        nonlocal active_sent
        for tail_code in (200, 102):
            active = build_p2p_active_packet(
                session_flag=session_flag,
                seq=rng.randrange(0x100000000),
                local_udp_port=local_udp_port,
                tail_code=tail_code,
            )
            sock.sendto(active, udp_target_tuple(sock, peer_addr[0], peer_addr[1]))
        active_sent = True

    while time.time() < deadline:
        if not active_sent and peer_hint is not None and time.time() + 0.5 >= deadline:
            send_active(peer_hint)
        try:
            data, _addr = sock.recvfrom(4096)
        except TimeoutError:
            if not active_sent and peer_hint is not None:
                send_active(peer_hint)
            continue
        try:
            frame = parse_p2p_transport_frame(data)
        except Exception:
            continue
        if frame.session_flag != session_flag:
            continue
        if frame.is_request and frame.remote_ip and frame.remote_port:
            seen_requests.append(frame)
            peer = (frame.remote_ip, frame.remote_port)
            ack = build_p2p_transport_ack(frame, local_udp_port=local_udp_port)
            sock.sendto(ack, udp_target_tuple(sock, frame.remote_ip, frame.remote_port))
            if not active_sent:
                send_active(peer)
            if len(seen_requests) >= 2:
                break

    if peer is None and peer_hint is not None:
        peer = peer_hint
        if not active_sent:
            send_active(peer_hint)

    if peer is None:
        raise TimeoutError("no inbound P2P transport request frames after probe")

    return peer, seen_requests


def select_preferred_logic_peer(response: P2PConnectResponse, fallback_peer: tuple[str, int]) -> tuple[str, int]:
    for candidate in response.local_ips:
        try:
            ip = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if ip.is_private and response.local_udp_port:
            return candidate, response.local_udp_port
    return fallback_peer


def describe_logic_peer_selection(
    response: P2PConnectResponse,
    fallback_peer: tuple[str, int],
) -> dict[str, Any]:
    candidates = _format_logic_peer_candidates(response)
    selected = select_preferred_logic_peer(response, fallback_peer)
    return {
        "fallback_peer": _format_peer(fallback_peer),
        "candidate_logic_peers": candidates,
        "selected_logic_peer": _format_peer(selected),
        "selected_from_response_local_ip": bool(candidates and selected != fallback_peer),
    }


class RbUdpQuiiTunnel:
    CONNECT_TAG = b"ion::Ope"
    DATA_TAG = b"ad()  st"
    CONTROL_BOOTSTRAP_WORD4 = 0x00000000
    CONTROL_BOOTSTRAP_STATUS = 0xFFFF4100
    CONTROL_ESTABLISHED_STATUS = 0xFFFF0900
    CONTROL_SYN_ACK_STATUS = 0xFFFF4900
    CONTROL_FLOW_STATUS = 0xFFFF0D00
    CONTROL_PROGRESS_STATUS = 0xFFB40900
    CONTROL_POST_CONNECT_STATUS = 0xFFA80900
    CONTROL_POST_CONNECT_ACK_STATUS = 0xFF700900
    CONTROL_POST_SETUP_STATUS = 0xFED80900
    CONTROL_POST_SETUP_ACK_STATUS = 0xFEB00900
    CONTROL_STREAM_READY_STATUS = 0xFF480900
    CONTROL_STREAM_READY_ACK_STATUS = 0xFF100900
    CONTROL_PLAY_SYNC_STATUS = 0xFF780900
    CONTROL_PLAY_LATE_STATUS = 0xFF880900
    CONTROL_PLAY_SYNC_ACK_STATUS = 0xFA740900
    CONTROL_PLAY_SYNC_STAGE2_STATUS = 0xFB540900
    CONTROL_PLAY_SYNC_STAGE3_STATUS = 0xFAD40900
    CONTROL_PLAY_SYNC_STAGE4_STATUS = 0xFE0D0900
    CONTROL_PLAY_SYNC_STAGE5_STATUS = 0xFC0C0900
    CONTROL_PLAY_SYNC_STAGE6_STATUS = 0xFB7F0900
    CONTROL_PLAY_ESTABLISHED_ACK_STATUS = 0xFB9E0900
    CONTROL_FRAGMENT_ACK_STATUS = CONTROL_ESTABLISHED_STATUS
    CONTROL_PLAY_SYNC_STEP = 0x0000058C
    CONTROL_PLAY_SYNC_LOCAL_BIAS = 0x00000140
    CONTROL_PLAY_SYNC_STAGE2_LOCAL_DELTA = 0x00000088
    CONTROL_PLAY_SYNC_STAGE2_REMOTE_BIAS = -0x000000F2
    CONTROL_PLAY_SYNC_STAGE3_REMOTE_BIAS = -0x00000152
    CONTROL_PLAY_SYNC_STAGE4_LOCAL_DELTA = 0x00000088
    CONTROL_PLAY_SYNC_STAGE4_REMOTE_BIAS = 0x000000A1
    CONTROL_PLAY_SYNC_STAGE5_REMOTE_BIAS = -0x000000F7
    CONTROL_PLAY_SYNC_STAGE6_REMOTE_BIAS = -0x00000202
    CONTROL_PLAY_PROBE_INNER_DEST = 0x0B030000
    CONTROL_PLAY_PROBE_TAG = bytes.fromhex("0000803f0050c3c7")
    QUII_PLAY_TAGS = (
        bytes.fromhex("61006e0064007200"),
        bytes.fromhex("0100000000000000"),
    )
    CONTROL_PLAY_PROBE2_PAYLOAD = bytes.fromhex(
        "c92a42d0f7ae17f0e7452a46ecfe5c4bc34b116aea1895dea5faec8f5a051f12"
        "628d07bf32b0020b7bc3fdee22102946aff8e68130346b50e4e7ce77f85693a2"
        "66aeb42f1bfc291abe335ac2254602be"
    )
    CONTROL_PLAY_PROBE3_PAYLOAD = bytes.fromhex(
        "939cd332393f73adee029583c588f74b17a6d27bb938de0c904c2a9a4499830c"
        "cf41af8852573ff6841eb9e753bbe64e55a11539403019424d80b692aaf030d1"
        "d0148a96a307f1a1c34ab4722c9b4303"
    )
    CONTROL_PLAY_PROBE4_PAYLOAD = bytes.fromhex(
        "900ed22985e6500a6f60b4670871d7fdcded3931d7cfcca249494621adf3fba4"
        "e795166764cac338b143da5d0749726952aacd7f96452f0e5fd5c429c9ca1065"
        "64340dca828431e2a6e3cf30b3c88fe5"
    )
    WRAPPED_STATUS = 0x00001900
    BOOTSTRAP_LOCAL_IDS = (0x00000000, 0x00000000)
    BOOTSTRAP_REMOTE_ID = 0x00000000

    def __init__(
        self,
        config: AutonomousConfig,
        response: P2PConnectResponse,
        test_response: ParsedP2PTestResponse,
        request_session_id: int,
        udp_sock: socket.socket | None = None,
        peer_addr: tuple[str, int] | None = None,
        transport_peer_addr: tuple[str, int] | None = None,
        p2p_session_flag: str | None = None,
    ):
        self.config = config
        self.response = response
        self.test_response = test_response
        self.request_session_id = request_session_id
        self.src_ids = [
            (config.logical_src_id_base + i) & 0xFFFFFFFF
            for i in range(max(1, int(config.logical_src_id_count)))
        ]
        self.src_id = self.src_ids[0]
        self.dest_id: int | None = None
        self.dest_ids: dict[int, int] = {}
        bootstrap_word8_values = [0x01000000, 0x02000001]
        while len(bootstrap_word8_values) < len(self.src_ids):
            idx = len(bootstrap_word8_values)
            bootstrap_word8_values.append(((idx + 1) << 24) | idx)
        bootstrap_rand_seed = random.randrange(1, 0x10000)
        self._lane_states: list[dict[str, int | bool]] = []
        for idx, src_id in enumerate(self.src_ids):
            bootstrap_local_id = self.BOOTSTRAP_LOCAL_IDS[min(idx, len(self.BOOTSTRAP_LOCAL_IDS) - 1)]
            lane_seed = (bootstrap_rand_seed - (idx * 0x0101)) & 0xFFFF
            if lane_seed == 0:
                lane_seed = 1
            self._lane_states.append(
                {
                    "src_id": src_id,
                    "bootstrap_word4": self.CONTROL_BOOTSTRAP_WORD4,
                    "bootstrap_word8": bootstrap_word8_values[idx],
                    "bootstrap_local_id": bootstrap_local_id,
                    "bootstrap_remote_id": self.BOOTSTRAP_REMOTE_ID,
                    "word4": 0,
                    "word8": 0,
                    "peer_word4": 0,
                    "peer_word8": 0,
                    "local_id": 0,
                    "remote_id": 0,
                    "nonce": lane_seed,
                    "connect_sent": False,
                    "setup_probe_sent": False,
                    "post_play_established_sent": False,
                    "play_sync_active": False,
                    "play_sync_local_id": 0,
                    "play_sync_counter": 0,
                    "play_sync_remaining": 0,
                    "play_probe_stage": 0,
                    "play_sync_sent_count": 0,
                    "play_sync_remote_bias": 0,
                    "play_word_refresh_sent": False,
                    "play_transport_refresh_sent": False,
                    "play_transport_refresh2_sent": False,
                    "play_word_refresh2_sent": False,
                    "progress_sent": False,
                    "flow_sent": False,
                    "established_sent": False,
                    "syn_ack_received": False,
                    "peer_logic_id": 0,
                    "quii_setup_acked": False,
                }
            )
        self._connected = threading.Event()
        self._quii_ready = threading.Event()
        self._quii_setup_acked = threading.Event()
        self._quii_play_sent = threading.Event()
        self._stop = threading.Event()
        self._data: "queue.Queue[dict[str, Any]]" = queue.Queue()
        self._udp_sock = udp_sock
        self._peer_addr = peer_addr or (test_response.address, test_response.port)
        self._transport_peer_addr = transport_peer_addr or (test_response.address, test_response.port)
        self._p2p_session_flag = p2p_session_flag or response.session_flag or ""
        self.local_id = 0
        self.remote_id = 0
        self.word4 = self.CONTROL_BOOTSTRAP_WORD4
        self.word8 = 0
        self.status_word = self.CONTROL_BOOTSTRAP_STATUS
        self._forced_transition = False
        self._transport_frames_seen = 0
        self._late_bootstrap_pending = 0
        self._late_post_bootstrap_prime = False
        self._thread: threading.Thread | None = None
        self._play_sync_thread: threading.Thread | None = None
        self._last_control: ParsedRbUdpControlPacket | None = None
        self._last_wrapped: ParsedRbUdpWrappedPacket | None = None
        self._bootstrap_sent_to: tuple[str, int] | None = None
        self._wrapped_debug_seen: set[str] = set()
        self._wrapped_fragment_streams: dict[
            tuple[int, int],
            dict[str, Any],
        ] = {}
        self.stream_payload_early_filler_count = 0
        self.stream_payload_early_count = 0
        self.stream_payload_filler_count = 0
        self.stream_payload_count = 0

    def _dbg(self, message: str, **kwargs: Any) -> None:
        details = " ".join(f"{key}={value}" for key, value in kwargs.items())
        if details:
            print(f"[RbUdp] {message} {details}")
        else:
            print(f"[RbUdp] {message}")

    def _queue_payload(self, payload: bytes, *, source: str, **meta: Any) -> None:
        self._data.put(
            {
                "payload": payload,
                "source": source,
                "meta": meta,
            }
        )

    def _fragment_stream_key(self, *, word4: int, word8: int) -> tuple[int, int]:
        return (word4 & 0xFFFFFFFF, word8 & 0xFFFFFFFF)

    def _lane_for_packet_words(self, *, word4: int, word8: int) -> dict[str, int | bool] | None:
        for lane in self._lane_states:
            if int(lane["peer_word4"]) == word4 and int(lane["peer_word8"]) == word8:
                return lane
            if int(lane["word4"]) == word8 and int(lane["word8"]) == word4:
                return lane
        return None

    def _ack_wrapped_fragment_stream(self, stream: dict[str, Any], *, reason: str) -> None:
        next_local_id = int(stream["next_local_id"])
        if int(stream.get("last_ack_remote_id", 0)) == next_local_id:
            return
        lane = self._lane_for_packet_words(
            word4=int(stream["word4"]),
            word8=int(stream["word8"]),
        )
        if lane is None:
            self._dbg(
                "skip_wrapped_fragment_ack_no_lane",
                word4=hex(int(stream["word4"])),
                word8=hex(int(stream["word8"])),
                next_local_id=next_local_id,
                reason=reason,
            )
            return
        self._send_lane_control(
            lane,
            status_word=self.CONTROL_FRAGMENT_ACK_STATUS,
            local_id=int(stream["remote_id"]),
            remote_id=next_local_id,
            log_label="send_control_fragment_ack",
        )
        stream["last_ack_remote_id"] = next_local_id

    def _carry_wrapped_fragment_remainder(
        self,
        stream: dict[str, Any],
        *,
        remainder: bytes,
        previous_total_length: int,
    ) -> None:
        if not remainder:
            return
        next_start_local_id = int(stream["start_local_id"]) + previous_total_length
        if len(remainder) < 8 or remainder[:4] != b"\xff\xff\xff\xff":
            self._dbg(
                "discard_wrapped_fragment_remainder",
                word4=hex(int(stream["word4"])),
                word8=hex(int(stream["word8"])),
                start_local_id=next_start_local_id,
                remainder_len=len(remainder),
                prefix=remainder[:32].hex(),
            )
            return
        inner_total_length = int.from_bytes(remainder[4:8], "little")
        if inner_total_length < 0x10:
            self._dbg(
                "discard_wrapped_fragment_remainder_bad_length",
                word4=hex(int(stream["word4"])),
                word8=hex(int(stream["word8"])),
                start_local_id=next_start_local_id,
                inner_total_length=inner_total_length,
                remainder_len=len(remainder),
            )
            return
        key = self._fragment_stream_key(
            word4=int(stream["word4"]),
            word8=int(stream["word8"]),
        )
        carried = {
            "marker": int(stream["marker"]),
            "word4": int(stream["word4"]),
            "word8": int(stream["word8"]),
            "start_local_id": next_start_local_id,
            "remote_id": int(stream["remote_id"]),
            "status_word": int(stream["status_word"]),
            "rand16": int(stream["rand16"]),
            "packet_len16": int(stream["packet_len16"]),
            "inner_total_length": inner_total_length,
            "payload": bytearray(remainder),
            "next_local_id": next_start_local_id + len(remainder),
            "last_ack_remote_id": next_start_local_id + len(remainder),
        }
        self._wrapped_fragment_streams[key] = carried
        self._dbg(
            "carry_wrapped_fragment_remainder",
            word4=hex(int(stream["word4"])),
            word8=hex(int(stream["word8"])),
            start_local_id=next_start_local_id,
            have=len(remainder),
            need=inner_total_length,
            next_local_id=int(carried["next_local_id"]),
        )

    def _resync_wrapped_fragment_stream_gap(
        self,
        stream: dict[str, Any],
        *,
        data: bytes,
        got_local_id: int,
        want_local_id: int,
    ) -> bool:
        payload = data[0x1C:]
        start_local_id = int(stream["start_local_id"])
        inner_total_length = int(stream["inner_total_length"])
        inner_end_local_id = start_local_id + inner_total_length
        payload_end_local_id = got_local_id + len(payload)
        key = self._fragment_stream_key(
            word4=int(stream["word4"]),
            word8=int(stream["word8"]),
        )
        self._wrapped_fragment_streams.pop(key, None)

        self._dbg(
            "wrapped_fragment_stream_gap",
            word4=hex(int(stream["word4"])),
            word8=hex(int(stream["word8"])),
            got_local_id=got_local_id,
            want_local_id=want_local_id,
            start_local_id=start_local_id,
            inner_end_local_id=inner_end_local_id,
            payload_len=len(payload),
        )

        if got_local_id < inner_end_local_id < payload_end_local_id:
            tail_offset = inner_end_local_id - got_local_id
            tail = payload[tail_offset:]
            self._dbg(
                "resync_wrapped_fragment_stream_gap_tail",
                word4=hex(int(stream["word4"])),
                word8=hex(int(stream["word8"])),
                tail_start_local_id=inner_end_local_id,
                tail_len=len(tail),
                tail_prefix=tail[:32].hex(),
            )
            self._carry_wrapped_fragment_remainder(
                stream,
                remainder=tail,
                previous_total_length=inner_total_length,
            )
            return True

        if got_local_id >= inner_end_local_id and payload.startswith(b"\xff\xff\xff\xff"):
            previous_total_length = got_local_id - start_local_id
            self._dbg(
                "resync_wrapped_fragment_stream_gap_new_packet",
                word4=hex(int(stream["word4"])),
                word8=hex(int(stream["word8"])),
                start_local_id=got_local_id,
                payload_len=len(payload),
                payload_prefix=payload[:32].hex(),
            )
            self._carry_wrapped_fragment_remainder(
                stream,
                remainder=payload,
                previous_total_length=previous_total_length,
            )
            return True

        self._dbg(
            "discard_wrapped_fragment_stream_gap_payload",
            word4=hex(int(stream["word4"])),
            word8=hex(int(stream["word8"])),
            got_local_id=got_local_id,
            want_local_id=want_local_id,
            inner_end_local_id=inner_end_local_id,
            payload_end_local_id=payload_end_local_id,
            prefix=payload[:32].hex(),
        )
        return True

    def _start_wrapped_fragment_stream(self, data: bytes) -> bool:
        if len(data) < 0x24:
            return False
        inner_total_length = int.from_bytes(data[0x20:0x24], "little")
        if inner_total_length < 0x10:
            return False
        word4 = int.from_bytes(data[0x04:0x08], "little")
        word8 = int.from_bytes(data[0x08:0x0C], "little")
        local_id = int.from_bytes(data[0x0C:0x10], "little")
        remote_id = int.from_bytes(data[0x10:0x14], "little")
        key = self._fragment_stream_key(word4=word4, word8=word8)
        existing = self._wrapped_fragment_streams.get(key)
        if existing is not None:
            existing_have = len(existing["payload"])
            if (
                int(existing["inner_total_length"]) == inner_total_length
                and existing_have >= len(data[0x1C:])
            ):
                self._dbg(
                    "ignore_wrapped_fragment_stream_restart",
                    word4=hex(word4),
                    word8=hex(word8),
                    local_id=local_id,
                    remote_id=remote_id,
                    existing_have=existing_have,
                    incoming_have=len(data[0x1C:]),
                )
                return True
        payload = bytearray(data[0x1C:])
        self._wrapped_fragment_streams[key] = {
            "marker": int.from_bytes(data[0x00:0x04], "little"),
            "word4": word4,
            "word8": word8,
            "start_local_id": local_id,
            "remote_id": remote_id,
            "status_word": int.from_bytes(data[0x14:0x18], "little"),
            "rand16": int.from_bytes(data[0x18:0x1A], "little"),
            "packet_len16": int.from_bytes(data[0x1A:0x1C], "little"),
            "inner_total_length": inner_total_length,
            "payload": payload,
            "next_local_id": local_id + len(payload),
            "last_ack_remote_id": 0,
        }
        self._dbg(
            "start_wrapped_fragment_stream",
            word4=hex(word4),
            word8=hex(word8),
            local_id=local_id,
            remote_id=remote_id,
            inner_total_length=inner_total_length,
            have=len(payload),
            next_local_id=local_id + len(payload),
        )
        self._ack_wrapped_fragment_stream(self._wrapped_fragment_streams[key], reason="start")
        return True

    def _append_wrapped_fragment_stream(self, data: bytes) -> bool:
        word4 = int.from_bytes(data[0x04:0x08], "little")
        word8 = int.from_bytes(data[0x08:0x0C], "little")
        local_id = int.from_bytes(data[0x0C:0x10], "little")
        remote_id = int.from_bytes(data[0x10:0x14], "little")
        key = self._fragment_stream_key(word4=word4, word8=word8)
        stream = self._wrapped_fragment_streams.get(key)
        if stream is None:
            return False
        if local_id != int(stream["next_local_id"]):
            if local_id < int(stream["next_local_id"]):
                self._dbg(
                    "ignore_wrapped_fragment_stream_replay",
                    word4=hex(word4),
                    word8=hex(word8),
                    got_local_id=local_id,
                    want_local_id=int(stream["next_local_id"]),
                    start_local_id=int(stream["start_local_id"]),
                )
                return True
            return self._resync_wrapped_fragment_stream_gap(
                stream,
                data=data,
                got_local_id=local_id,
                want_local_id=int(stream["next_local_id"]),
            )
        payload = data[0x1C:]
        stream["payload"].extend(payload)
        stream["next_local_id"] = local_id + len(payload)
        self._dbg(
            "append_wrapped_fragment_stream",
            word4=hex(word4),
            word8=hex(word8),
            local_id=local_id,
            remote_id=remote_id,
            have=len(stream["payload"]),
            need=int(stream["inner_total_length"]),
            next_local_id=int(stream["next_local_id"]),
        )
        self._ack_wrapped_fragment_stream(stream, reason="append")
        if len(stream["payload"]) < int(stream["inner_total_length"]):
            return True

        inner_total_length = int(stream["inner_total_length"])
        full_payload = bytes(stream["payload"])
        inner_packet = full_payload[:inner_total_length]
        remainder = full_payload[inner_total_length:]
        del self._wrapped_fragment_streams[key]
        self._dbg(
            "complete_wrapped_fragment_stream",
            word4=hex(word4),
            word8=hex(word8),
            inner_total_length=inner_total_length,
            remainder_len=len(remainder),
        )
        self._handle_wrapped(
            ParsedRbUdpWrappedPacket(
                marker=int(stream["marker"]),
                word4=int(stream["word4"]),
                word8=int(stream["word8"]),
                local_id=local_id,
                remote_id=remote_id,
                status_word=int(stream["status_word"]),
                rand16=int(stream["rand16"]),
                packet_len16=int(stream["packet_len16"]),
                inner_total_length=inner_total_length,
                tag8=b"",
                inner_packet=inner_packet,
            )
        )
        self._carry_wrapped_fragment_remainder(
            stream,
            remainder=remainder,
            previous_total_length=inner_total_length,
        )
        return True

    @property
    def peer_addr(self) -> tuple[str, int]:
        return self._peer_addr

    @property
    def transport_peer_addr(self) -> tuple[str, int]:
        return self._transport_peer_addr

    def _next_lane_nonce(self, lane: dict[str, int | bool]) -> int:
        nonce = int(lane["nonce"]) & 0xFFFFFFFF
        lane["nonce"] = (nonce + 1) & 0xFFFFFFFF
        return nonce

    def _send_udp(self, packet: bytes) -> None:
        if self._udp_sock is None:
            raise RuntimeError("RB UDP tunnel requires a UDP socket")
        self._udp_sock.sendto(packet, udp_target_tuple(self._udp_sock, self._peer_addr[0], self._peer_addr[1]))

    def _send_play_sync_ack(self, lane: dict[str, int | bool], *, local_id: int, remote_id: int) -> None:
        self._send_lane_control(
            lane,
            status_word=self.CONTROL_PLAY_SYNC_ACK_STATUS,
            local_id=local_id,
            remote_id=remote_id,
            log_label="send_control_play_sync_ack",
        )

    def _send_play_stage_ack(
        self,
        lane: dict[str, int | bool],
        *,
        status_word: int,
        local_id: int,
        remote_id: int,
        log_label: str,
    ) -> None:
        self._send_lane_control(
            lane,
            status_word=status_word,
            local_id=local_id,
            remote_id=remote_id,
            log_label=log_label,
        )

    def _send_play_data_probe(
        self,
        lane: dict[str, int | bool],
        *,
        seq: int,
        local_id: int,
        remote_id: int,
        payload: bytes,
    ) -> None:
        inner = build_rb_data_packet(
            payload=payload,
            src_id=int(lane["src_id"]),
            dest_id=self.CONTROL_PLAY_PROBE_INNER_DEST,
            seq=seq,
        )
        rand16 = self._next_lane_nonce(lane) & 0xFFFF
        packet = build_rb_udp_wrapped_packet(
            inner,
            word4=int(lane["word4"]),
            word8=int(lane["word8"]),
            local_id=local_id,
            remote_id=remote_id,
            status_word=self.WRAPPED_STATUS,
            nonce=rand16,
            tag8=self.CONTROL_PLAY_PROBE_TAG,
        )
        self._dbg(
            "send_wrapped_play_probe",
            peer=self._peer_addr,
            src_id=hex(int(lane["src_id"])),
            word4=hex(int(lane["word4"])),
            word8=hex(int(lane["word8"])),
            local_id=local_id,
            remote_id=remote_id,
            seq=seq,
            inner_dest_id=hex(self.CONTROL_PLAY_PROBE_INNER_DEST),
            payload_len=len(payload),
        )
        self._send_udp(packet)

    def _maybe_send_play_probe(self, lane: dict[str, int | bool], *, remote_id: int) -> None:
        probe_stage = int(lane["play_probe_stage"])
        sent_count = int(lane["play_sync_sent_count"])
        local_base = int(lane["play_sync_local_id"])
        if not local_base:
            return
        if probe_stage == 0 and sent_count >= 18:
            if not bool(lane["play_word_refresh_sent"]):
                for late_lane in self._lane_states:
                    if int(late_lane["local_id"]) == 0 and int(late_lane["remote_id"]) == 0:
                        continue
                    self._refresh_lane_word4(late_lane, target_word4=self._late_family_target_word4(late_lane))
                    late_lane["play_word_refresh_sent"] = True
                    late_lane["play_word_refresh2_sent"] = True
            self._send_play_data_probe(
                lane,
                seq=2,
                local_id=(local_base - 0x88) & 0xFFFFFFFF,
                remote_id=(remote_id + 0x118) & 0xFFFFFFFF,
                payload=self.CONTROL_PLAY_PROBE2_PAYLOAD,
            )
            lane["play_probe_stage"] = 1
            return
        if probe_stage == 1 and sent_count >= 35:
            self._send_play_data_probe(
                lane,
                seq=3,
                local_id=local_base,
                remote_id=(remote_id - 0x12) & 0xFFFFFFFF,
                payload=self.CONTROL_PLAY_PROBE3_PAYLOAD,
            )
            lane["play_sync_local_id"] = (local_base + self.CONTROL_PLAY_SYNC_STAGE2_LOCAL_DELTA) & 0xFFFFFFFF
            lane["play_sync_remote_bias"] = self.CONTROL_PLAY_SYNC_STAGE2_REMOTE_BIAS
            lane["play_probe_stage"] = 2
            return
        if probe_stage == 2 and sent_count >= 48:
            self._send_play_data_probe(
                lane,
                seq=4,
                local_id=local_base,
                remote_id=(remote_id - 0x152) & 0xFFFFFFFF,
                payload=self.CONTROL_PLAY_PROBE4_PAYLOAD,
            )
            lane["play_probe_stage"] = 3

    def _effective_play_sync_remote_id(self, lane: dict[str, int | bool], remote_id: int) -> int:
        bias = int(lane["play_sync_remote_bias"])
        return (remote_id + bias) & 0xFFFFFFFF

    def _refresh_lane_word4(
        self,
        lane: dict[str, int | bool],
        *,
        target_word4: int | None = None,
        high_delta: int = 0x12,
        low_delta: int = 0x0A,
    ) -> None:
        current_word4 = int(lane["word4"])
        if target_word4 is not None:
            refreshed_word4 = target_word4 & 0xFFFFFFFF
        else:
            high = (current_word4 >> 24) & 0xFF
            low = current_word4 & 0xFF
            if high < high_delta or low < low_delta:
                return
            refreshed_word4 = ((high - high_delta) << 24) | ((current_word4 & 0x00FFFF00)) | ((low - low_delta) & 0xFF)
        lane["word4"] = refreshed_word4
        lane["peer_word8"] = refreshed_word4
        self._dbg(
            "refresh_lane_word4",
            src_id=hex(int(lane["src_id"])),
            word4=hex(refreshed_word4),
            word8=hex(int(lane["word8"])),
            peer_word4=hex(int(lane["peer_word4"])),
            peer_word8=hex(int(lane["peer_word8"])),
        )

    def _late_family_target_word4(self, lane: dict[str, int | bool]) -> int:
        lane_offset = int(lane["src_id"]) - int(self.src_ids[0])
        return (0x3D000022 + (lane_offset * 0x01000001)) & 0xFFFFFFFF

    def _maybe_send_play_stage_controls(self, lane: dict[str, int | bool], *, remote_id: int) -> None:
        sent_count = int(lane["play_sync_sent_count"])
        local_id = int(lane["play_sync_local_id"])
        effective_remote_id = self._effective_play_sync_remote_id(lane, remote_id)
        if sent_count == 37:
            self._send_play_stage_ack(
                lane,
                status_word=self.CONTROL_PLAY_SYNC_STAGE2_STATUS,
                local_id=local_id,
                remote_id=effective_remote_id,
                log_label="send_control_play_stage2_ack",
            )
            return
        if sent_count == 41:
            lane["play_sync_remote_bias"] = self.CONTROL_PLAY_SYNC_STAGE3_REMOTE_BIAS
            effective_remote_id = self._effective_play_sync_remote_id(lane, remote_id)
            self._send_play_stage_ack(
                lane,
                status_word=self.CONTROL_PLAY_SYNC_STAGE3_STATUS,
                local_id=local_id,
                remote_id=effective_remote_id,
                log_label="send_control_play_stage3_ack",
            )
            if int(lane["word4"]) not in (0x3D000022, 0x3E000023):
                self._refresh_lane_word4(lane)
            return
        if sent_count == 49:
            lane["play_sync_local_id"] = (local_id + self.CONTROL_PLAY_SYNC_STAGE4_LOCAL_DELTA) & 0xFFFFFFFF
            lane["play_sync_remote_bias"] = self.CONTROL_PLAY_SYNC_STAGE4_REMOTE_BIAS
            local_id = int(lane["play_sync_local_id"])
            effective_remote_id = self._effective_play_sync_remote_id(lane, remote_id)
            self._send_play_stage_ack(
                lane,
                status_word=self.CONTROL_PLAY_SYNC_STAGE4_STATUS,
                local_id=local_id,
                remote_id=effective_remote_id,
                log_label="send_control_play_stage4_ack",
            )
            return
        if sent_count == 53:
            lane["play_sync_remote_bias"] = self.CONTROL_PLAY_SYNC_STAGE5_REMOTE_BIAS
            local_id = int(lane["play_sync_local_id"])
            effective_remote_id = self._effective_play_sync_remote_id(lane, remote_id)
            self._send_play_stage_ack(
                lane,
                status_word=self.CONTROL_PLAY_SYNC_STAGE5_STATUS,
                local_id=local_id,
                remote_id=effective_remote_id,
                log_label="send_control_play_stage5_ack",
            )
            return
        if sent_count == 60:
            lane["play_sync_remote_bias"] = self.CONTROL_PLAY_SYNC_STAGE6_REMOTE_BIAS
            local_id = int(lane["play_sync_local_id"])
            effective_remote_id = self._effective_play_sync_remote_id(lane, remote_id)
            self._send_play_stage_ack(
                lane,
                status_word=self.CONTROL_PLAY_SYNC_STAGE6_STATUS,
                local_id=local_id,
                remote_id=effective_remote_id,
                log_label="send_control_play_stage6_ack",
            )
            return
        if sent_count == 61 and not bool(lane["play_transport_refresh_sent"]):
            self._prime_lan_transport(seq_base=0x00018313)
            lane["play_transport_refresh_sent"] = True
            return
        if sent_count == 67 and not bool(lane["play_transport_refresh2_sent"]):
            self._prime_lan_transport(seq_base=0x00018AE4)
            lane["play_transport_refresh2_sent"] = True
            return
        if sent_count >= 68 and bool(lane["play_transport_refresh2_sent"]) and not bool(lane["play_word_refresh2_sent"]):
            for late_lane in self._lane_states:
                if int(late_lane["local_id"]) == 0 and int(late_lane["remote_id"]) == 0:
                    continue
                self._refresh_lane_word4(late_lane, target_word4=self._late_family_target_word4(late_lane))
            lane["play_word_refresh2_sent"] = True

    def _start_play_sync(self, lane: dict[str, int | bool], *, local_id: int, seed_remote_id: int) -> None:
        lane["play_sync_active"] = True
        lane["play_sync_local_id"] = local_id & 0xFFFFFFFF
        lane["play_sync_counter"] = seed_remote_id & 0xFFFFFFFF
        lane["play_sync_remaining"] = 72
        lane["play_sync_sent_count"] = 0
        lane["play_sync_remote_bias"] = 0
        lane["play_word_refresh_sent"] = False
        lane["play_transport_refresh_sent"] = False
        lane["play_transport_refresh2_sent"] = False
        lane["play_word_refresh2_sent"] = False
        play_sync_local_id = int(lane["play_sync_local_id"])
        remote_id = int(lane["play_sync_counter"])
        if play_sync_local_id and remote_id:
            self._send_play_sync_ack(
                lane,
                local_id=play_sync_local_id,
                remote_id=self._effective_play_sync_remote_id(lane, remote_id),
            )
            lane["play_sync_sent_count"] = int(lane["play_sync_sent_count"]) + 1
            self._maybe_send_play_probe(lane, remote_id=remote_id)
            self._maybe_send_play_stage_controls(lane, remote_id=remote_id)
            lane["play_sync_counter"] = (remote_id + self.CONTROL_PLAY_SYNC_STEP) & 0xFFFFFFFF
            lane["play_sync_remaining"] = max(0, int(lane["play_sync_remaining"]) - 1)

    def _play_sync_loop(self) -> None:
        while not self._stop.is_set():
            try:
                if self._quii_play_sent.is_set():
                    for lane in self._lane_states:
                        if not bool(lane["play_sync_active"]):
                            continue
                        if int(lane["play_sync_remaining"]) <= 0:
                            lane["play_sync_active"] = False
                            continue
                        local_id = int(lane["play_sync_local_id"])
                        remote_id = int(lane["play_sync_counter"])
                        if not local_id or not remote_id:
                            continue
                        self._send_play_sync_ack(
                            lane,
                            local_id=local_id,
                            remote_id=self._effective_play_sync_remote_id(lane, remote_id),
                        )
                        lane["play_sync_sent_count"] = int(lane["play_sync_sent_count"]) + 1
                        self._maybe_send_play_probe(lane, remote_id=remote_id)
                        self._maybe_send_play_stage_controls(lane, remote_id=remote_id)
                        lane["play_sync_counter"] = (remote_id + self.CONTROL_PLAY_SYNC_STEP) & 0xFFFFFFFF
                        lane["play_sync_remaining"] = max(0, int(lane["play_sync_remaining"]) - 1)
            except Exception:
                pass
            time.sleep(0.05)

    def _send_transport_udp(self, packet: bytes, peer_addr: tuple[str, int] | None = None) -> None:
        if self._udp_sock is None:
            raise RuntimeError("RB UDP tunnel requires a UDP socket")
        target = peer_addr or self._transport_peer_addr
        self._udp_sock.sendto(packet, udp_target_tuple(self._udp_sock, target[0], target[1]))

    def _prime_lan_transport(self, *, seq_base: int | None = None) -> None:
        if self._udp_sock is None:
            raise RuntimeError("RB UDP tunnel requires a UDP socket")
        local_udp_port = self._udp_sock.getsockname()[1]
        for idx, tail_code in enumerate((200, 102)):
            packet = build_p2p_active_packet(
                session_flag=self._p2p_session_flag,
                seq=((seq_base + idx) & 0xFFFFFFFF) if seq_base is not None else random.randrange(0x100000000),
                local_udp_port=local_udp_port,
                tail_code=tail_code,
            )
            self._dbg(
                "prime_lan_transport",
                peer=self._transport_peer_addr,
                tail=tail_code,
                seq=hex((seq_base + idx) & 0xFFFFFFFF) if seq_base is not None else "random",
            )
            self._send_transport_udp(packet, peer_addr=self._transport_peer_addr)

    def _send_control_bootstrap(self) -> None:
        for lane in self._lane_states:
            local_id = int(lane["bootstrap_local_id"])
            remote_id = int(lane["bootstrap_remote_id"])
            rand16 = self._next_lane_nonce(lane) & 0xFFFF
            packet = build_rb_udp_control_packet(
                word4=int(lane["bootstrap_word4"]),
                word8=int(lane["bootstrap_word8"]),
                local_id=local_id,
                remote_id=remote_id,
                status_word=self.CONTROL_BOOTSTRAP_STATUS,
                nonce=rand16,
            )
            self._dbg(
                "send_control_bootstrap",
                peer=self._peer_addr,
                src_id=hex(int(lane["src_id"])),
                word4=hex(int(lane["bootstrap_word4"])),
                word8=hex(int(lane["bootstrap_word8"])),
                local_id=hex(local_id),
                remote_id=hex(remote_id),
                status=hex(self.CONTROL_BOOTSTRAP_STATUS),
                rand16=hex(rand16),
                packet_len=28,
            )
            self._send_udp(packet)
        self._bootstrap_sent_to = self._peer_addr

    def _send_control_established(self, lane: dict[str, int | bool], *, status_word: int | None = None) -> None:
        status_word = self.CONTROL_ESTABLISHED_STATUS if status_word is None else status_word
        rand16 = self._next_lane_nonce(lane) & 0xFFFF
        packet = build_rb_udp_control_packet(
            word4=int(lane["word4"]),
            word8=int(lane["word8"]),
            local_id=int(lane["local_id"]),
            remote_id=int(lane["remote_id"]),
            status_word=status_word,
            nonce=rand16,
        )
        self._dbg(
            "send_control_established",
            peer=self._peer_addr,
            src_id=hex(int(lane["src_id"])),
            word4=hex(int(lane["word4"])),
            word8=hex(int(lane["word8"])),
            local_id=int(lane["local_id"]),
            remote_id=int(lane["remote_id"]),
            status=hex(status_word),
            rand16=hex(rand16),
            packet_len=28,
            hex=packet.hex(),
        )
        self._send_udp(packet)
        if status_word == self.CONTROL_ESTABLISHED_STATUS:
            lane["established_sent"] = True

    def _send_pending_established(self) -> None:
        pending = [
            lane
            for lane in self._lane_states
            if bool(lane["syn_ack_received"]) and not bool(lane["established_sent"])
        ]
        if not pending:
            return
        if not all(bool(lane["syn_ack_received"]) for lane in self._lane_states):
            return
        for lane in pending:
            self._send_control_established(lane)
            self._send_wrapped_connect(lane)

    def _send_lane_control(
        self,
        lane: dict[str, int | bool],
        *,
        status_word: int,
        local_id: int | None = None,
        remote_id: int | None = None,
        word4: int | None = None,
        word8: int | None = None,
        log_label: str = "send_control",
    ) -> None:
        current_word4 = int(lane["word4"] if word4 is None else word4)
        current_word8 = int(lane["word8"] if word8 is None else word8)
        current_local_id = int(lane["local_id"] if local_id is None else local_id)
        current_remote_id = int(lane["remote_id"] if remote_id is None else remote_id)
        lane["word4"] = current_word4
        lane["word8"] = current_word8
        lane["local_id"] = current_local_id
        lane["remote_id"] = current_remote_id
        rand16 = self._next_lane_nonce(lane) & 0xFFFF
        packet = build_rb_udp_control_packet(
            word4=current_word4,
            word8=current_word8,
            local_id=current_local_id,
            remote_id=current_remote_id,
            status_word=status_word,
            nonce=rand16,
        )
        self._dbg(
            log_label,
            peer=self._peer_addr,
            src_id=hex(int(lane["src_id"])),
            word4=hex(current_word4),
            word8=hex(current_word8),
            local_id=current_local_id,
            remote_id=current_remote_id,
            status=hex(status_word),
            rand16=hex(rand16),
            packet_len=28,
            hex=packet.hex(),
        )
        self._send_udp(packet)

    def _force_initial_established_transition(self) -> None:
        if self._forced_transition:
            return
        self.word4 = 0x5500002B
        self.word8 = 0x01000000
        if self.local_id == 0:
            self.local_id = 1
        if self.remote_id == 0:
            self.remote_id = 1
        self._forced_transition = True
        self._dbg(
            "force_initial_established_transition",
            peer=self._peer_addr,
            word4=hex(self.word4),
            word8=hex(self.word8),
            local_id=self.local_id,
            remote_id=self.remote_id,
        )
        lane = self._lane_states[0]
        lane["word4"] = self.word4
        lane["word8"] = self.word8
        lane["local_id"] = self.local_id
        lane["remote_id"] = self.remote_id
        self._send_control_established(lane)
        self._send_wrapped_connect(lane)

    def _active_lane(self) -> dict[str, int | bool]:
        for lane in self._lane_states:
            if int(lane["src_id"]) == self.src_id:
                return lane
        return self._lane_states[0]

    def _lane_for_syn_ack(self, control: ParsedRbUdpControlPacket) -> dict[str, int | bool] | None:
        for lane in self._lane_states:
            bootstrap_word8 = int(lane["bootstrap_word8"])
            if control.word4 == bootstrap_word8:
                return lane
        return None

    def _lane_for_control(self, control: ParsedRbUdpControlPacket) -> dict[str, int | bool] | None:
        for lane in self._lane_states:
            if int(lane["peer_word4"]) == control.word4 and int(lane["peer_word8"]) == control.word8:
                return lane
        return None

    def _lane_for_src_id(self, src_id: int) -> dict[str, int | bool] | None:
        for lane in self._lane_states:
            if int(lane["src_id"]) == src_id:
                return lane
        return None

    def _send_wrapped(self, inner_packet: bytes, *, tag8: bytes, lane: dict[str, int | bool] | None = None) -> None:
        lane = self._active_lane() if lane is None else lane
        rand16 = self._next_lane_nonce(lane) & 0xFFFF
        packet = build_rb_udp_wrapped_packet(
            inner_packet,
            word4=int(lane["word4"]),
            word8=int(lane["word8"]),
            local_id=int(lane["local_id"]),
            remote_id=int(lane["remote_id"]),
            status_word=self.WRAPPED_STATUS,
            nonce=rand16,
            tag8=tag8,
        )
        self._send_udp(packet)

    def _connected_lane_destinations(self) -> list[tuple[dict[str, int | bool], int]]:
        pairs: list[tuple[dict[str, int | bool], int]] = []
        for lane in self._lane_states:
            src_id = int(lane["src_id"])
            dest_id = self.dest_ids.get(src_id)
            if dest_id is not None:
                pairs.append((lane, dest_id))
        return pairs

    def _send_wrapped_connect(self, lane: dict[str, int | bool]) -> None:
        if bool(lane["connect_sent"]):
            return
        src_id = int(lane["src_id"])
        inner = build_kcp_connect_packet(
            src_id=src_id,
            channel=int(self.config.logical_channel),
            conn_type=int(self.config.logical_conn_type),
        )
        self._dbg(
            "send_wrapped_connect",
            peer=self._peer_addr,
            src_id=hex(src_id),
            channel=self.config.logical_channel,
            conn_type=self.config.logical_conn_type,
            local_id=int(lane["local_id"]),
            remote_id=int(lane["remote_id"]),
            word4=hex(int(lane["word4"])),
            word8=hex(int(lane["word8"])),
        )
        self._send_wrapped(inner, tag8=self.CONNECT_TAG, lane=lane)
        lane["connect_sent"] = True

    def _send_wrapped_setup_probe(self, lane: dict[str, int | bool], *, connect_id: int, dest_id: int) -> None:
        if bool(lane["setup_probe_sent"]):
            return
        inner = build_rb_data_packet(
            payload=build_live_setup_packet(),
            src_id=connect_id,
            dest_id=dest_id,
            seq=0,
        )
        self._dbg(
            "send_wrapped_setup_probe",
            peer=self._peer_addr,
            src_id=hex(connect_id),
            dest_id=hex(dest_id),
            word4=hex(int(lane["word4"])),
            word8=hex(int(lane["word8"])),
            local_id=int(lane["local_id"]),
            remote_id=int(lane["remote_id"]),
            inner_hex=inner.hex(),
        )
        self._send_wrapped(inner, tag8=self.DATA_TAG, lane=lane)
        lane["setup_probe_sent"] = True

    def _handle_control(self, control: ParsedRbUdpControlPacket) -> None:
        self._last_control = control
        status16 = control.status_word & 0xFFFF
        self._dbg(
            "recv_control",
            peer=self._peer_addr,
            word4=hex(control.word4),
            word8=hex(control.word8),
            local_id=control.local_id,
            remote_id=control.remote_id,
            status=hex(control.status_word),
            status16=hex(status16),
        )

        if control.status_word == self.CONTROL_SYN_ACK_STATUS and control.remote_id:
            lane = self._lane_for_syn_ack(control)
            if lane is None:
                return
            lane["peer_word4"] = control.word4
            lane["peer_word8"] = control.word8
            lane["word4"] = control.word8
            lane["word8"] = int(lane["bootstrap_word8"])
            lane["local_id"] = control.remote_id
            lane["remote_id"] = control.remote_id
            lane["progress_sent"] = False
            lane["flow_sent"] = False
            lane["established_sent"] = False
            lane["post_play_established_sent"] = False
            lane["play_probe_stage"] = 0
            lane["play_sync_active"] = False
            lane["play_sync_local_id"] = 0
            lane["play_sync_counter"] = 0
            lane["play_sync_remaining"] = 0
            lane["play_sync_sent_count"] = 0
            lane["play_sync_remote_bias"] = 0
            lane["play_word_refresh_sent"] = False
            lane["play_transport_refresh_sent"] = False
            lane["syn_ack_received"] = True
            lane["peer_logic_id"] = 0
            self._dbg(
                "syn_ack_transition",
                src_id=hex(int(lane["src_id"])),
                peer_word4=hex(int(lane["peer_word4"])),
                peer_word8=hex(int(lane["peer_word8"])),
                word4=hex(int(lane["word4"])),
                word8=hex(int(lane["word8"])),
                local_id=int(lane["local_id"]),
                remote_id=int(lane["remote_id"]),
            )
            self._send_pending_established()
            return

        lane = self._lane_for_control(control)
        if lane is None:
            return

        if control.local_id:
            lane["local_id"] = control.local_id
        if control.remote_id and control.remote_id != 0xFFFFFFFF:
            lane["remote_id"] = control.remote_id
        if control.remote_id and control.remote_id not in (0xFFFFFFFF, 1):
            lane["peer_logic_id"] = control.remote_id

        peer_logic_id = int(lane["peer_logic_id"])

        if control.status_word == self.CONTROL_FLOW_STATUS:
            if control.local_id == 1 and peer_logic_id and not bool(lane["flow_sent"]):
                self._send_lane_control(
                    lane,
                    status_word=self.CONTROL_FLOW_STATUS,
                    local_id=peer_logic_id,
                    remote_id=1,
                    log_label="send_control_flow",
                )
                lane["flow_sent"] = True
            return

        if control.status_word == self.CONTROL_ESTABLISHED_STATUS:
            if (
                self._quii_play_sent.is_set()
                and
                control.local_id > 1
                and control.remote_id > 1
            ):
                self._send_lane_control(
                    lane,
                    status_word=self.CONTROL_PLAY_ESTABLISHED_ACK_STATUS,
                    local_id=control.remote_id,
                    remote_id=control.local_id,
                    log_label="send_control_play_established_ack",
                )
                if not bool(lane["play_sync_active"]):
                    self._start_play_sync(
                        lane,
                        local_id=(control.local_id + self.CONTROL_PLAY_SYNC_LOCAL_BIAS) & 0xFFFFFFFF,
                        seed_remote_id=(control.local_id + self.CONTROL_PLAY_SYNC_STEP) & 0xFFFFFFFF,
                    )
            return

        if control.status_word == self.CONTROL_PROGRESS_STATUS:
            if (
                peer_logic_id
                and control.remote_id == peer_logic_id
                and not bool(lane["progress_sent"])
                and not bool(lane.get("setup_probe_sent", False))
            ):
                self._dbg(
                    "progress_reconnect_hint",
                    src_id=hex(int(lane["src_id"])),
                    control_local_id=control.local_id,
                    control_remote_id=control.remote_id,
                    peer_logic_id=peer_logic_id,
                )
                self._send_wrapped_connect(lane)
            if (
                control.local_id == peer_logic_id
                and peer_logic_id
                and control.remote_id == peer_logic_id
                and not bool(lane["progress_sent"])
            ):
                self._send_lane_control(
                    lane,
                    status_word=self.CONTROL_PROGRESS_STATUS,
                    local_id=peer_logic_id,
                    remote_id=peer_logic_id,
                    log_label="send_control_progress",
                )
                lane["progress_sent"] = True
                self._send_wrapped_connect(lane)
            return

        if control.status_word == self.CONTROL_POST_CONNECT_STATUS:
            next_local = control.remote_id if control.remote_id else int(lane["remote_id"])
            next_remote = (next_local + 0x38) & 0xFFFFFFFF
            self._send_lane_control(
                lane,
                status_word=self.CONTROL_POST_CONNECT_ACK_STATUS,
                local_id=next_local,
                remote_id=next_remote,
                log_label="send_control_post_connect_ack",
            )
            lane["local_id"] = next_local
            lane["remote_id"] = next_remote
            return

        if control.status_word == self.CONTROL_POST_SETUP_STATUS:
            next_local = control.remote_id if control.remote_id else int(lane["remote_id"])
            next_remote = (next_local + 0x60) & 0xFFFFFFFF
            self._send_lane_control(
                lane,
                status_word=self.CONTROL_POST_SETUP_ACK_STATUS,
                local_id=next_local,
                remote_id=next_remote,
                log_label="send_control_post_setup_ack",
            )
            lane["local_id"] = next_local
            lane["remote_id"] = next_remote
            return

        if control.status_word == self.CONTROL_STREAM_READY_STATUS:
            next_local = control.remote_id if control.remote_id else int(lane["remote_id"])
            next_remote = (next_local - 0x08) & 0xFFFFFFFF
            self._send_lane_control(
                lane,
                status_word=self.CONTROL_STREAM_READY_ACK_STATUS,
                local_id=next_local,
                remote_id=next_remote,
                log_label="send_control_stream_ready_ack",
            )
            lane["local_id"] = next_local
            lane["remote_id"] = next_remote
            self._quii_ready.set()
            return

        if control.status_word == self.CONTROL_PLAY_LATE_STATUS:
            self._dbg(
                "recv_control_play_late_status",
                src_id=hex(int(lane["src_id"])),
                word4=hex(int(lane["word4"])),
                word8=hex(int(lane["word8"])),
                local_id=control.local_id,
                remote_id=control.remote_id,
            )
            return

        if control.status_word == self.CONTROL_PLAY_SYNC_STATUS:
            self._start_play_sync(
                lane,
                local_id=(control.remote_id if control.remote_id else control.local_id),
                seed_remote_id=(control.local_id + self.CONTROL_PLAY_SYNC_STEP) & 0xFFFFFFFF,
            )
            return

    def _consume_transport_frame(self, data: bytes) -> bool:
        try:
            frame = parse_p2p_transport_frame(data)
        except Exception as exc:
            if len(data) == 164:
                self._dbg("transport_parse_fail", error=repr(exc), prefix=data[:32].hex())
            return False
        if frame.session_flag != self._p2p_session_flag and not (
            self._p2p_session_flag.startswith(frame.session_flag) or frame.session_flag.startswith(self._p2p_session_flag)
        ):
            self._dbg(
                "transport_session_mismatch",
                got=frame.session_flag,
                want=self._p2p_session_flag,
                remote_ip=frame.remote_ip,
                remote_port=frame.remote_port,
                tail=frame.tail_code,
                packet_type=frame.packet_type_flag,
            )
            return False
        self._dbg(
            "transport_frame",
            remote_ip=frame.remote_ip,
            remote_port=frame.remote_port,
            tail=frame.tail_code,
            packet_type=frame.packet_type_flag,
        )
        self._transport_frames_seen += 1
        if self._late_bootstrap_pending > 0:
            self._late_bootstrap_pending -= 1
            if self._late_bootstrap_pending == 0:
                self._send_control_bootstrap()
                if self._late_post_bootstrap_prime:
                    self._prime_lan_transport()
                    self._late_post_bootstrap_prime = False
        if frame.is_request and frame.remote_ip and frame.remote_port:
            ack = build_p2p_transport_ack(frame, local_udp_port=self._udp_sock.getsockname()[1])
            new_peer = (frame.remote_ip, frame.remote_port)
            self._transport_peer_addr = new_peer
            self._send_transport_udp(ack, peer_addr=new_peer)
            current_peer_is_private = is_private_ipv4(self._peer_addr[0])
            if current_peer_is_private:
                self._dbg(
                    "ignore_transport_peer_rebind",
                    current_peer=self._peer_addr,
                    transport_peer=new_peer,
                    transport_keepalive_peer=self._transport_peer_addr,
                )
            else:
                peer_changed = new_peer != self._peer_addr
                self._peer_addr = new_peer
                if self.local_id == 0 and self.remote_id == 0 and (peer_changed or self._bootstrap_sent_to != new_peer):
                    self._dbg("bootstrap_to_new_transport_peer", peer=new_peer)
                    self._send_control_bootstrap()
        return True

    def _handle_wrapped(self, wrapped: ParsedRbUdpWrappedPacket) -> None:
        self._last_wrapped = wrapped
        self._dbg(
            "recv_wrapped",
            peer=self._peer_addr,
            word4=hex(wrapped.word4),
            word8=hex(wrapped.word8),
            tag=wrapped.tag8,
            inner_len=wrapped.inner_total_length,
            local_id=wrapped.local_id,
            remote_id=wrapped.remote_id,
            status=hex(wrapped.status_word),
        )
        lane = None
        for candidate in self._lane_states:
            candidate_word4 = int(candidate["word4"])
            candidate_word8 = int(candidate["word8"])
            if (
                (candidate_word4 == wrapped.word4 and candidate_word8 == wrapped.word8)
                or (candidate_word8 == wrapped.word4 and candidate_word4 == wrapped.word8)
            ):
                lane = candidate
                break
        if lane is not None:
            if wrapped.local_id and not int(lane["local_id"]):
                lane["local_id"] = wrapped.local_id
            if wrapped.remote_id and not int(lane["remote_id"]):
                lane["remote_id"] = wrapped.remote_id
            peer_logic_id = int(lane["peer_logic_id"])
            if (
                wrapped.tag8 == self.CONNECT_TAG
                and peer_logic_id
                and not bool(lane["progress_sent"])
            ):
                self._send_lane_control(
                    lane,
                    status_word=self.CONTROL_PROGRESS_STATUS,
                    local_id=peer_logic_id,
                    remote_id=peer_logic_id,
                    log_label="send_control_progress",
                )
                lane["progress_sent"] = True
        try:
            frames = iter_kcp_packet_frames(wrapped.inner_packet)
        except Exception as exc:
            wrapped_key = wrapped.inner_packet.hex()
            if wrapped_key not in self._wrapped_debug_seen:
                self._wrapped_debug_seen.add(wrapped_key)
                self._dbg(
                    "recv_wrapped_unparsed",
                    error=repr(exc),
                    inner_hex=wrapped.inner_packet.hex(),
                )
            return

        for frame in frames:
            frame_hex = frame.raw.hex()
            should_debug_inner = frame_hex not in self._wrapped_debug_seen
            if should_debug_inner:
                self._wrapped_debug_seen.add(frame_hex)
            try:
                parsed = parse_kcp_packet_frame(frame)
            except Exception as exc:
                if should_debug_inner:
                    self._dbg(
                        "recv_wrapped_unparsed",
                        error=repr(exc),
                        inner_hex=frame_hex,
                    )
                continue

            if should_debug_inner and parsed.connect is not None:
                self._dbg(
                    "recv_wrapped_connect_parsed",
                    packet_type=parsed.connect.packet_type_flag,
                    result_code=parsed.connect.result_code,
                    command=hex(parsed.connect.command),
                    payload_length=parsed.connect.payload_length,
                    connect_id=hex(parsed.connect.connect_id),
                    dest_id=hex(parsed.connect.dest_id),
                    ok=parsed.connect.ok,
                    inner_hex=frame_hex,
                )
            elif should_debug_inner and parsed.data is not None:
                self._dbg(
                    "recv_wrapped_data_parsed",
                    packet_type=parsed.data.packet_type_flag,
                    command=hex(parsed.data.command),
                    seq=hex(parsed.data.seq),
                    payload_length=parsed.data.payload_length,
                    dest_id=hex(parsed.data.dest_id),
                    src_id=hex(parsed.data.src_id),
                    inner_hex=frame_hex,
                )

            if parsed.connect is not None:
                connect_lane = self._lane_for_src_id(parsed.connect.connect_id)
                connect_valid = (
                    parsed.connect.packet_type_flag == 1
                    and connect_lane is not None
                    and parsed.connect.connect_id == int(connect_lane["src_id"])
                    and parsed.connect.dest_id != 0
                )
                if connect_valid:
                    self.dest_ids[parsed.connect.connect_id] = parsed.connect.dest_id
                    if self.dest_id is None:
                        self.src_id = parsed.connect.connect_id
                        self.dest_id = parsed.connect.dest_id
                        self.word4 = int(connect_lane["word4"])
                        self.word8 = int(connect_lane["word8"])
                        self.local_id = int(connect_lane["local_id"])
                        self.remote_id = int(connect_lane["remote_id"])
                    if not bool(connect_lane["setup_probe_sent"]):
                        self._send_wrapped_setup_probe(
                            connect_lane,
                            connect_id=parsed.connect.connect_id,
                            dest_id=parsed.connect.dest_id,
                        )
                    self._dbg(
                        "connect_ok",
                        connect_id=hex(parsed.connect.connect_id),
                        dest_id=hex(parsed.connect.dest_id),
                        active_src_id=hex(self.src_id),
                    )
                    self._connected.set()
                continue

            if parsed.data is not None and not parsed.data.is_ack and parsed.data.payload:
                self._queue_payload(
                    parsed.data.payload,
                    source="wrapped_quii",
                    packet_type_flag=parsed.data.packet_type_flag,
                    command=parsed.data.command,
                    seq=parsed.data.seq,
                    dest_id=parsed.data.dest_id,
                    src_id=parsed.data.src_id,
                )
            elif parsed.data is not None and parsed.data.is_ack and parsed.data.seq == 0:
                ack_lane = self._lane_for_src_id(parsed.data.dest_id)
                if ack_lane is not None:
                    ack_lane["quii_setup_acked"] = True
                self._dbg(
                    "recv_quii_setup_ack",
                    seq=hex(parsed.data.seq),
                    dest_id=hex(parsed.data.dest_id),
                    src_id=hex(parsed.data.src_id),
                )
                self._quii_setup_acked.set()

    def _receive_loop(self):
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
            if marker == 0xFFABEFC1:
                if len(data) >= 0x20:
                    status_word = int.from_bytes(data[0x14:0x18], "little")
                    inner_marker = int.from_bytes(data[0x1C:0x20], "little")
                    if (
                        status_word == 0x00001900
                        and inner_marker == 0xFFFFFFFF
                        and len(data) >= 0x24
                    ):
                        inner_total_length = int.from_bytes(data[0x20:0x24], "little")
                        direct_end = 0x1C + inner_total_length
                        if direct_end > len(data):
                            if self._start_wrapped_fragment_stream(data):
                                continue
                    if status_word == 0x00000500 and inner_marker != 0xFFFFFFFF:
                        payload = data[0x1C:]
                        is_filler = bool(payload) and all(byte == 0xBB for byte in payload)
                        if not is_filler and self._append_wrapped_fragment_stream(data):
                            continue
                        after_play = self._quii_play_sent.is_set()
                        log_label = "recv_stream_payload" if after_play else "recv_stream_payload_early"
                        if is_filler:
                            log_label += "_filler"
                        if after_play:
                            if is_filler:
                                self.stream_payload_filler_count += 1
                            else:
                                self.stream_payload_count += 1
                        else:
                            if is_filler:
                                self.stream_payload_early_filler_count += 1
                            else:
                                self.stream_payload_early_count += 1
                        self._dbg(
                            log_label,
                            packet_len=len(data),
                            payload_len=len(payload),
                            word4=hex(int.from_bytes(data[0x04:0x08], "little")),
                            word8=hex(int.from_bytes(data[0x08:0x0C], "little")),
                            local_id=int.from_bytes(data[0x0C:0x10], "little"),
                            remote_id=int.from_bytes(data[0x10:0x14], "little"),
                            prefix=payload[:32].hex(),
                        )
                        if after_play and not is_filler:
                            self._queue_payload(
                                payload,
                                source="stream_payload",
                                packet_len=len(data),
                                payload_len=len(payload),
                                word4=int.from_bytes(data[0x04:0x08], "little"),
                                word8=int.from_bytes(data[0x08:0x0C], "little"),
                                local_id=int.from_bytes(data[0x0C:0x10], "little"),
                                remote_id=int.from_bytes(data[0x10:0x14], "little"),
                            )
                        continue
                    if status_word == 0x00001900 and inner_marker != 0xFFFFFFFF:
                        if self._append_wrapped_fragment_stream(data):
                            continue
                        payload = data[0x1C:]
                        after_play = self._quii_play_sent.is_set()
                        self._dbg(
                            "recv_direct_quii_blob",
                            packet_len=len(data),
                            payload_len=len(payload),
                            word4=hex(int.from_bytes(data[0x04:0x08], "little")),
                            word8=hex(int.from_bytes(data[0x08:0x0C], "little")),
                            local_id=int.from_bytes(data[0x0C:0x10], "little"),
                            remote_id=int.from_bytes(data[0x10:0x14], "little"),
                            prefix=payload[:32].hex(),
                        )
                        if after_play and payload:
                            self._queue_payload(
                                payload,
                                source="direct_quii_blob",
                                packet_len=len(data),
                                payload_len=len(payload),
                                word4=int.from_bytes(data[0x04:0x08], "little"),
                                word8=int.from_bytes(data[0x08:0x0C], "little"),
                                local_id=int.from_bytes(data[0x0C:0x10], "little"),
                                remote_id=int.from_bytes(data[0x10:0x14], "little"),
                            )
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
            if marker != 0xFFABEFC1:
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

    def start(self):
        if self._udp_sock is None:
            raise RuntimeError("RB UDP tunnel requires an existing UDP socket")
        self._dbg(
            "start",
            peer=self._peer_addr,
            transport_peer=self._transport_peer_addr,
            p2p_session_flag=self._p2p_session_flag,
        )
        self._udp_sock.settimeout(0.5)
        self._thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._thread.start()
        self._play_sync_thread = threading.Thread(target=self._play_sync_loop, daemon=True)
        self._play_sync_thread.start()
        lan_same_peer = (
            self._peer_addr == self._transport_peer_addr
            and is_private_ipv4(self._peer_addr[0])
        )
        if lan_same_peer:
            self._prime_lan_transport()
            deadline = time.time() + 1.5
            while time.time() < deadline and self._transport_frames_seen == 0:
                time.sleep(0.05)
        self._send_control_bootstrap()
        threading.Thread(target=self._keepalive_loop, daemon=True).start()
        if not self._connected.wait(self.config.connect_timeout):
            raise TimeoutError("timed out waiting for RB UDP logical connect response")
        self._quii_ready.wait(0.5)

    def _keepalive_loop(self):
        local_udp_port = self._udp_sock.getsockname()[1]
        time.sleep(1.0)
        while not self._stop.is_set():
            try:
                lan_same_peer = (
                    self._peer_addr == self._transport_peer_addr
                    and is_private_ipv4(self._peer_addr[0])
                )
                if not lan_same_peer:
                    packet = build_p2p_active_packet(
                        session_flag=self._p2p_session_flag,
                        seq=random.randrange(0x100000000),
                        local_udp_port=local_udp_port,
                        tail_code=3,
                    )
                    self._send_transport_udp(packet)
                sent_established = False
                for lane in self._lane_states:
                    if int(lane["local_id"]) and int(lane["remote_id"]):
                        sent_established = True
                        if not bool(lane["established_sent"]):
                            self._send_control_established(lane)
                if not sent_established and self._bootstrap_sent_to != self._peer_addr:
                    self._send_control_bootstrap()
            except Exception:
                pass
            time.sleep(1.0)

    def send_quii_setup(self, seq: int = 0):
        if self.dest_id is None:
            raise RuntimeError("tunnel is not connected")
        for lane, dest_id in self._connected_lane_destinations():
            src_id = int(lane["src_id"])
            inner = build_direct_quii_setup_rb(src_id=src_id, dest_id=dest_id, seq=seq)
            self._dbg(
                "send_quii_setup",
                src_id=hex(src_id),
                dest_id=hex(dest_id),
                seq=seq,
                lane_word4=hex(int(lane["word4"])),
                lane_word8=hex(int(lane["word8"])),
            )
            self._send_wrapped(inner, tag8=self.DATA_TAG, lane=lane)

    def send_quii_play(self, credentials: RuntimeCredentials, *, seq: int = 1):
        if self.dest_id is None:
            raise RuntimeError("tunnel is not connected")
        while True:
            try:
                self._data.get_nowait()
            except queue.Empty:
                break
        path = build_quii_live_path(
            channel=self.config.channel,
            stream=self.config.stream,
            ap=2,
            inner=False,
            newcn=False,
            connect_mode=self.config.connect_mode,
        )
        lane_profiles = [
            {"packet_type": 0x01, "ext_len_low": 0x01, "ext_len_high": 0x00, "play_param": 0x01, "stream_flag": 0x00},
            {"packet_type": 0x0B, "ext_len_low": 0xFF, "ext_len_high": 0xFF, "play_param": 0x00, "stream_flag": 0x00},
        ]
        self._quii_play_sent.set()
        for index, (lane, dest_id) in enumerate(self._connected_lane_destinations()):
            src_id = int(lane["src_id"])
            profile = lane_profiles[min(index, len(lane_profiles) - 1)]
            play_tag = self.QUII_PLAY_TAGS[min(index, len(self.QUII_PLAY_TAGS) - 1)]
            inner = build_direct_quii_play_oem_rb(
                "adminapp",
                credentials.dynamic_password,
                self.config.oem,
                src_id=src_id,
                dest_id=dest_id,
                seq=seq,
                packet_type=int(profile["packet_type"]),
                ext_len_low=int(profile["ext_len_low"]),
                ext_len_high=int(profile["ext_len_high"]),
                play_param=int(profile["play_param"]),
                stream_flag=int(profile["stream_flag"]),
                crypto_mode=2,
                key=credentials.data_encode_key,
                encrypt=True,
            )
            self._dbg(
                "send_quii_play",
                src_id=hex(src_id),
                dest_id=hex(dest_id),
                seq=seq,
                connect_mode=self.config.connect_mode,
                oem=self.config.oem,
                path=path,
                packet_type=hex(int(profile["packet_type"])),
                ext_len_low=hex(int(profile["ext_len_low"])),
                ext_len_high=hex(int(profile["ext_len_high"])),
                play_param=hex(int(profile["play_param"])),
                tag8=play_tag.hex(),
                lane_word4=hex(int(lane["word4"])),
                lane_word8=hex(int(lane["word8"])),
                local_id=int(lane["local_id"]),
                remote_id=int(lane["remote_id"]),
                payload_len=len(inner),
                payload_prefix=inner[:48].hex(),
            )
            self._send_wrapped(inner, tag8=play_tag, lane=lane)

    def wait_quii_setup_ack(self, timeout: float = 3.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            lane_pairs = self._connected_lane_destinations()
            if lane_pairs and all(bool(lane["quii_setup_acked"]) for lane, _dest_id in lane_pairs):
                return True
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            self._quii_setup_acked.wait(min(0.1, remaining))
        return False

    def recv_packet(self, timeout: float = 5.0) -> dict[str, Any]:
        return self._data.get(timeout=timeout)

    def recv_payload(self, timeout: float = 5.0) -> bytes:
        packet = self.recv_packet(timeout=timeout)
        return bytes(packet["payload"])

    def _emit_active_fragment_streams(self) -> None:
        if not self._wrapped_fragment_streams:
            return
        for stream in list(self._wrapped_fragment_streams.values()):
            payload = bytes(stream["payload"])
            missing = max(0, int(stream["inner_total_length"]) - len(payload))
            self._dbg(
                "emit_wrapped_fragment_partial",
                word4=hex(int(stream["word4"])),
                word8=hex(int(stream["word8"])),
                start_local_id=int(stream["start_local_id"]),
                next_local_id=int(stream["next_local_id"]),
                have=len(payload),
                need=int(stream["inner_total_length"]),
                missing=missing,
            )
            self._queue_payload(
                payload,
                source="wrapped_fragment_partial",
                word4=int(stream["word4"]),
                word8=int(stream["word8"]),
                start_local_id=int(stream["start_local_id"]),
                next_local_id=int(stream["next_local_id"]),
                remote_id=int(stream["remote_id"]),
                have=len(payload),
                need=int(stream["inner_total_length"]),
                missing=missing,
            )
        self._wrapped_fragment_streams.clear()

    def flush_fragment_partials(self) -> None:
        self._emit_active_fragment_streams()

    def close(self):
        self._stop.set()
        self._emit_active_fragment_streams()
        if self._udp_sock is not None:
            try:
                self._udp_sock.close()
            except Exception:
                pass


DirectKcpQuiiTunnel = RbUdpQuiiTunnel


def open_direct_preview(
    config: AutonomousConfig,
    *,
    credentials: RuntimeCredentials | None = None,
) -> tuple[RuntimeCredentials, P2PConnectResponse, ParsedP2PTestResponse, DirectKcpQuiiTunnel]:
    if not config.ust_address or not config.ust_test_address:
        populate_discovered_services(config)

    credentials = credentials or fetch_runtime_credentials(config.device_id, ip_region_id=config.ip_region_id)
    rng = random.Random(config.rng_seed)
    public_ip = discover_public_ip()
    local_ips = discover_local_ips()
    print(f"[NetInfo] public_ip={public_ip} local_ips={local_ips}")
    udp_sock = make_dualstack_udp_socket()
    local_udp_port = udp_sock.getsockname()[1]
    public_udp_port = local_udp_port

    if config.log_peer_diagnostics:
        print(
            "[P2PDiag] response_candidates_pending",
            {
                "local_udp_port": local_udp_port,
                "local_ips": local_ips,
            },
        )

    response: P2PConnectResponse | None = None
    request_session_id: int | None = None
    session_flag: str | None = None
    last_mqtt_exc: Exception | None = None

    for attempt_index in range(config.p2pconnect_retries):
        request_counter = rng.randrange(0x10000)
        current_request_session_id = create_request_session_id(request_counter, rng=rng)
        if config.session_flag_server_ip and config.session_flag_server_port is not None:
            current_session_flag = create_session_flag(
                config.session_flag_server_ip,
                config.session_flag_server_port,
                request_counter,
                config.device_id,
                rng=rng,
            )
        else:
            current_session_flag = f"{rng.randrange(0x100000000):08x}{int(time.time())}"

        reset_mqtt_runtime(config)
        ensure_mqtt_runtime(config)
        request = P2PConnectRequest(
            client_id=config.client_id or credentials.raw["login"].get("client_id", "") or "",
            client_type=config.client_type,
            oem=config.oem,
            app=config.app_id,
            device_id=config.device_id,
            session_flag=current_session_flag,
            request_session_id=current_request_session_id,
            mon_channel=-1,
            force_trans=config.force_trans,
            dev_type="normal",
            dev_sub_state="awakened",
            userdata=config.mqtt_userdata,
        )

        mqtt_bootstrap = MqttP2PBootstrap(config)
        try:
            mqtt_bootstrap.connect()
            mqtt_bootstrap.publish_unregister()
            time.sleep(0.1)
            mqtt_bootstrap.publish_register()
            mqtt_bootstrap.wait_for_command("register", config.mqtt_timeout)
            try:
                state = mqtt_bootstrap.wait_for_device_online(
                    config.device_id,
                    timeout=config.prewarm_timeout,
                    retry_interval=config.prewarm_retry_interval,
                )
                print(
                    "[Prewarm] device online",
                    {
                        "device_ids": state.device_ids,
                        "online": state.online,
                        "offline": state.offline,
                        "usrkey": state.usrkey,
                    },
                )
            except TimeoutError as exc:
                print(f"[Prewarm] online wait timeout: {exc}")
            mqtt_bootstrap.publish_p2pconnect(request)
            current_response = mqtt_bootstrap.wait_p2pconnect_response(current_session_flag, config.mqtt_timeout)
            mqtt_bootstrap.publish_update_netinfo(
                public_ip=public_ip,
                public_udp_port=public_udp_port,
                local_ips=local_ips,
                local_udp_port=local_udp_port,
            )
            if not _has_probe_targets(current_response):
                print(
                    "[P2PDiag] empty_p2pconnect_response",
                    {
                        "attempt": attempt_index + 1,
                        "response_local_ips": current_response.local_ips,
                        "response_local_udp_port": current_response.local_udp_port,
                        "public_ip": current_response.public_ip,
                        "public_udp_port": current_response.public_udp_port,
                        "utd_public_ip": current_response.utd_public_ip,
                        "utd_public_udp_port": current_response.utd_public_udp_port,
                    },
                )
                raise RuntimeError("empty p2pconnect response without probe targets")
            if config.preconnect_settle_delay > 0:
                print(f"[Prewarm] settle delay {config.preconnect_settle_delay:.1f}s before UDP probe")
                time.sleep(config.preconnect_settle_delay)
            response = current_response
            request_session_id = current_request_session_id
            session_flag = current_session_flag
            break
        except Exception as exc:
            last_mqtt_exc = exc
        finally:
            mqtt_bootstrap.close()

    if response is None or request_session_id is None or session_flag is None:
        udp_sock.close()
        if last_mqtt_exc is not None:
            raise last_mqtt_exc
        raise RuntimeError("failed to establish p2pconnect session")

    if config.log_peer_diagnostics:
        print(
            "[P2PDiag] p2pconnect_response",
            {
                "response_local_ips": response.local_ips,
                "response_local_udp_port": response.local_udp_port,
                "public_peer": _format_peer((response.public_ip or "", int(response.public_udp_port or 0))),
                "trans_peer": _format_peer((response.utd_public_ip or "", int(response.utd_public_udp_port or 0))),
                "probe_targets": _format_probe_targets(response),
            },
        )

    test_response = run_udp_probe(
        sock=udp_sock,
        response=response,
        request_session_id=request_session_id,
        target_session_flag=session_flag,
        ust_test_address=config.ust_test_address,
        timeout=config.udp_timeout,
        rng=rng,
    )
    if config.log_peer_diagnostics:
        print(
            "[P2PDiag] udp_probe_selected",
            {
                "test_peer": f"{test_response.address}:{test_response.port}",
                "test_id": test_response.test_id,
                "status_code": test_response.status_code,
                "result_code": test_response.result_code,
            },
        )
    if is_private_ipv4(test_response.address):
        transport_peer_addr = (test_response.address, test_response.port)
        peer_addr = transport_peer_addr
        print(f"[P2PActive] skip for LAN peer {peer_addr}")
        if config.log_peer_diagnostics:
            print(
                "[P2PDiag] peer_selection",
                {
                    "selection_mode": "lan_direct_from_udp_probe",
                    "transport_peer": _format_peer(transport_peer_addr),
                    "logic_peer": _format_peer(peer_addr),
                },
            )
    else:
        transport_peer_addr, _seen_requests = run_p2p_active_handshake(
            sock=udp_sock,
            session_flag=session_flag,
            timeout=config.udp_timeout,
            rng=rng,
            peer_hint=(test_response.address, test_response.port),
        )
        selection = describe_logic_peer_selection(response, transport_peer_addr)
        peer_addr = select_preferred_logic_peer(response, transport_peer_addr)
        if config.log_peer_diagnostics:
            print(
                "[P2PDiag] peer_selection",
                {
                    "selection_mode": "transport_then_logic_select",
                    "transport_peer": _format_peer(transport_peer_addr),
                    **selection,
                },
            )
    udp_sock.settimeout(None)

    tunnel = DirectKcpQuiiTunnel(
        config,
        response,
        test_response,
        request_session_id,
        udp_sock=udp_sock,
        peer_addr=peer_addr,
        transport_peer_addr=transport_peer_addr,
        p2p_session_flag=session_flag,
    )
    tunnel.start()
    return credentials, response, test_response, tunnel
