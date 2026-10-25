# QUII Helper 📹

[![PyPI](https://img.shields.io/pypi/v/quii-helper)](https://pypi.org/project/quii-helper/)
[![Python](https://img.shields.io/pypi/pyversions/quii-helper)](https://pypi.org/project/quii-helper/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/xaer981/quii-helper/blob/main/LICENSE)

Use QUII / Qualvision cameras and video intercoms from Python, without running
the original mobile app. Capture images and video, serve RTSP, inspect device
information, and explicitly open a connected door.

**Available on [PyPI](https://pypi.org/project/quii-helper/).**

[Features](https://github.com/xaer981/quii-helper#features-) ·
[Compatibility](https://github.com/xaer981/quii-helper#compatibility-) ·
[Quick Start](https://github.com/xaer981/quii-helper#quick-start-) ·
[RTSP](https://github.com/xaer981/quii-helper#rtsp-streaming-) ·
[Documentation](https://github.com/xaer981/quii-helper#documentation-) ·
[Safety](https://github.com/xaer981/quii-helper#safety-and-limitations-)

## Features ✨

| Feature | What you can do |
| --- | --- |
| LAN-only playback (default) | Connect by IP with a saved key/auth pair, without client-side cloud requests or fallback. |
| Snapshots | Capture a JPEG with `Camera.snapshot()`. |
| Recording | Save an MP4 clip with `Camera.save_video()`. |
| RTSP | Forward the live H.264 preview to a player such as VLC. |
| Stream-key bootstrap | Explicitly fetch/save a cloud key/auth pair, then reuse it for LAN-only playback. |
| Device inspection | Read supported cloud and local device information. |
| LAN discovery | Find devices exposing Qualvision-compatible services. |
| Call history | Read incoming-call cloud history with experimental `get_call_events()`. |
| Door control | Send an explicit local opening command with `Camera.open_door()`. |

Call history is **not** a live ringing subscription. Available device fields
and local commands depend on firmware; an unsupported query does not imply
that video capture is unsupported.

## Compatibility 🔍

- **Tantos Marilyn Wi-Fi s** with **vHome 2.2**: snapshots, MP4 capture, RTSP,
  door opening in `auto` mode, and incoming-call history on the tested backend.
- **Vimar K40955**, firmware **V401R001B002**, with **vEye Pro 1.9.4.0.2**:
  saved-key LAN RTSP, [confirmed by a user](https://github.com/xaer981/quii-helper/issues/5#issuecomment-6397243080)
  on 2026-10-25. Other features on this model remain unverified.

Tantos LAN playback and cloud-key bootstrap were also checked on a physical
Raspberry Pi (Linux ARM64). Its saved key still worked after more than 55 hours
without a client-side cloud request; the actual expiry remains unknown.

Related devices may return the HTTP header `Server: Qualvision -HTTPServer`
or expose TCP port `34567`. These are discovery hints, not proof of support.
See [Compatibility](https://github.com/xaer981/quii-helper/blob/main/COMPATIBILITY.md)
for per-device evidence, platform coverage, limitations, and reporting another
device. A working video stream does not establish support for door control,
call history, or two-way audio.

## Quick Start 🚀

### 1. Install

Use Python **3.10 or newer**, preferably in a virtual environment:

```shell
python -m pip install quii-helper
```

To upgrade, use `python -m pip install --upgrade quii-helper`.

### 2. Configure Your Application

`Camera` defaults to LAN-only playback: use the camera's IP and a saved
stream key/auth pair, with **no cloud requests or automatic fallback**.

There are two separate setup phases:

- **No saved key yet?** Complete the first-run cloud setup in step 3.
- **Already have a saved key for this camera?** Skip cloud setup and go
  straight to [step 4: LAN-only playback](https://github.com/xaer981/quii-helper#4-later-runs-lan-only-playback).

Prepare an application directory and run the following code from there:

```text
my-camera-app/
  app.py
  .env
  data/
    stream_credentials.json  # Created in step 3; keep private.
```

### 3. First Run: Cloud Setup And Key Save

**Local IP/channel/stream settings alone cannot obtain a key.** Before running
the cloud code below, fill **all 10 required variables** in `.env`:

```dotenv
CLOUD_ACCOUNT="<mobile-app-login>"
CLOUD_PASSWORD="<mobile-app-password>"
DEVICE_ID="<your-camera-device-id>"
CLOUD_CLIENT_UUID="<generate-once-with-command-below>"
CLOUD_AUTH_URL="<auth-url-for-your-app-and-region>"
CLOUD_SERVICE_URL="<service-discovery-base-url-from-your-app>"
CAMERA_OEM="<oem-from-your-app>"
CAMERA_APP_ID=<numeric-app-id>
CAMERA_CLIENT_TYPE=<numeric-client-type>
IP_REGION_ID=<numeric-region-id>
```

Replace every `<...>` placeholder with your own value before running anything.
The last three values must be positive integers, not the placeholder text.
Generate `CLOUD_CLIENT_UUID` once and keep it between runs:

```shell
python -c "import uuid; print(uuid.uuid4().hex)"
```

Copy the printed value into `CLOUD_CLIENT_UUID` in `.env`.

Find the other values using [Setup And APK Extraction](https://github.com/xaer981/quii-helper/blob/main/docs/setup.md#finding-apk-constants)
and [cloud discovery](https://github.com/xaer981/quii-helper/blob/main/docs/setup.md#discovering-cloud-values).
`CLOUD_SERVICE_URL` is required by shared validation even though key acquisition
does not perform discovery. `CLOUD_AUTH_VERSION` is additionally needed if your
app uses a versioned auth header. TLS verification defaults to enabled; see
[TLS troubleshooting](https://github.com/xaer981/quii-helper/blob/main/docs/setup.md#cloud-region-and-auth-url)
if a vendor certificate fails.

With these settings already known, this call needs cloud access but **no camera
IP, APK assets, FFmpeg, `AUTH_CODE`, or `STREAM_KEY`**. It obtains the matching
key/auth pair for you. Put this code in `app.py` and run `python app.py` once:

```python
from quii_helper import Camera, load_config

cloud_camera = Camera(config=load_config(), connection_mode="cloud")
credentials = cloud_camera.fetch_stream_credentials()
credentials.save("data/stream_credentials.json")
```

This saves `data/stream_credentials.json` without starting a preview or changing
`.env`. A failure here must be resolved before proceeding. Re-running this code
contacts cloud again and replaces the file; do not include it in normal LAN
startup. The library never fetches or renews a key automatically.

### 4. Later Runs: LAN-Only Playback

Keep the saved JSON for this camera. For this phase, `.env` only needs the
following local settings; replace the example IP with the camera's LAN IP:

```dotenv
CAMERA_CONNECTION_MODE=lan
CAMERA_DEVICE_HOST=192.0.2.10
CAMERA_STREAM_PORT=34567
CAMERA_CHANNEL=1
CAMERA_STREAM=2
```

The port/channel/stream above are defaults; select the correct channel/stream
for your device. You can remove cloud settings from this application's `.env`;
if retained, they are not used for this LAN connection. **No cloud account or
APK assets are needed.** The saved file supplies the device id and key/auth
pair; do not copy them into `.env` for this example.

For JPEG/MP4, install **FFmpeg** on `PATH` as described in
[Media Prerequisites](https://github.com/xaer981/quii-helper/blob/main/docs/setup.md#media-prerequisites).
RTSP does not need FFmpeg. Run from the directory containing `.env` and the
saved JSON: replace the bootstrap code in `app.py` with the following, then
run `python app.py`. Do not keep the cloud-fetch code in this script:

```python
from quii_helper import Camera, CameraStreamCredentials, load_config

saved = CameraStreamCredentials.load("data/stream_credentials.json")
camera = Camera(
    config=load_config(),
    connection_mode="lan",
    device_id=saved.device_id,
    stream_key=saved.stream_key,
    auth_code=saved.auth_code,
)

print(camera.snapshot())
print(camera.save_video(duration_seconds=15))
```

Both methods return a `pathlib.Path`. Default output goes to `./data/` with
timestamped names. Connection setup and file rendering add time to the media
collection window. See the [API reference](https://github.com/xaer981/quii-helper/blob/main/docs/api.md#capture-methods)
for timeouts, output paths, and capture results.

## RTSP Streaming 📡

Use the same saved file for a local live stream:

```python
from quii_helper import Camera, CameraStreamCredentials, load_config

saved = CameraStreamCredentials.load("data/stream_credentials.json")
camera = Camera(
    config=load_config(),
    connection_mode="lan",
    device_id=saved.device_id,
    stream_key=saved.stream_key,
    auth_code=saved.auth_code,
)

try:
    with camera.serve_rtsp(port=8554) as session:
        print(session.url)
        session.wait()
except KeyboardInterrupt:
    pass
```

Open `rtsp://127.0.0.1:8554/live` in VLC after media becomes available.
The context manager stops the server on exit; `session.wait()` reports
background failures and remains interruptible with `Ctrl+C`.

For a trusted LAN, pass `host="0.0.0.0"` and connect to the server's LAN IP,
not `0.0.0.0`. **There is no RTSP authentication or TLS.** Restrict access
with a firewall/VPN and never expose this port publicly.

Prefer runnable scripts? A [checkout](https://github.com/xaer981/quii-helper/blob/main/docs/setup.md#using-a-checkout)
includes `examples.cloud_key_rtsp` (fetch/save, then RTSP) and
`examples.lan_rtsp` (reuse the saved file, no cloud requests). Run them with
`python -m examples.<name>` from the repository root; they are not installed by pip.

## Documentation 📚

| I want to... | Read |
| --- | --- |
| Get a key, save it, then view locally | [Key Bootstrap And Reuse](https://github.com/xaer981/quii-helper/blob/main/docs/setup.md#stream-key-bootstrap-and-local-reuse) |
| Set up an account, assets, and `.env` | [Setup And APK Extraction](https://github.com/xaer981/quii-helper/blob/main/docs/setup.md) |
| Find methods, parameters, results, and errors | [Camera API Reference](https://github.com/xaer981/quii-helper/blob/main/docs/api.md) |
| Read call history | [Incoming Call History](https://github.com/xaer981/quii-helper/blob/main/docs/api.md#incoming-call-history-experimental) |
| Open a door explicitly | [Door Control](https://github.com/xaer981/quii-helper/blob/main/docs/api.md#door-control) |
| Resolve a setup failure | [Troubleshooting](https://github.com/xaer981/quii-helper/blob/main/docs/setup.md#troubleshooting) |
| Check platforms or report a device | [Compatibility](https://github.com/xaer981/quii-helper/blob/main/COMPATIBILITY.md) |
| Contribute or understand internals | [Contributing](https://github.com/xaer981/quii-helper/blob/main/CONTRIBUTING.md), [Protocol Notes](https://github.com/xaer981/quii-helper/blob/main/docs/protocol-notes.md) |

Library imports do not read `.env` or change application logging. Use
`load_config()` for file loading and see
[Logging](https://github.com/xaer981/quii-helper/blob/main/docs/api.md#logging)
to enable progress messages or diagnostics.

## Safety And Limitations 🔒

- Use only devices, accounts, and APKs you own or are authorized to access.
- Never share `.env`, extracted assets, private keys, raw logs, or camera media.
- Saved stream-credential JSON is also a secret: plaintext, not an encrypted
  vault. Keep it private and outside version control.
- LAN-only describes the client's network behavior, not the camera's own
  Internet access. Key lifetime and reboot persistence remain unknown.
- Keep TLS verification enabled. For vendor certificate failures, see the
  [TLS guidance](https://github.com/xaer981/quii-helper/blob/main/docs/setup.md#cloud-region-and-auth-url).
- Local CGI methods need an explicit camera LAN host and authentication code;
  preview/cloud credentials do not automatically configure local access.
- `open_door()` sends a **real command**. Acknowledgement is not proof of
  physical movement, and an uncertain outcome must not be retried automatically.
- The package is pre-`1.0`; experimental APIs and firmware compatibility have
  explicit limits. See the [Security Policy](https://github.com/xaer981/quii-helper/blob/main/SECURITY.md)
  and [Changelog](https://github.com/xaer981/quii-helper/blob/main/CHANGELOG.md).

<p align="center">
  <a href="https://github.com/xaer981"><img src="https://raw.githubusercontent.com/xaer981/xaer981/0aa64a3f8982d7dd0f90d5eaf2254ccc3d614994/main_cat.gif" alt="Animated cat" height="40" width="128"></a>
</p>
