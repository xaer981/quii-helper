import json
from typing import Any

from quii_helper.protocols.p2p.models import (
    P2PConnectResponse,
    ParsedKcpParams,
    ParsedSubDeviceState,
)


def maybe_int(value: Any) -> int | None:
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


def parse_p2pconnect_response(
    data: dict[str, Any] | str
) -> P2PConnectResponse:
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
        result_code=(
            str(result.get("code")) if result.get("code") is not None else None
        ),
        result_message=result.get("msg") or result.get("message"),
        device_id=content.get("devid"),
        session_flag=content.get("session-flag"),
        response_session_id=maybe_int(content.get("resp-session-id")),
        nettype=maybe_int(content.get("nettype")),
        netsubtype=maybe_int(content.get("netsubtype")),
        public_ip=content.get("pub-ip"),
        public_udp_port=maybe_int(content.get("pub-udpport")),
        local_udp_port=maybe_int(content.get("loc-udpport")),
        local_ips=[str(value) for value in local_ips if value is not None],
        utd_public_ip=content.get("utd-pub-ip"),
        utd_public_udp_port=maybe_int(content.get("utd-pub-udpport")),
        kcp_params=ParsedKcpParams(
            mode=str(kcp_raw.get("mode", "normal")).replace("nomal", "normal"),
            sndwnd=maybe_int(kcp_raw.get("sndwnd")),
            rcvwnd=maybe_int(kcp_raw.get("rcvwnd")),
            nodelay=maybe_int(kcp_raw.get("nodelay")),
            interval=maybe_int(kcp_raw.get("interval")),
            resend=maybe_int(kcp_raw.get("resend")),
            nc=maybe_int(kcp_raw.get("nc")),
            rto=maybe_int(kcp_raw.get("rto")),
            fastresend=maybe_int(kcp_raw.get("fastresend")),
            mtu=maybe_int(kcp_raw.get("mtu")),
        ),
    )


def parse_sub_device_state_response(
    data: dict[str, Any] | str
) -> ParsedSubDeviceState:
    if isinstance(data, str):
        data = json.loads(data)

    content = data.get("content", data)
    if not isinstance(content, dict):
        raise ValueError(
            "sub-device-state payload does not contain content object"
        )

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
