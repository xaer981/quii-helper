"""Desktop audio bridge and managed conversation lifecycle; no callback I/O."""

import math
import sys
import time
from array import array
from collections.abc import Callable, Generator
from threading import Condition, Event, Lock, Thread, current_thread

from quii_helper.camera.streaming.talk import CameraTalkSession
from quii_helper.media.audio.devices import open_duplex_device
from quii_helper.media.audio.g711 import decode_g711
from quii_helper.protocols.tcp.talk.packets import PCM_FRAME_BYTES
from quii_helper.support.errors import (
    AudioDeviceError,
    ConfigurationError,
    QuiiConnectionError,
)
from quii_helper.support.log import logger

MAX_BUFFER_BYTES = 3200  # 200ms of PCM16, 8000 Hz mono, per direction.
MAX_CALLBACK_BYTES = 16000


class _AudioBuffers:
    """Bounded, sample-aligned real-time buffers shared with native audio I/O."""

    def __init__(self) -> None:
        self.condition = Condition()
        self.stopped = Event()
        self.error: Exception | None = None
        self.capture = bytearray()
        self.playback = bytearray()
        self.dropped_capture = self.dropped_playback = 0

    def append(self, buffer: bytearray, pcm: bytes) -> int:
        """Keep only the newest 200ms; caller holds condition."""
        overflow = max(0, len(buffer) + len(pcm) - MAX_BUFFER_BYTES)
        if overflow:
            del buffer[:overflow]
        buffer.extend(pcm[-MAX_BUFFER_BYTES:])
        return overflow

    def fail(self, error: Exception) -> None:
        """Preserve the first failure and wake sender/monitor."""
        with self.condition:
            if self.error is None:
                self.error = error
            self.stopped.set()
            self.condition.notify_all()

    def callback(self) -> Generator[bytes, object, None]:
        """Exchange native-endian PCM; errors are reported outside the C callback."""
        samples = yield b""
        while not self.stopped.is_set():
            output = b""
            try:
                if isinstance(samples, array) and samples.typecode == "h":
                    samples = samples.tobytes()
                if (
                    not isinstance(samples, (bytes, bytearray))
                    or len(samples) % 2
                    or len(samples) > MAX_CALLBACK_BYTES
                ):
                    raise AudioDeviceError(
                        "Invalid PCM block from audio device"
                    )
                pcm = bytes(samples)
                if sys.byteorder != "little":
                    values = array("h", pcm)
                    values.byteswap()
                    pcm = values.tobytes()
                with self.condition:
                    self.dropped_capture += self.append(self.capture, pcm)
                    count = len(pcm)
                    output = bytes(self.playback[:count])
                    del self.playback[:count]
                    self.condition.notify_all()
                output += bytes(count - len(output))
                if sys.byteorder != "little":
                    values = array("h", output)
                    values.byteswap()
                    output = values.tobytes()
            except Exception as exc:
                self.fail(exc)
            samples = yield output

    def send(self, talk: CameraTalkSession) -> None:
        """Send hardware-clocked 40ms blocks; discard stale complete backlog."""
        try:
            while not self.stopped.is_set():
                with self.condition:
                    self.condition.wait_for(
                        lambda: self.stopped.is_set()
                        or len(self.capture) >= PCM_FRAME_BYTES
                    )
                    if self.stopped.is_set():
                        return
                    size = (
                        len(self.capture) // PCM_FRAME_BYTES * PCM_FRAME_BYTES
                    )
                    start = size - PCM_FRAME_BYTES
                    self.dropped_capture += start
                    pcm = bytes(self.capture[start:size])
                    del self.capture[:size]
                talk._send_captured_pcm(pcm)
        except Exception as exc:
            if not self.stopped.is_set():
                self.fail(exc)

    def receive(self, talk: CameraTalkSession) -> None:
        """Decode selected-panel G.711 into the bounded speaker buffer."""
        try:
            while not self.stopped.is_set():
                try:
                    frame = talk.recv_frame(timeout=0.1)
                except TimeoutError:
                    continue
                pcm = decode_g711(frame.data, frame.codec)
                with self.condition:
                    self.dropped_playback += self.append(self.playback, pcm)
        except Exception as exc:
            if not self.stopped.is_set():
                self.fail(exc)


