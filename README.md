# QUII Helper 📹

Python package for connecting to QUII / Qualvision-based cameras and video doorbells from code.

It can capture snapshots, save video clips, expose the camera as an RTSP stream, read available device metadata, and explicitly open a connected door without using the original mobile app.

## What It Does ✨

- 📸 Captures JPEG snapshots from the camera preview stream.
- 🎞 Saves MP4/H.264 video clips for a user-selected duration.
- 📡 Serves the live preview as an RTSP stream for players such as VLC.
- 🔎 Reads cloud, LAN, storage, network, product, alarm, video, and capability information where the device supports it.
- 🧭 Discovers local devices that expose Qualvision-compatible HTTP services.
- Reads incoming-call cloud history with the experimental [`get_call_events()` API](https://github.com/xaer981/quii-helper/blob/main/docs/api.md#incoming-call-history-experimental), without push registration or door commands.
- Sends explicit local door-opening commands with `Camera.open_door()`; see [Door Control](https://github.com/xaer981/quii-helper/blob/main/docs/api.md#door-control) for settings and acknowledgement semantics.

## Compatibility 🔍

This project targets devices that use the QUII / Qualvision protocol family, including devices managed by the **vHome 2.2** mobile app.

Useful discovery hints:

- A direct HTTP request to the device IP may return `Server: Qualvision -HTTPServer`.
- Many compatible devices expose TCP port `34567`.
- Local read-only device methods usually require that your machine can reach the camera LAN IP.

Successfully tested devices:

- `Tantos Marilyn Wi-Fi s`: snapshot, MP4 capture, RTSP, door opening in `auto` mode, and incoming-call cloud history on the tested account/backend.

History access does not guarantee live delivery or a maximum notification
delay. The library is also used by entrance-bot on Raspberry Pi ARM64; its
mocked integration tests cover that deployment, not ARM64 media capture.

If another device works, please open an issue or pull request so the compatibility list can be expanded.

## Quick Start 🚀

Use Python 3.10 or newer. For JPEG/MP4 output, also install the **FFmpeg
executable** and put it on `PATH` (`ffmpeg -version` must work in the same
environment). Installing this Python package does not install FFmpeg; see
[Media Prerequisites](https://github.com/xaer981/quii-helper/blob/main/docs/setup.md#media-prerequisites).
RTSP and read-only device methods do not require FFmpeg.

For development or the bundled examples, install from a checkout:

```powershell
git clone https://github.com/xaer981/quii-helper.git
cd quii-helper
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

For library use, install the published pre-release from
[PyPI](https://pypi.org/project/quii-helper/0.1.0rc6/):

```shell
python -m pip install "quii-helper==0.1.0rc6"
```

To install the latest available version, including pre-releases, use
`python -m pip install --upgrade --pre quii-helper`.
No repository checkout is needed for library use.
The wheel does **not** include `examples` or `.env.example`; use the
[installed-package setup](https://github.com/xaer981/quii-helper/blob/main/docs/setup.md#using-an-installed-package)
to create your own application directory and configuration.

Copy the required native assets extracted from the Android app into `assets/`:

```text
assets/
  ca.pem
  client.pem
  client.txt
  libqv-p2p-v2.so
```

Use the verified **vHome 2.2 arm64-v8a** `libqv-p2p-v2.so`, regardless of your
computer's architecture. Unsupported ELF/table layouts are rejected; files
from other ABIs or app builds are not interchangeable without native verification.

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

Detailed extraction instructions are in [docs/setup.md](https://github.com/xaer981/quii-helper/blob/main/docs/setup.md).

## Basic Usage 🧩

```python
from quii_helper import Camera, load_config

camera = Camera(config=load_config())

snapshot = camera.snapshot()
print(snapshot)

video = camera.save_video(duration_seconds=15)
print(video)
```

Start an RTSP stream:

```python
from quii_helper import Camera, load_config

camera = Camera(config=load_config())

try:
    with camera.serve_rtsp(port=8554) as session:
        print(session.url)
        session.wait()
except KeyboardInterrupt:
    pass
```

Open the stream in VLC:

```text
rtsp://127.0.0.1:8554/live
```

Alternatively, run `python -m quii_helper.main` to serve RTSP on port `8554`
until `Ctrl+C`. This entry point does not open the door.
RTSP binds to localhost by default. To serve a trusted LAN, explicitly pass
`host="0.0.0.0"` and use the server's LAN IP in the player. There is no RTSP
authentication or TLS: restrict access and do not expose the port publicly.
Examples honor `TLS_VERIFY` (enabled by default). The editable `main.py`
currently passes `tls_verify=False` for the owner's tested setup; remove that
override to use configured TLS verification.

Read device information:

```python
from quii_helper import Camera, load_config

camera = Camera(config=load_config())

print(camera.get_device_info())
print(camera.get_product_info())
print(camera.get_storage_info())
print(camera.get_network_info())
```

For the complete API reference, see [docs/api.md](https://github.com/xaer981/quii-helper/blob/main/docs/api.md).

`load_config()` explicitly reads `.env` from the working directory without
changing the process environment. For embedding, pass an `AutonomousConfig`
or use `Camera(...)` with process environment values and keyword arguments;
neither reads `.env` implicitly. Assets and default outputs belong to the
application (`./assets` and `./data`), not the installed package. See
[Library Configuration](https://github.com/xaer981/quii-helper/blob/main/docs/api.md#library-configuration).

## Logging 🧾

The standalone entry point and examples configure console logging explicitly.
Set `LOG_LEVEL=info` for user-friendly progress messages:

```env
LOG_LEVEL=info
```

Set `LOG_LEVEL=debug` when collecting diagnostics for bug reports:

```env
LOG_LEVEL=debug
```

Debug logging includes protocol counters, packet statistics, decoding summaries, and connection details.

Library logging is disabled by default and importing the package preserves
application Loguru sinks. To use your own logging setup, call
`logger.enable("quii_helper")` after importing the package. See
[Logging](https://github.com/xaer981/quii-helper/blob/main/docs/api.md#logging) for the optional console helper.

## Documentation 📚

- [Setup And APK Extraction](https://github.com/xaer981/quii-helper/blob/main/docs/setup.md)
- [Camera API Reference](https://github.com/xaer981/quii-helper/blob/main/docs/api.md)
- [Protocol Notes](https://github.com/xaer981/quii-helper/blob/main/docs/protocol-notes.md)
- [Compatibility Notes](https://github.com/xaer981/quii-helper/blob/main/COMPATIBILITY.md)
- [Contributing](https://github.com/xaer981/quii-helper/blob/main/CONTRIBUTING.md)
- [Security Policy](https://github.com/xaer981/quii-helper/blob/main/SECURITY.md)

## Important Notes ⚠️

- Do not commit `.env`, `assets/`, `data/`, logs, screenshots, or recordings.
- The package depends on native crypto/material extracted from the original Android app version you use.
- Some local read-only methods return `error=-1` on devices that do not support that command.
- If cloud TLS fails with `CERTIFICATE_VERIFY_FAILED`, see [Cloud Region And Auth URL](https://github.com/xaer981/quii-helper/blob/main/docs/setup.md#cloud-region-and-auth-url).
- From a checkout, `python -m examples.open_door` is an explicit door-control check. It prints capability 24 and sends a **real opening command** using `UNLOCK_PASSWORD` and `password_mode="auto"`; do not use it as a read-only smoke test.

## Status 🛠

The project is usable but still protocol-research-heavy. Public APIs are being stabilized around `Camera`, capture results, RTSP streaming, read-only device inspection, and explicit local door control.

<p align=center>
  <a href="https://github.com/xaer981"><img src="https://github.com/xaer981/xaer981/blob/main/main_cat.gif" align="center" height="40" width="128"></a>
</p>
