"""Exercise installed video-only or A/V RTSP with synthetic loopback media."""

import argparse
import gc
import json
import socket
import threading
import time
import tracemalloc
from urllib.parse import urljoin

from quii_helper import CameraAudioFrame
from quii_helper.streaming.rtsp.server import RtspH264Server

STAMP = (26 << 26) | (1 << 22) | (1 << 17)


def audio_frame(index: int) -> CameraAudioFrame:
    """Generate 40 ms of synthetic G.711 within a 30-second test cycle."""
    seconds, milliseconds = divmod(index * 40, 1000)
    assert seconds < 60
    return CameraAudioFrame(
        b"\xd5" * 320, 4, 8000, 1, STAMP | seconds, milliseconds
    )


def read_exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise EOFError("RTSP viewer disconnected")
        data.extend(chunk)
    return bytes(data)


class Viewer:
    """A real TCP viewer; the slow variant deliberately never reads RTP."""

    def __init__(self, server: RtspH264Server, *, slow: bool = False):
        self.sock = socket.socket()
        self.sock.settimeout(3)
        if slow:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
        self.sock.connect(("127.0.0.1", server.port))
        self.stopped = threading.Event()
        self.packets = 0
        self.frames = 0
        self.audio_packets = 0
        self.error: BaseException | None = None
        self.thread: threading.Thread | None = None
        try:
            headers, sdp = self._request("DESCRIBE", server.url, 1)
            controls = [
                line.removeprefix("a=control:")
                for line in sdp.decode().splitlines()
                if line.startswith("a=control:trackID=")
            ]
            assert len(controls) == (2 if server.audio else 1)
            for track, control in enumerate(controls):
                self._request(
                    "SETUP",
                    urljoin(headers["content-base"], control),
                    track + 2,
                    f"Transport: RTP/AVP/TCP;unicast;interleaved={2 * track}-{2 * track + 1}\r\n",
                )
            play, _ = self._request("PLAY", server.url, len(controls) + 2)
            assert "rtp-info" not in play
            self.sock.settimeout(0.5)
            if not slow:
                self.thread = threading.Thread(
                    target=self._receive, name="release-gate-viewer"
                )
                self.thread.start()
        except BaseException:
            self.close()
            raise

    def _request(
        self, method: str, uri: str, cseq: int, headers: str = ""
    ) -> tuple[dict[str, str], bytes]:
        self.sock.sendall(
            f"{method} {uri} RTSP/1.0\r\nCSeq: {cseq}\r\n{headers}\r\n".encode(
                "ascii"
            )
        )
        response = bytearray()
        while not response.endswith(b"\r\n\r\n"):
            response.extend(read_exact(self.sock, 1))
            assert len(response) <= 16384, "oversized RTSP response"
        lines = response.decode().splitlines()
        assert lines[0].startswith("RTSP/1.0 200 "), response
        fields = {
            key.lower(): value
            for key, value in (
                line.split(": ", 1) for line in lines[1:] if line
            )
        }
        size = int(fields.get("content-length", "0"))
        assert 0 <= size <= 16384
        return fields, read_exact(self.sock, size)

    def _receive(self) -> None:
        previous_sequences: dict[int, int] = {}
        previous_audio_timestamp = None
        ssrcs: dict[int, bytes] = {}
        try:
            while not self.stopped.is_set():
                try:
                    header = read_exact(self.sock, 4)
                except socket.timeout:
                    continue
                assert header[:1] == b"$" and header[1] in (0, 2), header
                track = header[1] // 2
                packet = read_exact(
                    self.sock, int.from_bytes(header[2:], "big")
                )
                assert len(packet) >= 12 and packet[0] == 0x80
                sequence = int.from_bytes(packet[2:4], "big")
                if track in previous_sequences:
                    assert sequence == (previous_sequences[track] + 1) & 0xFFFF
                previous_sequences[track] = sequence
                ssrcs[track] = packet[8:12]
                if len(ssrcs) == 2:
                    assert ssrcs[0] != ssrcs[1]
                self.packets += 1
                if track == 0:
                    assert packet[1] & 127 == 96
                    self.frames += bool(packet[1] & 0x80)
                else:
                    assert packet[1] & 127 == 8 and len(packet[12:]) == 320
                    timestamp = int.from_bytes(packet[4:8], "big")
                    if previous_audio_timestamp is not None:
                        assert (
                            timestamp - previous_audio_timestamp
                        ) & 0xFFFFFFFF == 320
                    previous_audio_timestamp = timestamp
                    self.audio_packets += 1
        except BaseException as exc:
            if not self.stopped.is_set():
                self.error = exc

    def close(self) -> None:
        self.stopped.set()
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()
        if self.thread is not None:
            self.thread.join(2)
            assert not self.thread.is_alive(), "viewer thread leaked"


