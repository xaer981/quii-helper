import json
from dataclasses import dataclass, field
from typing import Any


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
            for key in (
                "sndwnd",
                "rcvwnd",
                "nodelay",
                "interval",
                "resend",
                "nc",
                "rto",
                "fastresend",
                "mtu",
            ):
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
        return json.dumps(
            self.to_dict(), separators=(",", ":"), ensure_ascii=False
        )


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


__all__ = [
    "KcpParams",
    "P2PConnectRequest",
    "P2PConnectResponse",
    "P2PTestTarget",
    "ParsedKcpParams",
    "ParsedP2PTestResponse",
    "ParsedP2PTransportFrame",
    "ParsedSubDeviceState",
]
