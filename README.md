# QUII Helper 📹

Python package for connecting to QUII / Qualvision-based cameras and video doorbells from code.

It can capture snapshots, save short video clips, expose the camera as an RTSP stream, and read available device metadata without using the original mobile app.

## What It Does ✨

- 📸 Captures JPEG snapshots from the camera preview stream.
- 🎞 Saves MP4/H.264 video clips for a user-selected duration.
- 📡 Serves the live preview as an RTSP stream for players such as VLC.
- 🔎 Reads cloud, LAN, storage, network, product, alarm, video, and capability information where the device supports it.
- 🧭 Discovers local devices that expose Qualvision-compatible HTTP services.

## Compatibility 🔍

This project targets devices that use the QUII / Qualvision protocol family, including devices managed by the **vHome 2.2** mobile app.

Useful discovery hints:

- A direct HTTP request to the device IP may return `Server: Qualvision -HTTPServer`.
- Many compatible devices expose TCP port `34567`.
- Local read-only device methods usually require that your machine can reach the camera LAN IP.

Successfully tested devices:

- `Tantos Marilyn Wi-Fi s`

If another device works, please open an issue or pull request so the compatibility list can be expanded.

## Quick Start 🚀

Install the package in editable mode:

```powershell
git clone https://github.com/xaer981/quii-helper.git
cd quii-helper
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

Copy the required native assets extracted from the Android app into `assets/`:

```text
assets/
  ca.pem
  client.pem
  client.txt
  libqv-p2p-v2.so
```

Create `.env` from `.env.example` and fill in your account, device, cloud, and app constants:

```env
CLOUD_ACCOUNT=
CLOUD_PASSWORD=
DEVICE_ID=
CLOUD_CLIENT_UUID=
CLOUD_AUTH_URL=
CLOUD_SERVICE_URL=
CAMERA_OEM=
CAMERA_APP_ID=
CAMERA_CLIENT_TYPE=
IP_REGION_ID=
```

Detailed extraction instructions are in [docs/setup.md](docs/setup.md).

## Basic Usage 🧩

```python
from quii_helper import Camera

camera = Camera()

snapshot = camera.snapshot()
print(snapshot.path)

video = camera.save_video(duration_seconds=15)
print(video.path)
```

Start an RTSP stream:

```python
from quii_helper import Camera

camera = Camera()

with camera.serve_rtsp(port=8554) as session:
    print(session.url)
    input("Press Enter to stop streaming...")
```

Open the stream in VLC:

```text
rtsp://127.0.0.1:8554/live
```

Read device information:

```python
from quii_helper import Camera

camera = Camera()

print(camera.get_device_info())
print(camera.get_product_info())
print(camera.get_storage_info())
print(camera.get_network_info())
```

For the complete API reference, see [docs/api.md](docs/api.md).

## Logging 🧾

Set `LOG_LEVEL=info` for user-friendly progress messages:

```env
LOG_LEVEL=info
```

Set `LOG_LEVEL=debug` when collecting diagnostics for bug reports:

```env
LOG_LEVEL=debug
```

Debug logging includes protocol counters, packet statistics, decoding summaries, and connection details.

## Documentation 📚

- [Setup And APK Extraction](docs/setup.md)
- [Camera API Reference](docs/api.md)
- [Protocol Notes](docs/protocol-notes.md)
- [Compatibility Notes](COMPATIBILITY.md)
- [Contributing](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)

## Important Notes ⚠️

- Do not commit `.env`, `assets/`, `data/`, logs, screenshots, or recordings.
- The package depends on native crypto/material extracted from the original Android app version you use.
- Some local read-only methods return `error=-1` on devices that do not support that command.
- If cloud TLS fails with `CERTIFICATE_VERIFY_FAILED`, see [Cloud Region And Auth URL](docs/setup.md#cloud-region-and-auth-url).

## Status 🛠

The project is usable but still protocol-research-heavy. Public APIs are being stabilized around `Camera`, capture results, RTSP streaming, and read-only device inspection.

<p align=center>
  <a href="url"><img src="https://github.com/xaer981/xaer981/blob/main/main_cat.gif" align="center" height="40" width="128"></a>
</p>
