"""The interactive example must not use real audio or camera resources in CI."""

from unittest.mock import MagicMock, Mock

import pytest

from examples import converse


def test_device_listing_needs_no_credentials_or_camera(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["converse", "--list-devices"])
    monkeypatch.setattr(
        converse,
        "list_audio_devices",
        lambda: {"input": ["Mic"], "output": ["Headset"]},
    )
    camera, saved = Mock(), Mock()
    monkeypatch.setattr(converse, "Camera", camera)
    monkeypatch.setattr(converse, "CameraStreamCredentials", saved)
    converse.main()
    assert capsys.readouterr().out == "input: Mic\noutput: Headset\n"
    camera.assert_not_called()
    saved.load.assert_not_called()


@pytest.mark.parametrize("interrupted", [False, True])
def test_example_uses_saved_lan_settings_and_selected_devices(
    monkeypatch, interrupted
):
    monkeypatch.setattr(
        "sys.argv",
        [
            "converse",
            "--channel",
            "2",
            "--seconds",
            "3",
            "--input-device",
            "Mic",
            "--output-device",
            "Headset",
        ],
    )
    camera, saved = MagicMock(), Mock()
    session = (
        camera.return_value.serve_rtsp.return_value.__enter__.return_value
    )
    handle = session.start_talk.return_value
    handle.wait.side_effect = KeyboardInterrupt if interrupted else None
    monkeypatch.setattr(converse, "Camera", camera)
    monkeypatch.setattr(converse, "CameraStreamCredentials", saved)
    monkeypatch.setattr(converse, "load_config", lambda: "local settings")
    monkeypatch.setattr(converse, "configure_logging", Mock())
    monkeypatch.setattr("builtins.input", lambda _: "")
    converse.main()
    saved.load.assert_called_once_with("data/stream_credentials.json")
    assert camera.call_args.kwargs["connection_mode"] == "lan"
    assert camera.call_args.kwargs["channel"] == 2
    camera.return_value.serve_rtsp.assert_called_once_with(
        port=8554, audio=False
    )
    session.start_talk.assert_called_once_with(
        input_device="Mic",
        output_device="Headset",
    )
    session.stop_talk.assert_called_once()
    assert handle.wait.call_args_list[0].kwargs == {"timeout": 3.0}
    camera.return_value.converse.assert_not_called()


def test_interactive_example_waits_for_confirmation_before_microphone(
    monkeypatch,
):
    monkeypatch.setattr("sys.argv", ["converse"])
    camera, saved = MagicMock(), Mock()
    session = (
        camera.return_value.serve_rtsp.return_value.__enter__.return_value
    )
    monkeypatch.setattr(converse, "Camera", camera)
    monkeypatch.setattr(converse, "CameraStreamCredentials", saved)
    monkeypatch.setattr(converse, "load_config", lambda: "local settings")
    monkeypatch.setattr(converse, "configure_logging", Mock())
    prompts = []

    def confirm(prompt):
        if not prompts:
            camera.return_value.serve_rtsp.assert_called_once()
            session.start_talk.assert_not_called()
        else:
            session.start_talk.assert_called_once()
            session.stop_talk.assert_not_called()
        prompts.append(prompt)
        return ""

    monkeypatch.setattr("builtins.input", confirm)
    converse.main()
    assert len(prompts) == 2
    session.stop_talk.assert_called_once()
    session.wait.assert_called_once()


@pytest.mark.parametrize("duration", ["0", "-2", "nan", "inf"])
def test_invalid_duration_never_loads_credentials_or_opens_preview(
    monkeypatch, duration
):
    monkeypatch.setattr("sys.argv", ["converse", f"--seconds={duration}"])
    camera, saved = Mock(), Mock()
    monkeypatch.setattr(converse, "Camera", camera)
    monkeypatch.setattr(converse, "CameraStreamCredentials", saved)
    with pytest.raises(SystemExit):
        converse.main()
    camera.assert_not_called()
    saved.load.assert_not_called()
