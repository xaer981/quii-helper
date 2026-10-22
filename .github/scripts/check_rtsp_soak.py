"""Exercise the installed RTSP server with synthetic loopback-only video."""

import argparse
import gc
import json
import socket
import threading
import time
import tracemalloc

from quii_helper.streaming.rtsp.server import RtspH264Server


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
        self.error: BaseException | None = None
        self.thread: threading.Thread | None = None
        try:
            for cseq, method in enumerate(("SETUP", "PLAY"), 1):
                request = (
                    f"{method} {server.url} RTSP/1.0\r\nCSeq: {cseq}\r\n"
                    "Transport: RTP/AVP/TCP;unicast;interleaved=0-1\r\n\r\n"
                )
                self.sock.sendall(request.encode("ascii"))
                response = bytearray()
                while not response.endswith(b"\r\n\r\n"):
                    response.extend(read_exact(self.sock, 1))
                    if len(response) > 4096:
                        raise AssertionError("oversized RTSP response")
                assert response.startswith(b"RTSP/1.0 200 "), response
            self.sock.settimeout(0.5)
            if not slow:
                self.thread = threading.Thread(
                    target=self._receive, name="release-gate-viewer"
                )
                self.thread.start()
        except BaseException:
            self.close()
            raise

    def _receive(self) -> None:
        previous_sequence = None
        try:
            while not self.stopped.is_set():
                try:
                    header = read_exact(self.sock, 4)
                except socket.timeout:
                    continue
                assert header[:2] == b"$\0", header
                packet = read_exact(
                    self.sock, int.from_bytes(header[2:], "big")
                )
                assert len(packet) >= 12 and packet[0] == 0x80
                sequence = int.from_bytes(packet[2:4], "big")
                if previous_sequence is not None:
                    assert sequence == (previous_sequence + 1) & 0xFFFF
                previous_sequence = sequence
                self.packets += 1
                self.frames += bool(packet[1] & 0x80)
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


def run_soak(seconds: float) -> dict[str, object]:
    """Bound retained Python memory and exercise shutdown every 30 seconds."""
    if seconds < 3:
        raise ValueError("soak duration must be at least 3 seconds")
    unit = b"\0\0\0\1\x65" + b"x" * (16 * 1024)
    frames = packets = cycles = slow_disconnects = 0
    started = time.monotonic()
    deadline = started + seconds
    baseline = None
    growth = 0
    tracemalloc.start()
    try:
        while time.monotonic() < deadline:
            server = RtspH264Server(host="127.0.0.1", port=0).start()
            fast = slow = None
            workers = [server._accept_thread]
            try:
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
                while time.monotonic() < cycle_end:
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
                assert fast.error is None, repr(fast.error)
                frames += fast.frames
                packets += fast.packets
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
        "slow_disconnects": slow_disconnects,
        "retained_python_growth_bytes": growth,
        "peak_traced_python_bytes": peak,
        "worker_cleanup": "passed",
        "scope": "synthetic loopback TCP; not camera, codec, UDP or RSS proof",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=120)
    arguments = parser.parse_args()
    print(json.dumps(run_soak(arguments.seconds), indent=2))
