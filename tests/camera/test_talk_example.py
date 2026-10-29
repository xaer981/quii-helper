"""The active example is exercised with an injected fake camera only."""

import wave
from contextlib import nullcontext
from unittest.mock import Mock

import pytest

from examples.talk import send_wav


def write_wav(path, *, channels=1, rate=8000, width=2, frames=8010):
    with wave.open(str(path), "wb") as file:
        file.setnchannels(channels)
        file.setsampwidth(width)
        file.setframerate(rate)
        file.writeframes(b"\x01" * frames * channels * width)


def test_example_streams_bounded_batches_and_explicitly_pads_tail(tmp_path):
    path = tmp_path / "talk.wav"
    write_wav(path)
    camera, talk = Mock(), Mock()
    camera.talk.return_value = nullcontext(talk)
    send_wav(camera, path)
    camera.talk.assert_called_once_with()
    assert [len(call.args[0]) for call in talk.send_pcm.call_args_list] == [
        16000,
        640,
    ]
    assert talk.send_pcm.call_args.args[0] == b"\x01" * 20 + bytes(620)


@pytest.mark.parametrize(
    "kwargs", [{"channels": 2}, {"rate": 16000}, {"width": 1}, {"frames": 0}]
)
def test_example_rejects_wrong_format_before_connecting(tmp_path, kwargs):
    path = tmp_path / "talk.wav"
    write_wav(path, **kwargs)
    camera = Mock()
    with pytest.raises(ValueError):
        send_wav(camera, path)
    camera.talk.assert_not_called()
