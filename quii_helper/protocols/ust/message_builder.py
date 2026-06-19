import json
from typing import Any


def build_ust_header(
    *,
    command: str,
    client_id: str,
    client_type: str | int | None = None,
    oem: str | None = None,
    app: str | int | None = None,
    version: str = "v3.2.0",
    flag: str = "tdkcloud",
    userdata: str | None = None,
    seq: str | None = None,
    session: str | None = None,
) -> dict[str, Any]:
    client: dict[str, Any] = {"id": client_id}
    if client_type is not None:
        client["type"] = str(client_type)
    if oem is not None:
        client["oem"] = oem
    if app is not None:
        client["app"] = str(app)

    header: dict[str, Any] = {
        "flag": flag,
        "version": version,
        "command": command,
        "client": client,
    }
    if seq:
        header["seq"] = seq
    if session:
        header["session"] = session
    if userdata:
        header["userdata"] = userdata
    return header


def dump_ust_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
