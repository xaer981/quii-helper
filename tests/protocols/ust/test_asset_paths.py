from hashlib import sha256
from pathlib import Path
from struct import pack_into
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from quii_helper import AutonomousConfig
from quii_helper.protocols.mqtt import bootstrap
from quii_helper.protocols.ust import credentials, crypto_tables
from quii_helper.protocols.ust.key_derivation import derive_ust_aes_key
from quii_helper.support.errors import AssetMissingError


def _write_tables(path: Path, value: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = bytearray(
        crypto_tables.P2P_TABLE3_FILE_OFFSET + crypto_tables.P2P_TABLE_SIZE
    )
    blob[:7] = b"\x7fELF\x02\x01\x01"
    pack_into("<HH", blob, 16, 3, 183)
    for offset in (
        crypto_tables.P2P_TABLE1_FILE_OFFSET,
        crypto_tables.P2P_TABLE2_FILE_OFFSET,
        crypto_tables.P2P_TABLE3_FILE_OFFSET,
    ):
        blob[offset : offset + crypto_tables.P2P_TABLE_SIZE] = (
            bytes([value]) * crypto_tables.P2P_TABLE_SIZE
        )
    path.write_bytes(blob)


def _trust_synthetic_tables(
    monkeypatch: pytest.MonkeyPatch, value: int
) -> None:
    digest = sha256(bytes([value]) * crypto_tables.P2P_TABLE_SIZE).hexdigest()
    monkeypatch.setattr(crypto_tables, "P2P_TABLE_SHA256", (digest,) * 3)


def test_asset_directories_do_not_share_global_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, value in (("first", 1), ("second", 2)):
        root = tmp_path / name
        _write_tables(root / "libqv-p2p-v2.so", value)
    _trust_synthetic_tables(monkeypatch, 1)
    first = crypto_tables.load_p2p_crypto_tables(assets_dir=tmp_path / "first")
    _trust_synthetic_tables(monkeypatch, 2)
    second = crypto_tables.load_p2p_crypto_tables(
        assets_dir=tmp_path / "second"
    )
    assert first[0] == bytes([1]) * crypto_tables.P2P_TABLE_SIZE
    assert second[0] == bytes([2]) * crypto_tables.P2P_TABLE_SIZE


def test_asset_directory_preserves_native_key_derivation_and_layout_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "native"
    path = root / "lib" / "arm64-v8a" / "libqv-p2p-v2.so"
    _write_tables(path, 3)
    _trust_synthetic_tables(monkeypatch, 3)
    (root / "libqv-p2p-v2.so").write_bytes(b"incomplete")
    assert derive_ust_aes_key(
        "test-client", assets_dir=root
    ) == derive_ust_aes_key("test-client", so_path=path)


@pytest.mark.parametrize(
    ("offset", "replacement"),
    [(0, b"NOPE"), (4, b"\x01"), (5, b"\x02"), (16, b"\x02"), (18, b"\x3e")],
)
def test_unsupported_elf_is_rejected(tmp_path, offset, replacement):
    path = tmp_path / "libqv-p2p-v2.so"
    _write_tables(path, 1)
    with path.open("r+b") as source:
        source.seek(offset)
        source.write(replacement)
    with pytest.raises(AssetMissingError, match="expected an ELF64"):
        crypto_tables.load_p2p_crypto_tables(so_path=path)


@pytest.mark.parametrize("value", [0, 1, 255])
def test_wrong_build_tables_are_rejected(tmp_path, value):
    path = tmp_path / "libqv-p2p-v2.so"
    _write_tables(path, value)
    with pytest.raises(AssetMissingError, match="native layout verification"):
        crypto_tables.load_p2p_crypto_tables(so_path=path)


@pytest.mark.parametrize("table_index", [0, 1, 2])
def test_each_table_fingerprint_is_checked(tmp_path, monkeypatch, table_index):
    path = tmp_path / "libqv-p2p-v2.so"
    _write_tables(path, 1)
    _trust_synthetic_tables(monkeypatch, 1)
    with path.open("r+b") as source:
        source.seek(
            crypto_tables.P2P_TABLE1_FILE_OFFSET + table_index * 0x1000
        )
        source.write(b"\x02")
    with pytest.raises(
        AssetMissingError, match="unsupported P2P crypto table"
    ):
        crypto_tables.load_p2p_crypto_tables(so_path=path)


def test_truncated_tables_are_rejected(tmp_path):
    path = tmp_path / "libqv-p2p-v2.so"
    _write_tables(path, 1)
    with path.open("r+b") as source:
        source.truncate(crypto_tables.P2P_TABLE3_FILE_OFFSET + 100)
    with pytest.raises(
        AssetMissingError, match="incomplete P2P crypto tables"
    ):
        crypto_tables.load_p2p_crypto_tables(so_path=path)


def test_mqtt_credentials_forward_the_selected_asset_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decode = MagicMock(return_value=b"decoded")
    monkeypatch.setattr(credentials, "decrypt_ust_ciphertext", decode)
    parsed = SimpleNamespace(
        mqtt_username="user", mqtt_password="password", sver="1.0.0"
    )
    assert credentials.decode_ust_mqtt_credentials(
        parsed, srcid="client", assets_dir=tmp_path
    ) == ("decoded", "decoded")
    assert decode.call_count == 2
    assert all(
        call.kwargs["assets_dir"] == tmp_path for call in decode.call_args_list
    )


def test_mqtt_bootstrap_uses_its_own_camera_assets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = AutonomousConfig(
        assets_dir=tmp_path,
        client_id="test-client",
        ust_address="mqtts://broker.example:8883",
    )
    client = MagicMock()
    monkeypatch.setattr(
        bootstrap.mqtt, "Client", MagicMock(return_value=client)
    )
    decode = MagicMock(return_value=(None, None))
    monkeypatch.setattr(bootstrap, "decode_ust_mqtt_credentials", decode)
    session = bootstrap.MqttP2PBootstrap(config)
    session._connected.set()
    session.connect()
    assert decode.call_args.kwargs["assets_dir"] == tmp_path
    assert client.tls_set.call_args.kwargs["ca_certs"] == str(
        tmp_path / "ca.pem"
    )
