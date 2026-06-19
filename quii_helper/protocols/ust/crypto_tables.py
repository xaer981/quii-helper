from pathlib import Path

P2P_SO_CANDIDATES = (
    Path(r"D:\apk\vhome\vhome_clear\lib\arm64-v8a\libqv-p2p-v2.so"),
    Path(r"D:\apk\vhome\vhome_clear\lib\armeabi-v7a\libqv-p2p-v2.so"),
)
P2P_TABLE1_FILE_OFFSET = 0x6A5C27
P2P_TABLE2_FILE_OFFSET = 0x6A6C27
P2P_TABLE3_FILE_OFFSET = 0x6A7C27
P2P_TABLE_SIZE = 0x1000


def load_p2p_crypto_tables(
    so_path: str | Path | None = None,
) -> tuple[bytes, bytes, bytes]:
    candidates = (
        [Path(so_path)] if so_path is not None else list(P2P_SO_CANDIDATES)
    )
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            blob = Path(candidate).read_bytes()
            return (
                blob[
                    P2P_TABLE1_FILE_OFFSET : P2P_TABLE1_FILE_OFFSET
                    + P2P_TABLE_SIZE
                ],
                blob[
                    P2P_TABLE2_FILE_OFFSET : P2P_TABLE2_FILE_OFFSET
                    + P2P_TABLE_SIZE
                ],
                blob[
                    P2P_TABLE3_FILE_OFFSET : P2P_TABLE3_FILE_OFFSET
                    + P2P_TABLE_SIZE
                ],
            )
        except Exception as exc:
            last_error = exc
    raise FileNotFoundError(
        f"unable to load libqv-p2p-v2.so "
        f"tables from candidates={candidates!r};"
        f"last_error={last_error}"
    )
