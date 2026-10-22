from dataclasses import dataclass

MAX_HEADER_BYTES = 16 * 1024
MAX_BODY_BYTES = 64 * 1024


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
    if len(parts) != 3 or parts[2] != "RTSP/1.0":
        return None

    headers = {}
    for line in lines[1:]:
        if ":" not in line:
            return None
        name, value = line.split(":", 1)
        name = name.strip().lower()
        if not name or name in headers:
            return None
        headers[name] = value.strip()

    cseq = headers.get("cseq", "0")
    if not cseq.isascii() or not cseq.isdecimal() or len(cseq) > 20:
        return None

    return RtspRequest(
        method=parts[0],
        uri=parts[1],
        version=parts[2],
        cseq=cseq,
        headers=headers,
    )


class RtspRequestBuffer:
    """Frame bounded RTSP requests and skip interleaved RTP/RTCP frames."""

    def __init__(self) -> None:
        self.pending = b""

    def feed(self, chunk: bytes) -> list[str]:
        """Return complete headers, consuming their bodies before the next request."""
        self.pending += chunk
        requests = []
        while self.pending:
            if self.pending.startswith(b"$"):
                if len(self.pending) < 4:
                    break
                size = 4 + int.from_bytes(self.pending[2:4], "big")
                if len(self.pending) < size:
                    break
                self.pending = self.pending[size:]
                continue
            end = self.pending.find(b"\r\n\r\n")
            if end < 0:
                if len(self.pending) > MAX_HEADER_BYTES:
                    raise ValueError("RTSP header too large")
                break
            if end + 4 > MAX_HEADER_BYTES:
                raise ValueError("RTSP header too large")
            text = self.pending[:end].decode("latin1")
            request = parse_request(text)
            if request is None:
                raise ValueError("Malformed RTSP request")
            length = request.headers.get("content-length", "0")
            if (
                not length.isascii()
                or not length.isdecimal()
                or len(length) > 10
            ):
                raise ValueError("Invalid RTSP Content-Length")
            body_size = int(length)
            if body_size > MAX_BODY_BYTES:
                raise ValueError("RTSP body too large")
            size = end + 4 + body_size
            if len(self.pending) < size:
                break
            requests.append(text)
            self.pending = self.pending[size:]
        return requests
