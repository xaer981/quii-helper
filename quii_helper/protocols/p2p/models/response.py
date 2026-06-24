from dataclasses import dataclass, field
from typing import Any


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
