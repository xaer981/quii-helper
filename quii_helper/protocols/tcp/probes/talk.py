"""Bounded LAN talk diagnostics, without a microphone or outgoing media."""

import math
import time
from collections import Counter
from queue import Empty, SimpleQueue
from threading import Event, Lock, Thread
from typing import Any

from quii_helper.config import AutonomousConfig
from quii_helper.media.audio import CameraAudioFrame
from quii_helper.media.frames.cframe_pack import QuiiCFramePack
from quii_helper.models.packets import DecodedQuiiMessage
from quii_helper.protocols.tcp.live.session import (
    LanTcpSession,
    validate_lan_config,
)
from quii_helper.protocols.tcp.talk.packets import (
    talk_channel as normalize_talk_channel,
)
from quii_helper.protocols.tcp.talk.session import LanTalkSession
from quii_helper.protocols.tcp.transport.client import TcpTransportFactory
from quii_helper.protocols.tcp.transport.socket_transport import (
    TcpSocketTransport,
)

MAX_MESSAGE_BYTES = 1024 * 1024
MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_FORMATS = 16


class _Traffic:
    def __init__(self, started: float) -> None:
        self._started = started
        self._lock = Lock()
        self._packer = QuiiCFramePack()
        self._counts: Counter[str] = Counter()
        self._packets: Counter[str] = Counter()
        self._formats: Counter[str] = Counter()
        self._dimensions: Counter[str] = Counter()
        self._first_audio: float | None = None
        self._limit_reached = False

    def feed(self, message: DecodedQuiiMessage) -> None:
        with self._lock:
            self._counts["messages"] += 1
            if not message["is_media"]:
                return
            payload = message["payload"]
            self._counts["media_bytes"] += len(payload)
            self._packets[f"{message['header'].packet_type:02x}"] += 1
            if (
                len(payload) > MAX_MESSAGE_BYTES
                or self._counts["media_bytes"] > MAX_SOURCE_BYTES
            ):
                self._limit_reached = True
                raise ValueError("talk diagnostic media budget exceeded")
            frames = self._packer.feed(payload)
            if (
                self._packer.stats["trailing_partial_bytes"]
                > MAX_MESSAGE_BYTES
            ):
                self._limit_reached = True
                raise ValueError(
                    "talk diagnostic partial-frame budget exceeded"
                )
            for frame in frames:
                if frame["frame_tag"] == 0xE3:
                    self._counts["audio_frames"] += 1
                    try:
                        audio = CameraAudioFrame.from_cpacket(frame)
                    except ValueError:
                        self._counts["invalid_audio_frames"] += 1
                        continue
                    if self._first_audio is None:
                        self._first_audio = round(
                            time.monotonic() - self._started, 3
                        )
                    self._counts["audio_bytes"] += len(audio.data)
                    key = f"{audio.codec}:{audio.sample_rate}:{audio.channels}"
                    self._bucket(self._formats, key)
                elif frame["frame_type"] in {0, 1, 9, 10}:
                    self._counts["video_frames"] += 1
                    key = f"{frame['width']}x{frame['height']}"
                    self._bucket(self._dimensions, key)

    def _bucket(self, counts: Counter[str], key: str) -> None:
        if key not in counts and len(counts) >= MAX_FORMATS:
            self._counts["other_formats"] += 1
        else:
            counts[key] += 1

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                **{
                    key: self._counts[key]
                    for key in (
                        "messages",
                        "media_bytes",
                        "video_frames",
                        "audio_frames",
                        "audio_bytes",
                        "invalid_audio_frames",
                        "other_formats",
                    )
                },
                "media_packets": dict(self._packets),
                "audio_codec_rate_channels": dict(self._formats),
                "video_dimensions": dict(self._dimensions),
                "first_audio_seconds": self._first_audio,
                "limit_reached": self._limit_reached,
                "cframe": dict(self._packer.stats),
            }


