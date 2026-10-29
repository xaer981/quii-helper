"""Device boundary tests never initialize the host microphone or speakers."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from quii_helper import AudioDeviceError, ConfigurationError
from quii_helper.media.audio import devices


@pytest.fixture
def audio(monkeypatch):
    module = Mock()
    module.SampleFormat = SimpleNamespace(SIGNED16="signed16")
    module.DuplexStream.return_value.backend = "fixture"
    module.Devices.return_value.get_captures.return_value = [
        {"name": "Headset microphone", "id": 11}
    ]
    module.Devices.return_value.get_playbacks.return_value = [
        {"name": "Headphones", "id": 22}
    ]
    monkeypatch.setattr(devices, "_audio_module", lambda: module)
    return module


def test_defaults_prepare_but_do_not_start_audio(audio):
    device = devices.open_duplex_device(None, None)
    kwargs = audio.DuplexStream.call_args.kwargs
    assert kwargs["sample_rate"] == 8000
    assert kwargs["capture_channels"] == kwargs["playback_channels"] == 1
    assert kwargs["capture_format"] == kwargs["playback_format"] == "signed16"
    assert kwargs["buffersize_msec"] == 40
    assert kwargs["capture_device_id"] is kwargs["playback_device_id"] is None
    audio.Devices.assert_not_called()
    device.start.assert_not_called()
    assert callable(device.stop_callback)


def test_explicit_names_select_exact_devices(audio):
    devices.open_duplex_device("Headset microphone", "Headphones")
    kwargs = audio.DuplexStream.call_args.kwargs
    assert (kwargs["capture_device_id"], kwargs["playback_device_id"]) == (
        11,
        22,
    )


@pytest.mark.parametrize("name", ["", "  ", 123, "missing"])
def test_invalid_name_never_initializes_hardware(audio, name):
    with pytest.raises(ConfigurationError):
        devices.open_duplex_device(name, None)
    audio.DuplexStream.assert_not_called()


def test_ambiguous_names_fail_instead_of_picking_wrong_microphone(audio):
    audio.Devices.return_value.get_captures.return_value *= 2
    with pytest.raises(ConfigurationError, match="ambiguous"):
        devices.open_duplex_device("Headset microphone", None)
    audio.DuplexStream.assert_not_called()


def test_null_backend_closed_and_rejected(audio):
    audio.DuplexStream.return_value.backend = "Null"
    with pytest.raises(AudioDeviceError, match="No physical"):
        devices.open_duplex_device(None, None)
    audio.DuplexStream.return_value.close.assert_called_once()


def test_local_init_and_enumeration_failures_are_domain_errors(audio):
    audio.DuplexStream.side_effect = RuntimeError("denied")
    with pytest.raises(AudioDeviceError) as result:
        devices.open_duplex_device(None, None)
    assert isinstance(result.value.__cause__, RuntimeError)
    audio.Devices.side_effect = RuntimeError("no devices")
    with pytest.raises(AudioDeviceError):
        devices.list_audio_devices()


def test_listing_only_enumerates(audio):
    assert devices.list_audio_devices() == {
        "input": ["Headset microphone"],
        "output": ["Headphones"],
    }
    audio.DuplexStream.assert_not_called()


def test_missing_extra_has_actionable_message(monkeypatch):
    def missing(name):
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(devices, "import_module", missing)
    with pytest.raises(ConfigurationError, match=r"quii-helper\[audio\]"):
        devices._audio_module()
