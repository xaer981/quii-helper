import xml.etree.ElementTree as ET
from typing import Any

from quii_helper.device.http.transport import request_cgi


def request_streamkey(**kwargs: Any) -> dict[str, str]:
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
