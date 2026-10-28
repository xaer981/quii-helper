"""Optional desktop audio boundary; importing this module opens no devices."""

from importlib import import_module
from typing import Any, Callable, Generator, Protocol, cast

from quii_helper.support.errors import AudioDeviceError, ConfigurationError


class DuplexDevice(Protocol):
    """The small part of miniaudio needed by the conversation coordinator."""

    running: bool
    backend: str
    stop_callback: Callable[[], None] | None

    def start(self, callback: Generator[bytes, object, None]) -> None:
        """Start an already primed duplex callback, with signed PCM16 samples."""

    def close(self) -> None:
        """Stop capture/playback and release native resources."""


def _audio_module() -> Any:
    """Load the optional dependency only after an explicit audio operation."""
    try:
        return import_module("miniaudio")
    except ImportError as exc:
        raise ConfigurationError(
            'Computer audio requires: python -m pip install "quii-helper[audio]"'
        ) from exc


def list_audio_devices() -> dict[str, list[str]]:
    """Enumerate microphone/output names without starting audio capture."""
    audio = _audio_module()
    try:
        devices = audio.Devices()
        return {
            "input": [device["name"] for device in devices.get_captures()],
            "output": [device["name"] for device in devices.get_playbacks()],
        }
    except Exception as exc:
        raise AudioDeviceError(
            "Could not enumerate local audio devices"
        ) from exc


def open_duplex_device(
    input_device: str | None, output_device: str | None
) -> DuplexDevice:
    """Initialize 8kHz mono PCM16 I/O, without starting the microphone.

    miniaudio converts native device rates/layouts. Explicit names must match
    exactly one device; None uses the OS default. Never accept a silent NULL
    backend as successful hardware initialization.
    """
    audio = _audio_module()
    for name in (input_device, output_device):
        if name is not None and (
            not isinstance(name, str) or not name.strip()
        ):
            raise ConfigurationError(
                "Audio device names must be nonempty strings"
            )

    def select(devices: list[dict[str, Any]], name: str) -> Any:
        matches = [device for device in devices if device["name"] == name]
        if len(matches) != 1:
            raise ConfigurationError(
                "Audio device name is missing or ambiguous; "
                "use python -m examples.converse --list-devices"
            )
        return matches[0]["id"]

    try:
        capture_id = playback_id = None
        if input_device is not None or output_device is not None:
            devices = audio.Devices()
            if input_device is not None:
                capture_id = select(devices.get_captures(), input_device)
            if output_device is not None:
                playback_id = select(devices.get_playbacks(), output_device)
        device = cast(
            DuplexDevice,
            audio.DuplexStream(
                playback_format=audio.SampleFormat.SIGNED16,
                playback_channels=1,
                capture_format=audio.SampleFormat.SIGNED16,
                capture_channels=1,
                sample_rate=8000,
                buffersize_msec=40,
                playback_device_id=playback_id,
                capture_device_id=capture_id,
                app_name="quii-helper conversation",
            ),
        )
        if device.backend.lower() == "null":
            device.close()
            raise AudioDeviceError(
                "No physical microphone/playback backend available"
            )
        # miniaudio only updates running on device-stop when a callback exists.
        device.stop_callback = lambda: None
        return device
    except (ConfigurationError, AudioDeviceError):
        raise
    except Exception as exc:
        raise AudioDeviceError(
            "Could not initialize microphone/speaker; check devices and OS permissions"
        ) from exc
