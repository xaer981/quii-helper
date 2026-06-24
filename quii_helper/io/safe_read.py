from pathlib import Path


def read_existing_bytes(path: str | Path) -> bytes:
    path = Path(path)
    if not path.exists():
        return b""
    try:
        return path.read_bytes()
    except Exception:
        return b""