def run_soak(seconds: float, *, audio: bool = False) -> dict[str, object]:
    """Bound retained Python memory and exercise shutdown every 30 seconds."""
    if seconds < 3:
        raise ValueError("soak duration must be at least 3 seconds")
    unit = b"\0\0\0\1\x67sps\0\0\0\1\x68pps\0\0\0\1\x65" + b"x" * (16 * 1024)
    frames = packets = audio_packets = cycles = slow_disconnects = 0
    started = time.monotonic()
    deadline = started + seconds
    baseline = None
    growth = 0
    tracemalloc.start()
    try:
        while time.monotonic() < deadline:
            server = RtspH264Server(
                host="127.0.0.1", port=0, audio=audio
            ).start()
            fast = slow = None
            workers = [server._accept_thread]
            try:
                server.publish(unit)
                if audio:
                    server.publish_audio(audio_frame(0))
                fast = Viewer(server)
                slow = Viewer(server, slow=True)
                with server._clients_lock:
                    clients = list(server._clients)
                for client in clients:
                    workers.extend([client._thread, client._sender_thread])
                    if client.address[1] == slow.sock.getsockname()[1]:
                        client.sock.setsockopt(
                            socket.SOL_SOCKET, socket.SO_SNDBUF, 1024
                        )
                cycle_started = time.monotonic()
                cycle_end = min(deadline, cycle_started + 30)
                slow_checked = False
                audio_index = 1
                while time.monotonic() < cycle_end:
                    elapsed_ms = int((time.monotonic() - cycle_started) * 1000)
                    if audio:
                        server.publish_frame(
                            unit,
                            {
                                "frame_stamp": STAMP | (elapsed_ms // 1000),
                                "frame_ms": elapsed_ms % 1000,
                            },
                        )
                        while audio_index * 40 <= elapsed_ms:
                            server.publish_audio(audio_frame(audio_index))
                            audio_index += 1
                    else:
                        server.publish(unit)
                    assert fast.error is None, repr(fast.error)
                    with server._clients_lock:
                        assert all(
                            client._outgoing_bytes <= 4 * 1024 * 1024
                            for client in server._clients
                        )
                    if time.monotonic() - cycle_started >= 2:
                        assert server.client_count == 1, "slow viewer retained"
                        slow_checked = True
                    time.sleep(0.1)
                assert fast.frames > 0, "fast viewer received no media"
                if audio:
                    assert (
                        fast.audio_packets > 0
                    ), "fast viewer received no audio"
                assert fast.error is None, repr(fast.error)
                frames += fast.frames
                packets += fast.packets
                audio_packets += fast.audio_packets
                slow_disconnects += slow_checked
            finally:
                for viewer in (fast, slow):
                    if viewer is not None:
                        viewer.close()
                server.close()
                for worker in workers:
                    if worker is not None:
                        worker.join(2)
                        assert not worker.is_alive(), worker.name
            cycles += 1
            gc.collect()
            retained, _ = tracemalloc.get_traced_memory()
            if baseline is None:
                baseline = retained
            growth = max(growth, retained - baseline)
            assert growth <= 8 * 1024 * 1024, "retained Python memory grew"
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert slow_disconnects > 0, "slow-client test did not run"
    return {
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "cycles": cycles,
        "received_frames": frames,
        "received_rtp_packets": packets,
        "received_audio_packets": audio_packets,
        "audio_enabled": audio,
        "slow_disconnects": slow_disconnects,
        "retained_python_growth_bytes": growth,
        "peak_traced_python_bytes": peak,
        "worker_cleanup": "passed",
        "scope": "synthetic loopback TCP; not camera, codec, UDP or RSS proof",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=120)
    parser.add_argument("--audio", action="store_true")
    arguments = parser.parse_args()
    print(
        json.dumps(
            run_soak(arguments.seconds, audio=arguments.audio), indent=2
        )
    )
