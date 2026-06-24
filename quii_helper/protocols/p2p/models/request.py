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
