# QUII Helper

Python helpers for opening a QUII camera preview, receiving stream packets,
decoding media payloads, and saving snapshots or MP4 recordings.

Runtime files are written under `data/`. The repository keeps `data/.gitkeep`,
while generated captures, logs, binaries, and JSONL diagnostics are ignored by
git.

## Compatibility And Discovery

This package targets QUII/Qualvision-based cameras and video intercoms used by
the `vHome 2.2` mobile application. Devices in this family may expose a web
server that responds with the HTTP header `Server: Qualvision -HTTPServer` and
often have TCP port `34567` open.

Known working devices:

- `Tantos Marilyn Wi-Fi s`

## Setup

Before running the package on a new vendor app, extract the APK with `jadx`,
`apktool`, or `unzip`. The repository does not include vendor assets, private
keys, or app identity values.

Required files from the extracted APK:

- Copy `<extracted-apk>/assets/ca.pem` to `assets/ca.pem`.
- Copy `<extracted-apk>/assets/client.pem` to `assets/client.pem`.
- Copy `<extracted-apk>/assets/client.txt` to `assets/client.txt`.
- Copy `<extracted-apk>/lib/arm64-v8a/libqv-p2p-v2.so` to
  `assets/libqv-p2p-v2.so`.

`lib/armeabi-v7a/libqv-p2p-v2.so` is not recommended for the current code path
because the UST table offsets were matched against the arm64 library.

Create `.env` from `.env.example`. Required keys for cloud/P2P preview:

```dotenv
CLOUD_USERNAME=""
CLOUD_PASSWORD=""
DEVICE_ID=""
CLOUD_CLIENT_UUID=""
CLOUD_AUTH_URL=""
CLOUD_SERVICE_URL=""
CAMERA_OEM=""
CAMERA_APP_ID=
CAMERA_CLIENT_TYPE=
IP_REGION_ID=
```

Optional keys:

```dotenv
CLOUD_AUTH_VERSION=""
CAMERA_CHANNEL=1
CAMERA_STREAM=2
AUTH_CODE=""
DEVICE_PASSWORD=""
TLS_VERIFY=true
LOG_LEVEL=info
```

`CLOUD_AUTH_VERSION` may be empty for older auth protocol versions.
`AUTH_CODE` and `DEVICE_PASSWORD` are only used by TCP/CGI probe helpers, not
by the normal cloud/P2P preview flow. `CLOUD_ACCOUNT` is still accepted as a
legacy alias for `CLOUD_USERNAME`.

## Extracting Values

Find app-specific values in the decompiled Android app:

- `CAMERA_APP_ID`: search Java sources for `AppConfig.APP_ID`, usually in
  `.../publico/common/AppConfig.java`.
- `CAMERA_OEM`: use `AppConfig.OEM_ID`. Some builds override it through
  `SpUtil.getServiceId()` before `QvOpenSDK.setKey(...)`; if an override is
  present in app storage/logs, use that runtime service id instead.
- `CLOUD_SERVICE_URL`: use
  `https://{AppConfig.SERVER_ADDRESS}:{AppConfig.SERVER_PORT}`. This is the
  base URL used for service discovery (`/mst/query`).
- `CLOUD_AUTH_URL`: use the user-auth endpoint for the same app/region,
  normally `https://{auth-host}:{auth-port}/auth/user`. In Java, search for
  `UserApi`, `DownChannelManager`, `QvLocationManager.getCurrentUrl(0)`, or
  `/auth/user`; the host is the current auth service selected by the app.
- `CLOUD_AUTH_VERSION`: search for `AppConfig.AUTH_VERSION_CODE` and
  `QvCore.setAuthVersionCode(...)`. The current SDK maps code `0` to an empty
  string, code `1` to `v1.10`, and code `2` to `v1.13`.
- `CAMERA_CLIENT_TYPE`: search for
  `QvAlarmCore.getInstance().initParams(...)`; the second argument is the
  client type used in user-auth headers.
- `IP_REGION_ID`: runtime region state, not a simple `AppConfig` constant.
  Search for `QvLocationManager.getCurrentIpRegionId()`,
  `currentIpRegionId`, `LoginReqContent`, and `redirect-region-id`. Use the
  IP region id saved by the original app after login/service discovery, or the
  `redirect-region-id` returned by a successful original-app login.
- `CLOUD_CLIENT_UUID`: use a stable per-install client id. The original app
  passes `DataUtils.getUniqueId(application)` into SDK initialization. For
  this package it can be a generated UUID, but keep it stable between runs.