def converse(
    open_talk: Callable[[], CameraTalkSession],
    *,
    input_device: str | None = None,
    output_device: str | None = None,
    duration_seconds: float | None = None,
    stop_event: Event | None = None,
    on_ready: Callable[[], None] | None = None,
) -> None:
    """Own local audio and talk until Ctrl+C, stop_event, duration or failure.

    Devices are prepared before TCP, but recording starts only after talk is
    ready. A device failure terminates the session; no recording or automatic
    retry is performed. Headphones are recommended: no AEC is provided.
    """
    if duration_seconds is not None and (
        isinstance(duration_seconds, bool)
        or not isinstance(duration_seconds, (int, float))
        or not math.isfinite(duration_seconds)
        or duration_seconds <= 0
    ):
        raise ConfigurationError(
            "duration_seconds must be finite and positive"
        )
    if stop_event is not None and not isinstance(stop_event, Event):
        raise ConfigurationError("stop_event must be a threading.Event")
    if stop_event is not None and stop_event.is_set():
        return
    device = open_duplex_device(input_device, output_device)
    buffers = _AudioBuffers()
    callback = buffers.callback()
    next(callback)
    talk: CameraTalkSession | None = None
    workers: list[Thread] = []
    try:
        logger.info("Connecting conversation; microphone is not recording yet")
        talk = open_talk()
        if stop_event is not None and stop_event.is_set():
            return
        for name, target in (
            ("send", buffers.send),
            ("receive", buffers.receive),
        ):
            worker = Thread(
                target=target,
                args=(talk,),
                name=f"quii-conversation-{name}",
                daemon=True,
            )
            worker.start()
            workers.append(worker)
        try:
            device.start(callback)
        except Exception as exc:
            raise AudioDeviceError(
                "Could not start microphone/speaker"
            ) from exc
        logger.info("Conversation active. Microphone on")
        if on_ready is not None:
            on_ready()
        deadline = (
            None
            if duration_seconds is None
            else time.monotonic() + duration_seconds
        )
        while True:
            if buffers.error is not None:
                raise buffers.error
            if stop_event is not None and stop_event.is_set():
                break
            if deadline is not None and time.monotonic() >= deadline:
                break
            if not device.running:
                raise AudioDeviceError(
                    "Microphone/speaker stopped unexpectedly"
                )
            buffers.stopped.wait(0.05)
    finally:
        primary_error = sys.exc_info()[1]
        buffers.stopped.set()
        with buffers.condition:
            buffers.condition.notify_all()
        cleanup_error: Exception | None = None
        audio_closed = False
        for close in (device.close, talk.close if talk is not None else None):
            if close is None:
                continue
            try:
                close()
                if close == device.close:
                    audio_closed = True
            except Exception as exc:
                cleanup_error = cleanup_error or exc
        deadline = time.monotonic() + 1
        for worker in workers:
            worker.join(timeout=max(0, deadline - time.monotonic()))
        if audio_closed:
            callback.close()
        with buffers.condition:
            buffers.capture.clear()
            buffers.playback.clear()
        logger.debug(
            "Conversation dropped PCM bytes: capture={} playback={}",
            buffers.dropped_capture,
            buffers.dropped_playback,
        )
        if cleanup_error is not None:
            logger.warning("Conversation resource cleanup failed")
            if primary_error is None:
                raise AudioDeviceError(
                    "Conversation cleanup failed"
                ) from cleanup_error
        else:
            logger.info("Conversation stopped. Microphone off")


class CameraConversationSession:
    """Active computer audio returned by preview.start_talk(); owns no preview.

    start_talk() waits for readiness and returns this handle. close() stops
    microphone/playback and talk only; the parent preview remains live.
    wait() reports asynchronous audio/talk errors. No automatic retry occurs.
    """

    def __init__(
        self,
        talk: CameraTalkSession,
        *,
        input_device: str | None = None,
        output_device: str | None = None,
        on_close: Callable[["CameraConversationSession"], None],
    ) -> None:
        self._talk = talk
        self._input_device = input_device
        self._output_device = output_device
        self._on_close = on_close
        self._stop_event = Event()
        self._ready = Event()
        self._done = Event()
        self._error: BaseException | None = None
        self._thread: Thread | None = None
        self._lock = Lock()

    @property
    def active(self) -> bool:
        """Whether audio started and no cancellation or termination occurred."""
        return (
            self._ready.is_set()
            and not self._stop_event.is_set()
            and not self._done.is_set()
        )

    @property
    def error(self) -> BaseException | None:
        """First asynchronous failure, or None; also raised by wait()."""
        return self._error

    def _start(self) -> "CameraConversationSession":
        """Start once and wait interruptibly for device and talk readiness."""
        try:
            with self._lock:
                if self._stop_event.is_set():
                    raise AudioDeviceError(
                        "Conversation was stopped during startup"
                    )
                self._thread = Thread(
                    target=self._run,
                    name="quii-session-conversation",
                    daemon=True,
                )
                self._thread.start()
            while not self._ready.wait(0.05):
                if self._done.is_set():
                    self.wait(timeout=0)
                    raise AudioDeviceError(
                        "Conversation stopped before audio became ready"
                    )
            if self._done.is_set() or self._stop_event.is_set():
                self.wait(timeout=0)
                raise AudioDeviceError("Conversation stopped during startup")
            return self
        except BaseException as exc:
            if (
                self._error is None
                and not self._stop_event.is_set()
                and isinstance(exc, Exception)
            ):
                self._error = exc
            try:
                self.close()
            except Exception:
                logger.warning(
                    "Conversation cleanup failed after startup error"
                )
            raise

    def _run(self) -> None:
        try:
            converse(
                self._talk.open,
                input_device=self._input_device,
                output_device=self._output_device,
                stop_event=self._stop_event,
                on_ready=self._ready.set,
            )
        except BaseException as exc:
            if not self._stop_event.is_set() or not isinstance(
                exc, QuiiConnectionError
            ):
                self._error = exc
        finally:
            self._stop_event.set()
            try:
                self._on_close(self)
            finally:
                self._done.set()

    def wait(self, timeout: float | None = None) -> None:
        """Wait for termination and report errors; a timeout leaves audio active."""
        if timeout is not None and (not math.isfinite(timeout) or timeout < 0):
            raise ValueError("timeout must be finite and nonnegative")
        deadline = None if timeout is None else time.monotonic() + timeout
        while not self._done.is_set():
            remaining = (
                0.05
                if deadline is None
                else min(0.05, deadline - time.monotonic())
            )
            if remaining <= 0:
                break
            self._done.wait(remaining)
        if self._error is not None:
            raise self._error

    def close(self) -> None:
        """Cancel startup/active audio and join its worker, leaving preview alone."""
        self._stop_event.set()
        try:
            self._talk.close()
        finally:
            with self._lock:
                worker = self._thread
            if worker is not None and worker.ident is not None:
                if worker is not current_thread():
                    worker.join(timeout=2)
                    if worker.is_alive():
                        raise AudioDeviceError(
                            "Conversation worker did not stop"
                        )
            else:
                self._done.set()
                self._on_close(self)

    def __enter__(self) -> "CameraConversationSession":
        """Return the already active handle without opening another session."""
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Stop local audio/talk when leaving the block."""
        self.close()
