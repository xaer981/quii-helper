"""Bounded two-connection audio: preview receives, generic talk transmits."""

import math
import time
from collections import deque
from dataclasses import dataclass, field
from threading import Condition, Event, Lock, Thread, current_thread
from typing import Any

from quii_helper.media.audio import CameraAudioFrame
from quii_helper.media.audio.g711 import encode_g711
from quii_helper.media.frames.cframe_pack import QuiiCFramePack
from quii_helper.protocols.tcp.live.session import (
    MAX_TCP_PAYLOAD_BYTES,
    LanTcpSession,
)
from quii_helper.protocols.tcp.talk.packets import (
    FRAME_SECONDS,
    PCM_FRAME_BYTES,
)
from quii_helper.protocols.tcp.talk.session import LanTalkSession
from quii_helper.support.errors import QuiiConnectionError

MAX_RECEIVED_FRAMES = 64
MAX_PCM_BYTES = 25 * PCM_FRAME_BYTES
MAX_AUDIO_FRAME_BYTES = 65535


@dataclass
class _SendBatch:
    pcm: bytes = field(repr=False)
    offset: int = 0
    next_send: float = 0.0
    live: bool = False


class CameraTalkSession:
    """A context-managed active talk session returned by Camera.talk().

    PCM input is signed 16-bit little-endian, 8000 Hz mono. send_pcm() blocks
    while one 40ms-1000ms batch is transmitted at real-time speed; one producer
    is supported. recv_frame() returns encoded audio from a separate preview
    of the selected panel. Talk uses generic selector 65535, not that panel id.
    No microphone, speaker, resampler, cloud or automatic reconnect is used.

    Half-duplex is the default: talk-side reception is disabled during each
    send batch and restored afterwards, matching SDK push-to-talk. Preview is
    drained in both modes. full_duplex=True skips those talk-side toggles;
    neither mode guarantees hardware duplex or echo cancellation.
    Slow consumers lose the oldest of 64 received frames; dropped_frames makes
    that explicit. This is a real-time conversation API, not lossless capture.

    When preview is None, the RTSP owner supplies completed audio frames from
    its existing packer. No preview reader is created or closed by this handle.
    """

    def __init__(
        self,
        session: LanTalkSession,
        *,
        preview: LanTcpSession | None = None,
        full_duplex: bool = False,
    ) -> None:
        if not isinstance(full_duplex, bool):
            raise ValueError("full_duplex must be a boolean")
        self._session = session
        self._preview = preview
        self.full_duplex = full_duplex
        self._condition = Condition()
        self._producer = Lock()
        self._stopped = Event()
        self._worker: Thread | None = None
        self._preview_worker: Thread | None = None
        self._error: Exception | None = None
        self._received: deque[CameraAudioFrame] = deque()
        self._batch: _SendBatch | None = None
        self._packer = QuiiCFramePack()
        self.frames_sent = 0
        self.dropped_frames = 0

    @property
    def codec(self) -> int | None:
        """Negotiated outgoing codec (4=A-law, 5=mu-law), available after open."""
        return self._session.codec

    def open(self) -> "CameraTalkSession":
        """Wait for preview audio, then talk; only owned transports are closed."""
        self._check_available(require_open=False)
        if self._worker is not None:
            return self
        try:
            if self._preview is not None:
                self._preview.open()
                self._check_available(require_open=False)
                deadline = (
                    time.monotonic() + self._preview.config.connect_timeout
                )
                while not self._received:
                    self._check_available(require_open=False)
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise QuiiConnectionError(
                            "LAN talk preview did not provide audio before startup deadline"
                        )
                    try:
                        message = self._preview.recv_message(
                            timeout=min(remaining, 0.1)
                        )
                    except TimeoutError:
                        continue
                    if message["is_media"]:
                        self._receive_audio(message["payload"])
                reader = Thread(
                    target=self._run_preview,
                    name="quii-lan-talk-preview",
                    daemon=True,
                )
                self._preview_worker = reader
                reader.start()
            else:
                # The existing producer may still be connecting when talk is requested.
                deadline = (
                    time.monotonic() + 2 * self._session.config.connect_timeout
                )
                with self._condition:
                    while not self._received:
                        self._check_available(require_open=False)
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise QuiiConnectionError(
                                "LAN talk shared preview did not provide audio before startup deadline"
                            )
                        self._condition.wait(remaining)
            self._check_available(require_open=False)
            self._session.open()
            self._check_available(require_open=False)
            worker = Thread(
                target=self._run, name="quii-lan-talk", daemon=True
            )
            self._worker = worker
            worker.start()
            self._check_available()
            return self
        except BaseException as exc:
            self.close()
            if isinstance(exc, Exception) and self._error is not None:
                self._check_available(require_open=False)
            raise

    def send_pcm(self, pcm: bytes) -> None:
        """Send 1-25 complete 40ms PCM16 LE blocks, with bounded backpressure.

        Args:
            pcm: 640-16000 bytes, in multiples of 640. A caller supplying audio
                from another rate/layout must convert and buffer it first.

        Returns after all frames and their nominal playback window have been
        sent, including the half-duplex receive restoration ACK. Acceptance is
        not proof the door speaker played sound. Concurrent producers and
        invalid blocks are rejected before enqueueing. Network failure closes
        the session; never retry an ambiguous send automatically.
        """
        self._send_pcm(pcm, live=False)

    def _send_captured_pcm(self, pcm: bytes) -> None:
        """Send one hardware-clocked block; never add a second playback wait.

        Only the desktop bridge uses this path. It keeps the newest complete
        block if capture falls behind, rather than bursting an old backlog.
        Caller-supplied PCM/WAV retains send_pcm()'s existing pacing contract.
        """
        if not self.full_duplex or len(pcm) != PCM_FRAME_BYTES:
            raise ValueError(
                "Live capture requires full_duplex and one 640-byte block"
            )
        self._send_pcm(pcm, live=True)

    def _send_pcm(self, pcm: bytes, *, live: bool) -> None:
        """Serialize one bounded batch; live input is already hardware-clocked."""
        if (
            not isinstance(pcm, bytes)
            or not 0 < len(pcm) <= MAX_PCM_BYTES
            or len(pcm) % PCM_FRAME_BYTES
        ):
            raise ValueError(
                "PCM must be bytes: 640-16000 bytes in multiples of 640"
            )
        if not self._producer.acquire(blocking=False):
            raise RuntimeError("LAN talk supports only one PCM producer")
        timed_out = False
        try:
            batch = _SendBatch(pcm, live=live)
            deadline = (
                time.monotonic()
                + len(pcm) / 16000
                + 2 * self._session.config.connect_timeout
                + 1
            )
            with self._condition:
                self._check_available()
                self._batch = batch
                while self._batch is batch and not self._stopped.is_set():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        timed_out = True
                        break
                    self._condition.wait(remaining)
                if not timed_out:
                    self._check_available()
            if timed_out:
                self.close()
                raise QuiiConnectionError(
                    "LAN talk send deadline exceeded; no retry attempted"
                )
        finally:
            self._producer.release()

    def recv_frame(self, *, timeout: float = 5.0) -> CameraAudioFrame:
        """Return encoded G.711 from the selected preview, or raise TimeoutError.

        Args:
            timeout: Finite positive maximum wait, not extended by commands.

        Read timeouts preserve the active session. Connection/protocol errors
        propagate from the worker and invalidate it. close() wakes this wait.
        """
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        deadline = time.monotonic() + timeout
        with self._condition:
            while True:
                self._check_available()
                if self._received:
                    return self._received.popleft()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("timed out waiting for LAN talk audio")
                self._condition.wait(remaining)

    def _advance_send(self) -> None:
        with self._condition:
            batch = self._batch
        if batch is None or self._session.receive_pending:
            return
        if (
            not self.full_duplex
            and batch.offset == 0
            and self._session.receiving
        ):
            self._session.request_receive(False)
            return
        if time.monotonic() < batch.next_send:
            return
        if batch.offset < len(batch.pcm):
            assert self.codec is not None
            block = batch.pcm[batch.offset : batch.offset + PCM_FRAME_BYTES]
            self._session.send_audio(encode_g711(block, self.codec))
            batch.offset += PCM_FRAME_BYTES
            # Never burst old microphone samples to catch up after a stalled send.
            batch.next_send = time.monotonic() + FRAME_SECONDS
            self.frames_sent += 1
            if not batch.live:
                return
        if not self.full_duplex and not self._session.receiving:
            self._session.request_receive(True)
        else:
            with self._condition:
                if self._batch is batch:
                    self._batch = None
                    self._condition.notify_all()

    def _receive_audio(self, payload: bytes) -> None:
        with self._condition:
            if self._stopped.is_set():
                return
            frames = self._packer.feed(payload)
            if (
                self._packer.stats["trailing_partial_bytes"]
                > MAX_TCP_PAYLOAD_BYTES
                or self._packer.stats["invalid_headers"]
                or self._packer.stats["dropped_orphan_bytes"]
                or self._packer.stats["dropped_oversize_frames"]
                or any(
                    frame["frame_len"] > MAX_TCP_PAYLOAD_BYTES
                    for frame in frames
                )
            ):
                raise QuiiConnectionError(
                    "invalid or unsupported LAN talk preview framing"
                )
            for frame in frames:
                if frame["frame_tag"] != 0xE3:
                    continue
                try:
                    audio = CameraAudioFrame.from_cpacket(frame)
                except ValueError as exc:
                    raise QuiiConnectionError(
                        "invalid LAN talk preview audio metadata"
                    ) from exc
                self._queue_audio(audio)

    def _queue_audio(self, audio: CameraAudioFrame) -> None:
        """Admit one audio frame without retaining video or another CFrame parser."""
        with self._condition:
            if self._stopped.is_set():
                return
            if (
                audio.codec not in (4, 5)
                or audio.sample_rate != 8000
                or audio.channels != 1
                or len(audio.data) > MAX_AUDIO_FRAME_BYTES
            ):
                raise QuiiConnectionError(
                    "unsupported LAN talk incoming preview audio format"
                )
            if len(self._received) == MAX_RECEIVED_FRAMES:
                self._received.popleft()
                self.dropped_frames += 1
            self._received.append(audio)
            self._condition.notify_all()

    def _feed_preview_frame(self, frame: dict[str, Any]) -> None:
        """Borrow a completed audio frame; a talk failure must not stop preview."""
        try:
            self._queue_audio(CameraAudioFrame.from_cpacket(frame))
        except (ValueError, QuiiConnectionError) as exc:
            self._record_failure(exc)
            self._stop()

    def _run(self) -> None:
        try:
            while not self._stopped.is_set():
                self._advance_send()
                try:
                    self._session.recv_message(timeout=0.01)
                except TimeoutError:
                    continue
                # Talk carries ACKs/keepalive; never mix its media into preview audio.
        except Exception as exc:
            self._record_failure(exc)
        finally:
            self._stop()

    def _run_preview(self) -> None:
        assert self._preview is not None
        try:
            while not self._stopped.is_set():
                try:
                    message = self._preview.recv_message(timeout=0.1)
                except TimeoutError:
                    continue
                if message["is_media"]:
                    self._receive_audio(message["payload"])
        except Exception as exc:
            self._record_failure(exc)
        finally:
            self._stop()

    def _record_failure(self, exc: Exception) -> None:
        with self._condition:
            if not self._stopped.is_set() and self._error is None:
                self._error = exc

    def _stop(self) -> None:
        self._stopped.set()
        try:
            self._session.close()
        finally:
            try:
                if self._preview is not None:
                    self._preview.close()
            finally:
                with self._condition:
                    self._batch = None
                    self._received.clear()
                    self._packer = QuiiCFramePack()
                    self._condition.notify_all()

    def _check_available(self, *, require_open: bool = True) -> None:
        if self._error is not None:
            if isinstance(self._error, QuiiConnectionError):
                raise self._error
            raise QuiiConnectionError(
                "LAN talk worker failed"
            ) from self._error
        if self._stopped.is_set():
            raise QuiiConnectionError(
                "LAN talk session is closed; create a new session"
            )
        if require_open and (
            self._worker is None
            or (self._preview is not None and self._preview_worker is None)
        ):
            raise QuiiConnectionError("LAN talk session is not open")

    def close(self) -> None:
        """Cancel both sockets and join both workers, including after failure."""
        try:
            self._stop()
        finally:
            deadline = time.monotonic() + 1.0
            alive = False
            for worker in (self._worker, self._preview_worker):
                if (
                    worker is not None
                    and worker is not current_thread()
                    and worker.ident is not None
                ):
                    worker.join(timeout=max(0, deadline - time.monotonic()))
                    alive |= worker.is_alive()
            if alive:
                raise QuiiConnectionError("LAN talk worker did not stop")

    def __enter__(self) -> "CameraTalkSession":
        """Return the already opened session without a second authorization."""
        return self.open()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Stop even if microphone/application processing raises an exception."""
        self.close()