- `DEVICE_ID`: camera UID/device id from the original app, QR code, label, or
  cloud device list.

For cloud/P2P preview, the camera LAN IP and UDP port are discovered from the
P2P response. A user-provided device IP is not required.

Do not commit `.env` or extracted APK assets. They include credentials,
private keys, and native libraries.

## Usage

Use `quii_helper.Camera` as the high-level API. By default it reads settings
from `.env`.

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

For reusable application code, pass credentials and app identity explicitly
instead of depending on process-level environment:

```python
from quii_helper import Camera

camera = Camera(
    device_id="12345qwes6ca",
    cloud_username="account@example.com",
    cloud_password="password-or-sha256",
    client_id="client-uuid",
    auth_url="https://auth-host:443/auth/user",
    service_url="https://service-host:443",
    oem="G0000",
    app_id=4000,
    client_type=3,
    ip_region_id=1,
)

snapshot_path = camera.snapshot(timeout_seconds=5)
```

Stream quality can be selected explicitly. The native app defaults to stream
`2` (`low`/`sd`), while stream `1` (`high`/`hd`) requests a higher-quality
preview when the camera supports it:

```python
camera = Camera(stream_quality="high")  # ids=1
camera = Camera(stream_quality="low")   # ids=2, native default
camera = Camera(stream=1)               # direct numeric stream id
```

Optional explicit output names are normalized into `data/`:

```python
camera.snapshot(output_path="front-door.jpg")
camera.save_video(10, output_path="front-door.mp4")
```

RTSP serving keeps running until the context is closed. The default status
callback logs the RTSP URL after the camera has started producing media:

```python
with camera.serve_rtsp(port=8554) as rtsp_stream:
    rtsp_stream.wait()
```

`snapshot(timeout_seconds=...)` waits up to that many seconds for a decodable
frame. `save_video(duration_seconds=...)` reads the live stream for the
requested duration before writing the MP4.

Set `LOG_LEVEL=debug` to enable protocol diagnostics, packet summaries, and
full capture summaries. The default `LOG_LEVEL=info` prints short progress
messages such as connection, media receiving, and completion status.

`TLS_VERIFY=true` is the default and verifies HTTPS certificates for cloud and
device requests. Set `TLS_VERIFY=false` only when working with vendor endpoints
that use non-public or hostname-mismatched certificates.

Debug HTTP dumps redact common credential fields such as passwords, tokens,
session ids, cookies, and dynamic media keys before logging. Treat debug logs
as sensitive anyway because they can still contain device ids, IP addresses,
and private operational metadata.

## Protocol Notes

The default live play request uses `live_play_payload="path"`, matching the
Java live URL flow used by `QvPlayerCore.startPlay` /
`QvLtPlayerCore.startPlayCompat` for
`/mode=real&idc=...&ids=...&ap=...`. `live_play_payload="oem"` is kept as a
protocol experiment for the SDK custom-id path, but it did not start media on
the current direct/LAN tunnel.

By default `play_sync_iterations=0`, so synthetic RBUDP play-sync control
packets are disabled. Use a positive value only as a protocol diagnostic
experiment; native RBUDP clears its send-list from ACK `remote_id` values, so
synthetic ACK-like packets can suppress data that was not actually received.

Synthetic play probes are disabled by default with `enable_play_probes=False`.
The fixed probe payloads were not found in the native player binaries, so this
option should only be used for diagnostics against older captured behavior.

## Package Layout

- `quii_helper.camera`: public high-level API for snapshots and recordings.
- `quii_helper.cloud`: cloud login, device token, service discovery.
- `quii_helper.direct`: direct P2P preview orchestration.
- `quii_helper.preview`: application-level preview capture pipeline.
- `quii_helper.media`: media parsing, H.264 assembly, ffmpeg output, probe analysis.
- `quii_helper.protocols`: protocol implementations and protocol-facing transports.
- `quii_helper.protocols.mqtt`: MQTT bootstrap/runtime for P2P session setup.
- `quii_helper.protocols.p2p`: P2P request/response models, UDP probes, transport packets.
- `quii_helper.protocols.quii`: QUII crypto, blob decode, URL and live packet builders.
- `quii_helper.protocols.rbudp`: RBUDP/KCP tunnel protocol implementation.
- `quii_helper.protocols.tcp`: TCP client and probe flow.
- `quii_helper.protocols.ust`: UST message/credential crypto helpers.
- `quii_helper.io`: runtime output paths and JSONL writer.
- `quii_helper.diagnostics`: payload/tail diagnostic helpers.