def diagnose_lan_talk(
    config: AutonomousConfig,
    *,
    duration_seconds: float = 10.0,
    talk_channel: int = 65535,
    transport_factory: TcpTransportFactory = TcpSocketTransport,
) -> dict[str, Any]:
    """Observe preview and talk separately, without waiting for preview audio.

    Uses a saved LAN key/auth pair only. Setup/Open/C1/D1 and keepalives are
    sent, never A2 media, microphone data, cloud requests or device settings.
    Opening talk reserves a conversation slot and may contend with an app;
    this is receive-only diagnostics, not a side-effect-free CGI query.

    Args:
        config: Valid LAN config; channel/stream select the preview panel.
        duration_seconds: Observation after talk becomes ready, 0 < N <= 60.
            Connection stages additionally use config.connect_timeout.
        talk_channel: Native generic selector 65535, or an explicit panel id.
            No automatic selector retries or fallback are performed.
        transport_factory: Existing TCP transport seam for offline tests.

    Returns:
        Sanitized counters, negotiated codec, validated Open/C/D statuses and
        failure-stage/exception types. No exception text, credentials, raw
        packets or audio/video payloads are retained in the report.
        Each source has separate CFrame state, a 1 MiB message/partial limit,
        a 32 MiB media budget and at most 16 format/dimension buckets.
        A missing C reply is None even if the native D-ready reply succeeded.
    """
    if (
        isinstance(duration_seconds, bool)
        or not isinstance(duration_seconds, (int, float))
        or not math.isfinite(duration_seconds)
        or not 0 < duration_seconds <= 60
    ):
        raise ValueError(
            "duration_seconds must be finite and between 0 and 60"
        )
    validate_lan_config(config)
    selector = normalize_talk_channel(talk_channel)
    started = time.monotonic()
    preview_traffic, talk_traffic = _Traffic(started), _Traffic(started)
    stopped = Event()
    failures: SimpleQueue[dict[str, str]] = SimpleQueue()
    preview: LanTcpSession | None = None
    talk: LanTalkSession | None = None
    reader: Thread | None = None
    stage = "preview_create"
    startup_completed = False
    observation_started: float | None = None
    observation_seconds = 0.0

    def failed(where: str, error: Exception) -> None:
        cause = error.__cause__
        failures.put(
            {
                "stage": where,
                "type": type(error).__name__,
                "cause_type": type(cause).__name__ if cause else "",
            }
        )
        stopped.set()

    def read_preview() -> None:
        assert preview is not None and talk is not None
        try:
            while not stopped.is_set():
                try:
                    message = preview.recv_message(timeout=0.1)
                except TimeoutError:
                    continue
                preview_traffic.feed(message)
        except Exception as error:
            if not stopped.is_set():
                failed("preview_receive", error)
                # Interrupt a talk handshake if the selected preview failed.
                try:
                    talk.close()
                except Exception as close_error:
                    failed("talk_close", close_error)

    try:
        preview = LanTcpSession(config, transport_factory=transport_factory)
        stage = "talk_create"
        talk = LanTalkSession(
            config,
            channel=selector,
            transport_factory=transport_factory,
            message_observer=talk_traffic.feed,
        )
        stage = "preview_open"
        preview.open()
        reader = Thread(
            target=read_preview, name="quii-talk-probe-preview", daemon=True
        )
        reader.start()
        stage = "talk_open"
        if not stopped.is_set():
            talk.open()
            startup_completed = True
            observation_started = time.monotonic()
            deadline = observation_started + duration_seconds
            stage = "talk_receive"
            while not stopped.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    talk.recv_message(timeout=min(remaining, 0.1))
                except TimeoutError:
                    continue
    except Exception as error:
        failed(stage, error)
    finally:
        if observation_started is not None:
            observation_seconds = time.monotonic() - observation_started
        stopped.set()
        for name, connection in (("talk", talk), ("preview", preview)):
            if connection is None:
                continue
            try:
                connection.close()
            except Exception as error:
                failed(f"{name}_close", error)
        if reader is not None and reader.ident is not None:
            reader.join(timeout=2.0)
            if reader.is_alive():
                failed("preview_join", RuntimeError())
    errors = []
    while True:
        try:
            errors.append(failures.get_nowait())
        except Empty:
            break
    return {
        "status": "failed" if errors else "completed",
        "preview_channel": config.channel,
        "preview_stream": config.stream,
        "talk_channel": selector,
        "duration_seconds": duration_seconds,
        "observation_seconds": round(observation_seconds, 3),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "wait_for_preview_audio": False,
        "microphone_used": False,
        "audio_transmitted": False,
        "talk_startup_completed": startup_completed,
        "handshake": talk.handshake_diagnostics if talk else {},
        "codec": talk.codec if talk else None,
        "full_packet": talk.full_packet if talk else None,
        "preview": preview_traffic.summary(),
        "talk": talk_traffic.summary(),
        "errors": errors,
    }
