from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from quii_helper.camera.streaming.conversation import CameraConversationSession
from quii_helper.camera.streaming.talk import CameraTalkSession
from quii_helper.models.packets import DecodedQuiiMessage
from quii_helper.preview.outputs.manager.artifacts import (
    PreviewArtifactManager,
)
from quii_helper.preview.pipeline.config import PreviewCaptureSettings
from quii_helper.preview.pipeline.stream import TunnelPacketStream
from quii_helper.preview.processing.packets.processor import (
    PreviewPacketProcessor,
)
from quii_helper.protocols.tcp.live.session import LanTcpSession
from quii_helper.streaming.h264 import H264LiveAssembler
from quii_helper.streaming.rtsp import RtspH264Server
from quii_helper.support.errors import ConfigurationError, QuiiConnectionError

STREAM_PACKET_BATCH_SECONDS = 1.0
STREAM_PACKET_TIMEOUT_SECONDS = 1.0
PRODUCER_JOIN_TIMEOUT_SECONDS = 2.0
PRODUCER_WAIT_INTERVAL_SECONDS = 0.1
LIVE_PREVIEW_SETUP_SEQ = 0
LIVE_PREVIEW_PLAY_SEQ = 1
LIVE_PREVIEW_SETUP_TIMEOUT_SECONDS = 3.0
EmitCallback = Callable[[object], None]
StatusCallback = Callable[[str], None]


