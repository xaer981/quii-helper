from hashlib import sha256
from pathlib import Path
from struct import unpack_from

from quii_helper.support.errors import AssetMissingError

P2P_TABLE1_FILE_OFFSET = 0x6A5C27
P2P_TABLE2_FILE_OFFSET = 0x6A6C27
P2P_TABLE3_FILE_OFFSET = 0x6A7C27
P2P_TABLE_SIZE = 0x1000
# GenerateSourceData() in the verified vHome 2.2 arm64-v8a library.
P2P_TABLE_SHA256 = (
    "44d524b21bab5137d8f6f14d7206bcb0b3a06b8558906292efb6e6678acf6bea",
    "9cbefb328bd7954ae6ff15efe165bb411eef004bd4e31fe880881fc697d5b2a5",
    "66c652d1d1a41c5e72945c1d16eb9950584b7ea1354b7f85be68e263e8e9d391",
)


def load_p2p_crypto_tables(
    so_path: str | Path | None = None,
    *,
    assets_dir: str | Path | None = None,
) -> tuple[bytes, bytes, bytes]:
    """Read tables from an explicit file or the application's asset directory."""
    if so_path is not None:
        return _read_p2p_crypto_tables(Path(so_path))

    errors: list[str] = []
    root = Path(assets_dir) if assets_dir is not None else Path("assets")
    root = root.expanduser().resolve()
    for candidate in (
        root / "libqv-p2p-v2.so",
        root / "lib" / "arm64-v8a" / "libqv-p2p-v2.so",
    ):
        try:
            return _read_p2p_crypto_tables(candidate)
        except AssetMissingError as exc:
            errors.append(f"{candidate}: {exc}")

    details = "; ".join(errors) if errors else "no candidates configured"
    raise AssetMissingError(
        "unable to load P2P crypto tables from libqv-p2p-v2.so; "
        "put the extracted arm64-v8a libqv-p2p-v2.so into assets/; "
        f"{details}"
    )


def _read_p2p_crypto_tables(so_path: Path) -> tuple[bytes, bytes, bytes]:
    try:
        with so_path.open("rb") as source:
            header = source.read(64)
            if (
                len(header) != 64
                or header[:7] != b"\x7fELF\x02\x01\x01"
                or unpack_from("<HH", header, 16) != (3, 183)
            ):
                raise AssetMissingError(
                    f"unsupported P2P asset {so_path}; expected an ELF64 "
                    "little-endian AArch64 shared library (arm64-v8a)"
                )
            tables = []
            for offset in (
                P2P_TABLE1_FILE_OFFSET,
                P2P_TABLE2_FILE_OFFSET,
                P2P_TABLE3_FILE_OFFSET,
            ):
                source.seek(offset)
                tables.append(source.read(P2P_TABLE_SIZE))
    except OSError as exc:
        raise AssetMissingError(
            f"unable to read P2P crypto table asset {so_path}: {exc}"
        ) from exc
    if any(len(table) != P2P_TABLE_SIZE for table in tables):
        raise AssetMissingError(f"incomplete P2P crypto tables in {so_path}")
    if (
        tuple(sha256(table).hexdigest() for table in tables)
        != P2P_TABLE_SHA256
    ):
        raise AssetMissingError(
            f"unsupported P2P crypto table layout in {so_path}; "
            "use the verified vHome 2.2 arm64-v8a library; other builds "
            "require native layout verification"
        )
    return tables[0], tables[1], tables[2]
