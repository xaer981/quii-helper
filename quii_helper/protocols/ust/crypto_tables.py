from pathlib import Path

from quii_helper.constants import P2P_SO_PATHS

P2P_SO_CANDIDATES = P2P_SO_PATHS
P2P_TABLE1_FILE_OFFSET = 0x6A5C27
P2P_TABLE2_FILE_OFFSET = 0x6A6C27
P2P_TABLE3_FILE_OFFSET = 0x6A7C27
P2P_TABLE_SIZE = 0x1000


def load_p2p_crypto_tables(
    so_path: str | Path | None = None,
) -> tuple[bytes, bytes, bytes]:
    if so_path is not None:
        return _read_p2p_crypto_tables(Path(so_path))

    errors: list[str] = []
    for candidate in P2P_SO_CANDIDATES:
        try:
            return _read_p2p_crypto_tables(candidate)
        except Exception as exc:
            errors.append(f"{candidate}: {exc}")

    details = "; ".join(errors) if errors else "no candidates configured"
    raise FileNotFoundError(
        "unable to load P2P crypto tables from libqv-p2p-v2.so; "
        "put the extracted arm64-v8a libqv-p2p-v2.so into assets/; "
        f"{details}"
    )


def _read_p2p_crypto_tables(so_path: Path) -> tuple[bytes, bytes, bytes]:
    blob = so_path.read_bytes()
    tables = (
        blob[P2P_TABLE1_FILE_OFFSET : P2P_TABLE1_FILE_OFFSET + P2P_TABLE_SIZE],
        blob[P2P_TABLE2_FILE_OFFSET : P2P_TABLE2_FILE_OFFSET + P2P_TABLE_SIZE],
        blob[P2P_TABLE3_FILE_OFFSET : P2P_TABLE3_FILE_OFFSET + P2P_TABLE_SIZE],
    )
    if any(len(table) != P2P_TABLE_SIZE for table in tables):
        raise ValueError(f"incomplete P2P crypto tables in {so_path}")
    return tables