@dataclass
class CameraRtspStream:
    """Running RTSP stream created by `Camera.serve_rtsp()`.

    The object starts an RTSP server
    and a background producer thread that reads camera preview packets,
    assembles H.264 access units, and publishes them to RTSP clients.

    Attributes:
        connector: Camera connector used to fetch credentials and open preview.
        preview_settings: Capture/packet processing settings.
        data_dir: Directory used for temporary artifact manager state.
        emit: Callback for structured debug summaries.
        status: Callback for user-facing status messages.
        host: Interface bound by the RTSP server.
        port: TCP port bound by the RTSP server.
        path: RTSP path exposed by the server.
        connection_mode: Explicit source selection; LAN never fetches credentials.
    """

    connector: Any
    preview_settings: PreviewCaptureSettings
    data_dir: Path
    emit: EmitCallback
    status: StatusCallback
    host: str = "127.0.0.1"
    port: int = 8554
    path: str = "/live"
    connection_mode: str = "cloud"
    audio: bool = False
    server: RtspH264Server = field(init=False)
    assembler: H264LiveAssembler = field(init=False)
    _stop_event: threading.Event = field(
        default_factory=threading.Event, init=False, repr=False
    )
    _thread: threading.Thread | None = field(default=None, init=False)
    _packet_stream: TunnelPacketStream | LanTcpSession | None = field(
        default=None, init=False, repr=False
    )
    _error: BaseException | None = field(default=None, init=False, repr=False)
    _started: bool = field(default=False, init=False)
    _ready_announced: bool = field(default=False, init=False)
    _lifecycle_lock: threading.RLock = field(
        default_factory=threading.RLock, init=False, repr=False
    )
    _closing: bool = field(default=False, init=False)
    _talk: CameraConversationSession | None = field(
        default=None, init=False, repr=False
    )
    _talk_error: BaseException | None = field(
        default=None, init=False, repr=False
    )

    def __post_init__(self) -> None:
        self.server = RtspH264Server(
            host=self.host,
            port=self.port,
            path=self.path,
            audio=self.audio,
        )
        self.assembler = H264LiveAssembler(
            sink=self.server.publish,
            audio_sink=self.server.publish_audio if self.audio else None,
            frame_sink=self.server.publish_frame if self.audio else None,
            audio_frame_observer=self._observe_audio_frame,
        )

    @property
    def url(self) -> str:
        """RTSP URL clients should open."""
        return self.server.url

    @property
    def stats(self) -> dict[str, object]:
        """Runtime stream statistics for diagnostics."""
        return {
            "rtsp_clients": self.server.client_count,
            "h264": self.assembler.stats,
            "talk_active": self.talk_active,
        }

    @property
    def talk_active(self) -> bool:
        """Whether explicitly started computer audio is active on this preview."""
        with self._lifecycle_lock:
            return self._talk is not None and self._talk.active

    @property
    def talk_error(self) -> BaseException | None:
        """Last isolated talk failure; preview errors are reported by wait()."""
        with self._lifecycle_lock:
            return self._talk_error

    def start_talk(
        self,
        *,
        input_device: str | None = None,
        output_device: str | None = None,
    ) -> CameraConversationSession:
        """Start PC microphone/playback using this LAN preview's audio frames.

        No second preview is opened. Only generic talk 65535 is added; the
        existing producer/parser remains the sole reader of video and sound.
        This call waits for talk/device readiness, then returns an active
        handle. Names select exact local devices; None uses OS defaults.
        Requires the optional audio extra. It is an explicit active operation,
        not an RTSP backchannel. Use headphones; echo cancellation is absent.

        Duplicate/parallel starts are rejected. stop_talk(), handle.close(),
        failure or parent close stop local audio and the talk socket. Talk
        failures do not close preview; inspect talk_error or handle.wait().
        Cloud mode and calls from the producer callback are not supported.
        """
        with self._lifecycle_lock:
            if self.connection_mode != "lan":
                raise ConfigurationError("start_talk requires a LAN preview")
            if (
                not self._started
                or self._closing
                or self._stop_event.is_set()
                or self._thread is None
                or not self._thread.is_alive()
            ):
                raise QuiiConnectionError(
                    "start_talk requires an active preview session"
                )
            if threading.current_thread() is self._thread:
                raise RuntimeError(
                    "start_talk cannot block the preview producer callback"
                )
            if self._talk is not None:
                raise RuntimeError(
                    "Talk is already active, starting or stopping"
                )
            talk = CameraTalkSession(
                self.connector.create_lan_talk_session(), full_duplex=True
            )
            handle = CameraConversationSession(
                talk,
                input_device=input_device,
                output_device=output_device,
                on_close=self._talk_finished,
            )
            self._talk_error = None
            self._talk = handle
        return handle._start()

    def stop_talk(self) -> None:
        """Stop only local audio and talk; idempotent, preview/RTSP stays active."""
        with self._lifecycle_lock:
            handle = self._talk
        if handle is not None:
            handle.close()

    def _talk_finished(self, handle: CameraConversationSession) -> None:
        with self._lifecycle_lock:
            if self._talk is handle:
                self._talk_error = handle.error
                self._talk = None

    def _observe_audio_frame(self, frame: dict[str, Any]) -> None:
        """Fan out completed frames, never read or reassemble preview a second time."""
        with self._lifecycle_lock:
            handle = self._talk
        if handle is not None:
            handle._talk._feed_preview_frame(frame)

    def start(self) -> "CameraRtspStream":
        """Start the RTSP server and background camera producer.

        Returns:
            This stream handle, allowing `Camera.serve_rtsp()` to return a
            started object directly.
        """
        with self._lifecycle_lock:
            if self._closing or (
                self._stop_event.is_set()
                and self._thread is not None
                and self._thread.is_alive()
            ):
                raise RuntimeError("RTSP producer is still stopping")
            if self._started:
                return self
            if self._talk is not None:
                raise RuntimeError("Talk is still stopping")
            self.status("Starting RTSP server")
            self._error = None
            self.server.start()
            self.assembler = H264LiveAssembler(
                sink=self.server.publish,
                wait_for_keyframe=self.connection_mode == "lan",
                audio_sink=self.server.publish_audio if self.audio else None,
                frame_sink=self.server.publish_frame if self.audio else None,
                audio_frame_observer=self._observe_audio_frame,
            )
            self._ready_announced = False
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_preview_loop,
                name="quii-camera-rtsp-producer",
                daemon=True,
            )
            self._started = True
            try:
                self._thread.start()
            except BaseException:
                self._started = False
                self._thread = None
                self.server.close()
                raise
        return self

    def wait(self, timeout: float | None = None) -> None:
        """Wait for the producer thread and re-raise producer errors.

        Args:
            timeout: Maximum seconds to wait. `None` waits indefinitely.

        Waiting remains interruptible with `Ctrl+C`, including on Windows.
        A timeout does not close the stream; use the context manager or `close`.

        Raises:
            BaseException: Re-raises the background producer error, if any.
        """
        with self._lifecycle_lock:
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            deadline = (
                None if timeout is None else time.monotonic() + max(0, timeout)
            )
            # An indefinite join can defer SIGINT on Windows; poll without it.
            while thread.is_alive():
                interval = PRODUCER_WAIT_INTERVAL_SECONDS
                if deadline is not None:
                    interval = min(interval, deadline - time.monotonic())
                    if interval <= 0:
                        break
                time.sleep(interval)
        if self._error is not None:
            raise self._error

    def close(self) -> None:
        """
        Stop serving and request producer cancellation.

        An in-flight connection may finish at its own network timeout. Restart
        is rejected until that worker exits; no later playback stage is started.
        """
        with self._lifecycle_lock:
            if self._closing:
                return
            self._closing = True
            self._stop_event.set()
            self._started = False
            packet_stream, thread = self._packet_stream, self._thread
        try:
            try:
                self.stop_talk()
            finally:
                try:
                    if packet_stream is not None:
                        packet_stream.close()
                finally:
                    self.server.close()
        finally:
            if thread is not None and thread is not threading.current_thread():
                thread.join(timeout=PRODUCER_JOIN_TIMEOUT_SECONDS)
            with self._lifecycle_lock:
                if thread is None or not thread.is_alive():
                    self._thread = None
                self._closing = False

    def __enter__(self) -> "CameraRtspStream":
        """Start and return this stream when used as a context manager."""
        return self.start()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Close the stream when leaving a context manager block."""
        self.close()

    def _run_preview_loop(self) -> None:
        try:
            if self._stop_event.is_set():
                return
            if self.connection_mode == "lan":
                self._run_lan_preview()
                return
            self.status("Fetching runtime credentials")
            if self._stop_event.is_set():
                return
            credentials = self.connector.fetch_credentials()
            if self._stop_event.is_set():
                return
            self.status("Opening preview session")
            if self._stop_event.is_set():
                return
            with self.connector.open_preview(
                credentials=credentials
            ) as session:
                with self._lifecycle_lock:
                    if self._stop_event.is_set():
                        return
                    self._packet_stream = TunnelPacketStream(session.tunnel)
                self.status("Connected")
                self.emit(session.connection_summary())
                self.status("Starting live preview")
                setup_acked = session.start_live_preview(
                    setup_seq=LIVE_PREVIEW_SETUP_SEQ,
                    play_seq=LIVE_PREVIEW_PLAY_SEQ,
                    setup_timeout=LIVE_PREVIEW_SETUP_TIMEOUT_SECONDS,
                    stop_event=self._stop_event,
                )
                if self._stop_event.is_set():
                    return
                self.emit({"quii_setup_acked": setup_acked})
                self.status("Receiving media packets")
                self._consume_session_packets(session, credentials)
        except Exception as exc:
            if self._stop_event.is_set():
                return
            self._error = exc
            self.status(f"RTSP producer stopped: {exc}")
        finally:
            try:
                self.stop_talk()
            except Exception as exc:
                if self._error is None and not self._stop_event.is_set():
                    self._error = exc
            finally:
                self.server.close()
                with self._lifecycle_lock:
                    self._packet_stream = None

    def _consume_session_packets(self, session: Any, credentials: Any) -> None:
        artifacts = PreviewArtifactManager(
            diagnostics_enabled=False,
            data_dir=self.data_dir,
            direct_blob_sample_limit=(
                self.preview_settings.direct_blob_sample_limit
            ),
            wrapped_tail_sample_limit=(
                self.preview_settings.wrapped_tail_sample_limit
            ),
            fragment_partial_sample_limit=(
                self.preview_settings.fragment_partial_sample_limit
            ),
        )
        processor = PreviewPacketProcessor(
            key=session.credentials.data_encode_key,
            artifacts=artifacts,
            fragment_partial_collector=(
                artifacts.create_fragment_partial_collector(
                    key=session.credentials.data_encode_key
                )
            ),
            emit=self.emit,
            min_media_messages=self.preview_settings.min_media_messages,
            max_media_messages=self.preview_settings.max_media_messages,
            direct_blob_summary_limit=(
                self.preview_settings.direct_blob_summary_limit
            ),
            media_message_sink=self._feed_assembler_message,
            store_media_messages=False,
        )
        packet_stream = self._packet_stream
        if not isinstance(packet_stream, TunnelPacketStream):
            return
        while not self._stop_event.is_set():
            for packet in packet_stream.live_packets(
                duration=STREAM_PACKET_BATCH_SECONDS,
                timeout=STREAM_PACKET_TIMEOUT_SECONDS,
                keepalive_credentials=credentials,
            ):
                if self._stop_event.is_set():
                    break
                processor.process_packet(packet, phase="live")

    def _run_lan_preview(self) -> None:
        self.status("Opening LAN preview session")
        with self._lifecycle_lock:
            if self._stop_event.is_set():
                return
            session = self.connector.create_lan_session()
            self._packet_stream = session
        # Register before opening so close() can interrupt setup/receive too.
        with session:
            if self._stop_event.is_set():
                return
            self.status("Connected")
            self.status("Receiving media packets")
            while not self._stop_event.is_set():
                try:
                    decoded = session.recv_message(
                        timeout=STREAM_PACKET_TIMEOUT_SECONDS
                    )
                except TimeoutError:
                    continue
                self._feed_assembler_message(decoded)

    def _feed_assembler_message(self, decoded: DecodedQuiiMessage) -> None:
        if self._stop_event.is_set():
            return
        self.assembler.feed_message(decoded)
        if self.assembler.access_unit_count > 0 and (
            not self.audio
            or (
                self.server.audio_format is not None
                and self.server.parameter_sets
            )
        ):
            self._announce_ready_once()

    def _announce_ready_once(self) -> None:
        if self._ready_announced:
            return
        self._ready_announced = True
        self.status(f"RTSP stream ready: {self.url}")
