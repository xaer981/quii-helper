from typing import Any

from quii_helper.protocols.p2p.codec.json_state import (
    content_or_self,
    decoded_json_object,
    list_of_strings,
    maybe_int,
    parse_kcp_params,
    result_code_value,
    result_message_value,
)
from quii_helper.protocols.p2p.models import (
    P2PConnectResponse,
    ParsedSubDeviceState,
)

__all__ = [
    "maybe_int",
    "parse_p2pconnect_response",
    "parse_sub_device_state_response",
]


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
    data = decoded_json_object(data)
    content = content_or_self(data)
    result = content.get("result") or {}
    kcp_raw = content.get("kcpParam") or {}

    return P2PConnectResponse(
        result_code=result_code_value(result),
        result_message=result_message_value(result),
        device_id=content.get("devid"),
        session_flag=content.get("session-flag"),
        response_session_id=maybe_int(content.get("resp-session-id")),
        nettype=maybe_int(content.get("nettype")),
        netsubtype=maybe_int(content.get("netsubtype")),
        public_ip=content.get("pub-ip"),
        public_udp_port=maybe_int(content.get("pub-udpport")),
        local_udp_port=maybe_int(content.get("loc-udpport")),
        local_ips=list_of_strings(
            content.get("loc-ip"),
            omit_none_items=True,
        ),
        utd_public_ip=content.get("utd-pub-ip"),
        utd_public_udp_port=maybe_int(content.get("utd-pub-udpport")),
        kcp_params=parse_kcp_params(kcp_raw),
    )


def parse_sub_device_state_response(
    data: dict[str, Any] | str
) -> ParsedSubDeviceState:
    data = decoded_json_object(data)
    content = content_or_self(data)
    if not isinstance(content, dict):
        raise ValueError(
            "sub-device-state payload does not contain content object"
        )

    state_r = content.get("state-r") or {}
    state_s = content.get("state-s") or {}

    usrkeys = list_of_strings(state_r.get("usrkey"))
    return ParsedSubDeviceState(
        device_ids=list_of_strings(content.get("devices")),
        registered=list_of_strings(state_r.get("register")),
        unregistered=list_of_strings(state_r.get("unregister")),
        online=list_of_strings(state_s.get("aonline")),
        offline=list_of_strings(state_s.get("aoffline")),
        usrkey=usrkeys[0] if usrkeys else None,
        raw=data,
    )
