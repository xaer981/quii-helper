# QUII Helper

Python helpers for opening a QUII camera preview, receiving stream packets, decoding media payloads, and saving runtime artifacts.

Runtime files are written under `data/`. The repository keeps `data/.gitkeep`, while generated captures, logs, binaries, and JSONL diagnostics are ignored by git.

## Package API

Use `quii_helper.Camera` as the high-level API. By default it reads device/cloud settings from `.env`.

```python
from quii_helper import Camera

camera = Camera()

snapshot_path = camera.snapshot(timeout_seconds=5)
video_path = camera.save_video(30)
capture = camera.capture(duration_seconds=15)

print(snapshot_path)
print(video_path)
print(capture.snapshot_path, capture.video_path)
```

Stream quality can be selected explicitly. The native app defaults to stream
`2` (`low`/`sd`), while stream `1` (`high`/`hd`) requests a higher-quality
preview when the camera supports it:

```python
camera = Camera(stream_quality="high")  # ids=1
camera = Camera(stream_quality="low")   # ids=2, native default
camera = Camera(stream=1)               # direct numeric stream id
```

Optional explicit output names are still normalized into `data/`:

```python
camera.snapshot(output_path="front-door.jpg")
camera.save_video(10, output_path="front-door.mp4")
```

`snapshot(timeout_seconds=...)` waits up to that many seconds for a decodable frame. `save_video(duration_seconds=...)` reads the live stream for the requested duration before writing the MP4.

For reusable application code, pass credentials explicitly instead of depending on process-level environment:

```python
from quii_helper import Camera

camera = Camera(
    device_id="22058iwsv6av",
    cloud_account="account@example.com",
    cloud_password="password-or-sha256",
    client_id="client-uuid",
)

snapshot_path = camera.snapshot(timeout_seconds=5)
```

The default live play request uses `live_play_payload="path"`, matching the Java live URL flow used by `QvPlayerCore.startPlay` / `QvLtPlayerCore.startPlayCompat` for `/mode=real&idc=...&ids=...&ap=...`. `live_play_payload="oem"` is kept as a protocol experiment for the SDK custom-id path, but it did not start media on the current direct/LAN tunnel.

By default `play_sync_iterations=0`, so synthetic RBUDP play-sync control packets are disabled. Use a positive value only as a protocol diagnostic experiment; native RBUDP clears its send-list from ACK `remote_id` values, so synthetic ACK-like packets can suppress data that was not actually received.

Synthetic play probes are disabled by default with `enable_play_probes=False`. The fixed probe payloads were not found in the native player binaries, so this option should only be used for diagnostics against older captured behavior.

## Configuration

`.env` is loaded in `quii_helper.constants` with `python-dotenv` and used only as default values for `AutonomousConfig`.

Explicit values passed to `Camera(...)` override `.env` defaults. Prefer explicit values in library/production use, and keep `.env` for local development.

Supported local `.env` keys:

```dotenv
CLOUD_ACCOUNT=""
CLOUD_PASSWORD=""
DEVICE_ID=""
AUTH_CODE=""
DEVICE_PASSWORD=""
CLOUD_CLIENT_UUID=""
CAMERA_CHANNEL=1
```

`CAMERA_CHANNEL` selects the camera channel/video panel used as QUII `idc`.
Legacy aliases `VIDEO_PANEL` and `QUII_CHANNEL` are also accepted.
`AUTH_CODE` and `DEVICE_PASSWORD` are device-local credentials used by the
TCP/CGI probe helpers.

## Main Application Flow

The preview path is intentionally composed from separate classes:

- `quii_helper.camera.Camera` is the public high-level API for snapshots and recordings.
- `quii_helper.camera.CameraConnector` fetches credentials and opens a camera preview session.
- `quii_helper.camera.CameraPreviewSession` wraps the active tunnel and exposes setup/play/close operations.
- `quii_helper.preview.stream.TunnelPacketStream` reads packets from the tunnel.
- `quii_helper.preview.packet_processor.PreviewPacketProcessor` decodes and classifies incoming packets.
- `quii_helper.preview.output_writer.PreviewOutputWriter` writes image/video and optional diagnostics.
- `quii_helper.preview.application.CameraPreviewApplication` wires lower-level preview components for direct internal use.

## Package Layout

- `quii_helper.protocols`: protocol implementations and protocol-facing transports.
- `quii_helper.protocols.mqtt`: MQTT bootstrap/runtime for P2P session setup.
- `quii_helper.protocols.p2p`: P2P request/response models, UDP probes, transport packets.
- `quii_helper.protocols.quii`: QUII crypto, blob decode, URL and live packet builders.
- `quii_helper.protocols.rbudp`: RBUDP/KCP tunnel protocol implementation.
- `quii_helper.protocols.tcp`: TCP client and probe flow.
- `quii_helper.protocols.ust`: UST message/credential crypto helpers.
- `quii_helper.io`: runtime output paths and JSONL writer.
- `quii_helper.diagnostics`: payload/tail diagnostic helpers.
- `quii_helper.diagnostics.wrapped`: wrapped payload/tail diagnostics.
- `quii_helper.cloud`: cloud login, device token, service discovery.
- `quii_helper.device`: local CGI/device stream-key helpers.
- `quii_helper.direct`: direct P2P preview orchestration.
- `quii_helper.media`: media parsing, H.264 assembly, ffmpeg output, probe analysis.
- `quii_helper.preview`: application-level preview capture pipeline.

## Notes

Do not commit `.env`, generated files in `data/`, or local virtual environments.
