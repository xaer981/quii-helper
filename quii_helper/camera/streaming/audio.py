"""Synchronous receive-only audio over the existing LAN preview session."""

import math
import time
from collections import deque
from threading import Event, Lock

from quii_helper.media.audio import CameraAudioFrame
from quii_helper.media.frames.assembler_state import MEDIA_PACKET_TYPES
from quii_helper.media.frames.cframe_pack import QuiiCFramePack
from quii_helper.protocols.tcp.live.session import LanTcpSession
from quii_helper.support.errors import QuiiConnectionError


class CameraAudioStream:
    """A single-reader encoded audio stream returned by `Camera.listen_audio()`.

    Use a context manager or call `close()`. No background worker, local audio
    device, decoder, file writer or automatic reconnect is started. The caller
    must drain frames promptly; this is not a lossless recording API.
    """

    def __init__(self, session: LanTcpSession) -> None:
        self._session = session
        self._packer = QuiiCFramePack()
        self._pending: deque[CameraAudioFrame] = deque()
        self._opened = False
        self._closed = Event()
        self._buffer_lock = Lock()

    def open(self) -> "CameraAudioStream":
        """Open the owned LAN session once; startup failure closes it."""
        self._check_closed()
        if not self._opened:
            try:
                self._session.open()
                self._check_closed()
                self._opened = True
            except BaseException:
                self.close()
                raise
        return self

    def recv_frame(self, *, timeout: float = 5.0) -> CameraAudioFrame:
        """Read the next complete audio frame, discarding video and commands.

        Args:
            timeout: Finite positive maximum seconds for this call, including
                reads of non-audio messages. Partial frames survive a timeout.

        Returns:
            Encoded payload plus the camera's codec and timestamp metadata.

        Raises:
            TimeoutError: No complete audio arrived in time; retry is allowed.
            ValueError: The timeout is not finite and positive.
            QuiiConnectionError: The session is closed, failed, or received
                invalid audio metadata. Connection errors close the stream.
        """
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        self._check_closed()
        if not self._opened:
            raise QuiiConnectionError("audio stream is not open")
        deadline = time.monotonic() + timeout
        try:
            while True:
                with self._buffer_lock:
                    self._check_closed()
                    if self._pending:
                        return self._pending.popleft()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("timed out waiting for camera audio")
                try:
                    decoded = self._session.recv_message(
                        timeout=min(remaining, 1.0)
                    )
                except TimeoutError:
                    continue
                self._check_closed()
                header = decoded.get("header")
                if (
                    header is None
                    or header.packet_type not in MEDIA_PACKET_TYPES
                ):
                    continue
                with self._buffer_lock:
                    self._check_closed()
                    for frame in self._packer.feed(
                        decoded.get("payload", b"")
                    ):
                        if frame["frame_tag"] == 0xE3:
                            self._pending.append(
                                CameraAudioFrame.from_cpacket(frame)
                            )
        except TimeoutError:
            raise
        except (OSError, RuntimeError, ValueError) as exc:
            self.close()
            if isinstance(exc, QuiiConnectionError):
                raise
            raise QuiiConnectionError("LAN audio receive failed") from exc

    def close(self) -> None:
        """Close the socket and release buffered frames; repeated calls are safe."""
        self._closed.set()
        self._opened = False
        try:
            self._session.close()
        finally:
            with self._buffer_lock:
                self._pending.clear()
                self._packer = QuiiCFramePack()

    def _check_closed(self) -> None:
        if self._closed.is_set():
            raise QuiiConnectionError(
                "audio stream is closed; create a new stream"
            )

    def __enter__(self) -> "CameraAudioStream":
        """Return the opened stream; does not send a second play command."""
        return self.open()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Release the session when leaving the context, including on errors."""
        self.close()
