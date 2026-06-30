from dataclasses import dataclass


@dataclass(frozen=True)
class RtspRequest:
    method: str
    uri: str
    version: str
    cseq: str
    headers: dict[str, str]


def parse_request(request_text: str) -> RtspRequest | None:
    lines = [line for line in request_text.split("\r\n") if line]
    if not lines:
        return None
    parts = lines[0].split()
    if len(parts) != 3:
        return None

    headers = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        headers[name.strip().lower()] = value.strip()

    return RtspRequest(
        method=parts[0],
        uri=parts[1],
        version=parts[2],
        cseq=headers.get("cseq", "0"),
        headers=headers,
    )
