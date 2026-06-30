import json
from typing import Any

from quii_helper.protocols.p2p.models import ParsedKcpParams

KCP_PARAM_FIELDS = (
    "sndwnd",
    "rcvwnd",
    "nodelay",
    "interval",
    "resend",
    "nc",
    "rto",
    "fastresend",
    "mtu",
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


def decoded_json_object(data: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(data, str):
        decoded = json.loads(data)
        if not isinstance(decoded, dict):
            raise ValueError("expected JSON object")
        return decoded
    return data


def content_or_self(data: dict[str, Any]) -> Any:
    return data.get("content", data)


def list_of_strings(value: Any, *, omit_none_items: bool = False) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        if omit_none_items:
            value = [item for item in value if item is not None]
        return [str(item) for item in value]
    return [str(value)]


def parse_kcp_params(kcp_raw: dict[str, Any]) -> ParsedKcpParams:
    values = {
        field: maybe_int(kcp_raw.get(field)) for field in KCP_PARAM_FIELDS
    }
    return ParsedKcpParams(
        mode=str(kcp_raw.get("mode", "normal")).replace("nomal", "normal"),
        **values,
    )


def result_code_value(result: dict[str, Any]) -> str | None:
    code = result.get("code")
    return str(code) if code is not None else None


def result_message_value(result: dict[str, Any]) -> Any:
    return result.get("msg") or result.get("message")
