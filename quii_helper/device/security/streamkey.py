from typing import Any

from quii_helper.device.cgi.client import COMMAND_GET_STREAM_KEY_INFO
from quii_helper.device.cgi.parser import (
    parse_cgi_response,
    parse_stream_key_info,
)
from quii_helper.device.http.transport import request_cgi


def request_streamkey(**kwargs: Any) -> dict[str, str]:
    result = request_cgi(COMMAND_GET_STREAM_KEY_INFO, **kwargs)
    if result["error"] != "0":
        raise RuntimeError(f"device error: {result['error']}")

    info = parse_stream_key_info(
        parse_cgi_response(COMMAND_GET_STREAM_KEY_INFO, result["raw"])
    )
    return {
        "key": info.key,
        "tdc": info.tdc,
        "synctime": info.sync_time,
    }
