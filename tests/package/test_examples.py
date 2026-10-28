import importlib
import re
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, sentinel

import pytest

from quii_helper import CameraDoorOpenResult


class ExampleModuleTests:
    @pytest.mark.parametrize("document", ["README.md", "docs/api.md"])
    def test_documented_rtsp_example_waits_and_reports_producer_failure(
        self, document
    ):
        root = Path(__file__).resolve().parents[2]
        blocks = re.findall(
            r"```python\n(.*?)\n```",
            (root / document).read_text(encoding="utf-8"),
            re.DOTALL,
        )
        source = next(
            block
            for block in blocks
            if "camera.serve_rtsp(" in block
            and "session.start_talk(" not in block
        )
        with (
            patch("quii_helper.Camera", autospec=True) as camera_cls,
            patch("quii_helper.CameraStreamCredentials", autospec=True),
            patch("quii_helper.load_config", return_value=sentinel.config),
            patch(
                "builtins.input",
                side_effect=AssertionError("must wait for producer"),
            ),
        ):
            context = camera_cls.return_value.serve_rtsp.return_value
            stream = context.__enter__.return_value
            failure = RuntimeError("synthetic producer failure")
            stream.wait.side_effect = failure
            with pytest.raises(RuntimeError) as error:
                exec(compile(source, document, "exec"), {})
            assert error.value is failure
            stream.wait.assert_called_once_with()
            context.__exit__.assert_called_once()
            camera_cls.return_value.open_door.assert_not_called()

    @pytest.mark.parametrize(
        "failure", [None, RuntimeError("talk failed"), KeyboardInterrupt()]
    )
    def test_documented_shared_conversation_stops_talk_on_every_exit(
        self, failure
    ):
        root = Path(__file__).resolve().parents[2]
        blocks = re.findall(
            r"```python\n(.*?)\n```",
            (root / "docs/api.md").read_text(encoding="utf-8"),
            re.DOTALL,
        )
        source = next(
            block for block in blocks if "session.start_talk()" in block
        )
        camera, session = Mock(), Mock()
        context = MagicMock()
        context.__enter__.return_value = session
        camera.serve_rtsp.return_value = context
        session.start_talk.return_value.wait.side_effect = failure
        if failure is not None:
            with pytest.raises(type(failure)):
                exec(
                    compile(source, "docs/api.md", "exec"), {"camera": camera}
                )
        else:
            exec(compile(source, "docs/api.md", "exec"), {"camera": camera})
            session.wait.assert_called_once_with()
        camera.serve_rtsp.assert_called_once_with(port=8554)
        session.start_talk.assert_called_once_with()
        session.stop_talk.assert_called_once_with()
        context.__exit__.assert_called_once()
        camera.talk.assert_not_called()
        camera.converse.assert_not_called()

    def test_discover_env_values_module_is_importable(self) -> None:
        module = importlib.import_module("examples.discover_env_values")

        assert "/auth/user" == module.USERAUTH_PATH
        assert callable(module.main)

    @pytest.mark.parametrize("interrupted", [False, True])
    def test_main_serves_rtsp_without_opening_door(
        self, interrupted: bool
    ) -> None:
        module = importlib.import_module("quii_helper.main")
        with (
            patch.object(module, "Camera", autospec=True) as camera_cls,
            patch.object(
                module, "load_config", return_value=sentinel.config
            ) as load,
            patch.object(module, "configure_logging") as configure,
        ):
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
            config=sentinel.config,
            tls_verify=False,
        )
        load.assert_called_once_with()
        configure.assert_called_once_with(replace_existing=True)
        camera.serve_rtsp.assert_called_once_with(port=8554, audio=True)
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

            with (
                patch.object(module, "Camera", camera_cls),
                patch.object(
                    module, "load_config", return_value=sentinel.config
                ),
                patch.object(module, "configure_logging"),
            ):
                module.main()

        camera_cls.assert_called_once_with(
            config=sentinel.config, connection_mode="cloud"
        )
        camera.get_device_info.assert_called_once_with()
        camera.open_door.assert_called_once_with(password_mode="auto")
        camera.serve_rtsp.assert_not_called()
        output = capsys.readouterr().out
        assert "Capability 24 (TYPE_ENCRYPY_SHA256): True" in output
        assert "Accepted: True; message: Door-open command accepted" in output
