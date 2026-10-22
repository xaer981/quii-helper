import asyncio
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import quii_helper
from quii_helper import AutonomousConfig, Camera
from quii_helper.config.settings_loader import has_default_settings_cache


def test_import_does_not_read_settings_touch_files_or_remove_host_sinks(
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text("CAMERA_APP_ID=invalid\n", encoding="utf-8")
    code = """
from pathlib import Path
from unittest.mock import patch
from loguru import logger
messages = []
logger.remove()
sink = logger.add(lambda message: messages.append(str(message)))
with patch('dotenv.dotenv_values', side_effect=AssertionError('dotenv read')), \\
     patch('dotenv.load_dotenv', side_effect=AssertionError('dotenv load')), \\
     patch('pathlib.Path.mkdir', side_effect=AssertionError('directory write')), \\
     patch('socket.socket.connect', side_effect=AssertionError('network')), \\
     patch('threading.Thread.start', side_effect=AssertionError('thread')):
    from quii_helper import Camera
    from quii_helper.config.settings_loader import has_default_settings_cache
    assert not has_default_settings_cache()
logger.info('host sink survived')
logger.remove(sink)
assert len(messages) == 1 and 'host sink survived' in messages[0]
assert not Path('data').exists() and not Path('assets').exists()
"""
    root = str(Path(quii_helper.__file__).parents[1])
    code = f"import sys; sys.path.insert(0, {root!r})\n" + code
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_explicit_camera_config_isolated_from_env_file_and_process_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CAMERA_APP_ID", "invalid")
    (tmp_path / ".env").write_text("CAMERA_APP_ID=invalid\n", encoding="utf-8")
    config = AutonomousConfig(device_host="192.0.2.10", app_id=17)
    camera = Camera(config=config)
    assert camera.config.app_id == 17
    assert camera.config.device_host == "192.0.2.10"


def test_camera_process_defaults_are_loaded_per_instance_without_dotenv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("CAMERA_APP_ID=invalid\n", encoding="utf-8")
    monkeypatch.setenv("CAMERA_APP_ID", "17")
    first = Camera()
    monkeypatch.setenv("CAMERA_APP_ID", "18")
    second = Camera()
    assert first.config.app_id == 17
    assert second.config.app_id == 18
    assert not has_default_settings_cache()


def test_camera_instances_do_not_mutate_a_shared_input_config() -> None:
    config = AutonomousConfig()
    first = Camera(config)
    second = Camera(config)
    first.config.mqtt_userdata = "first-session"
    assert second.config.mqtt_userdata is None
    assert config.mqtt_userdata is None


def test_entrance_bot_style_async_adapter_sends_one_local_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    camera = Camera(
        AutonomousConfig(
            device_host="192.0.2.10",
            auth_code="test-auth",
            unlock_password="test-unlock",
            channel=1,
        )
    )
    with (
        patch(
            "quii_helper.device.control.request_cgi",
            return_value={
                "raw": "<envelope><body><error>0</error></body></envelope>"
            },
        ) as sender,
        patch.object(
            camera.connector,
            "fetch_credentials",
            side_effect=AssertionError("cloud"),
        ),
        patch.object(
            camera.connector,
            "open_preview",
            side_effect=AssertionError("preview"),
        ),
        patch(
            "quii_helper.protocols.ust.crypto_tables._read_p2p_crypto_tables",
            side_effect=AssertionError("asset read"),
        ),
    ):
        result = asyncio.run(
            asyncio.to_thread(camera.open_door, password_mode="sha256")
        )
    assert result.accepted
    assert sender.call_count == 1
    assert sender.call_args.kwargs["allow_redirects"] is False
    assert not camera.data_dir.exists()
    assert not camera.config.assets_dir.exists()
