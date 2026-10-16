import importlib
from unittest.mock import patch

import pytest

from quii_helper import CameraDoorOpenResult


class ExampleModuleTests:
    def test_discover_env_values_module_is_importable(self) -> None:
        module = importlib.import_module("examples.discover_env_values")

        assert "/auth/user" == module.USERAUTH_PATH
        assert callable(module.main)

    @pytest.mark.parametrize("interrupted", [False, True])
    def test_main_serves_rtsp_without_opening_door(
        self, interrupted: bool
    ) -> None:
        module = importlib.import_module("quii_helper.main")
        with patch.object(module, "Camera", autospec=True) as camera_cls:
            camera = camera_cls.return_value
            context = camera.serve_rtsp.return_value
            stream = context.__enter__.return_value
            if interrupted:
                stream.wait.side_effect = KeyboardInterrupt
                with pytest.raises(KeyboardInterrupt):
                    module.main()
            else:
                module.main()

        camera_cls.assert_called_once_with(
            stream_quality="high", live_newcn=True, tls_verify=False
        )
        camera.serve_rtsp.assert_called_once_with(port=8554)
        stream.wait.assert_called_once_with()
        context.__exit__.assert_called_once()
        camera.open_door.assert_not_called()
        camera.get_device_info.assert_not_called()

    def test_open_door_example_requires_explicit_main_call(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with patch("quii_helper.Camera", autospec=True) as camera_cls:
            module = importlib.import_module("examples.open_door")
            camera_cls.assert_not_called()
            camera = camera_cls.return_value
            camera.get_device_info.return_value.supports_sha256_password = True
            camera.open_door.return_value = CameraDoorOpenResult(0, 1, 1)

            with patch.object(module, "Camera", camera_cls):
                module.main()

        camera_cls.assert_called_once_with()
        camera.get_device_info.assert_called_once_with()
        camera.open_door.assert_called_once_with(password_mode="auto")
        camera.serve_rtsp.assert_not_called()
        output = capsys.readouterr().out
        assert "Capability 24 (TYPE_ENCRYPY_SHA256): True" in output
        assert "Accepted: True; message: Door-open command accepted" in output
