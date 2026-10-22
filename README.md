# QUII Helper 📹

[![PyPI](https://img.shields.io/pypi/v/quii-helper)](https://pypi.org/project/quii-helper/)
[![Python](https://img.shields.io/pypi/pyversions/quii-helper)](https://pypi.org/project/quii-helper/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/xaer981/quii-helper/blob/main/LICENSE)

Use QUII / Qualvision cameras and video intercoms from Python, without running
the original mobile app. Capture images and video, serve RTSP, inspect device
information, and explicitly open a connected door.

**The first final release, `0.1.0`, is available on
[PyPI](https://pypi.org/project/quii-helper/0.1.0/).**

[Features](https://github.com/xaer981/quii-helper#features-) ·
[Compatibility](https://github.com/xaer981/quii-helper#compatibility-) ·
[Quick Start](https://github.com/xaer981/quii-helper#quick-start-) ·
[RTSP](https://github.com/xaer981/quii-helper#rtsp-streaming-) ·
[Documentation](https://github.com/xaer981/quii-helper#documentation-) ·
[Safety](https://github.com/xaer981/quii-helper#safety-and-limitations-)

## Features ✨

| Feature | What you can do |
| --- | --- |
| Snapshots | Capture a JPEG with `Camera.snapshot()`. |
| Recording | Save an MP4 clip with `Camera.save_video()`. |
| RTSP | Forward the live H.264 preview to a player such as VLC. |
| Device inspection | Read supported cloud and local device information. |
| LAN discovery | Find devices exposing Qualvision-compatible services. |
| Call history | Read incoming-call cloud history with experimental `get_call_events()`. |
| Door control | Send an explicit local opening command with `Camera.open_door()`. |

Call history is **not** a live ringing subscription. Available device fields
and local commands depend on firmware; an unsupported query does not imply
that video capture is unsupported.

## Compatibility 🔍

The tested device is **Tantos Marilyn Wi-Fi s**, used with **vHome 2.2**:
snapshots, MP4 capture, RTSP, door opening in `auto` mode, and incoming-call
history on the tested account/backend.

Related devices may return the HTTP header `Server: Qualvision -HTTPServer`
or expose TCP port `34567`. These are discovery hints, not proof of support.
See [Compatibility](https://github.com/xaer981/quii-helper/blob/main/COMPATIBILITY.md)
for platform coverage and how to report another device.

## Quick Start 🚀

### 1. Install

Use Python **3.10 or newer**, preferably in a virtual environment:

```shell
python -m pip install quii-helper
```

To upgrade an existing installation, use
`python -m pip install --upgrade quii-helper`. No `--pre` is needed.

### 2. Configure Your Application

**Installing the package is not the complete camera setup.** Preview/RTSP
requires app-specific settings and assets extracted from an Android APK you
are authorized to use. The verified native asset is from **vHome 2.2,
arm64-v8a**, even when Python runs on Windows or Linux x86_64.

Follow [Setup And APK Extraction](https://github.com/xaer981/quii-helper/blob/main/docs/setup.md)
to prepare an application directory:

```text
my-camera-app/
  app.py
  .env
  assets/
    ca.pem
    client.pem
    client.txt
    libqv-p2p-v2.so
  data/                 # Generated output; created when needed.
```

The wheel does not include `.env.example` or the repository's `examples/`.
The setup guide explains both installed-package and checkout workflows.
JPEG/MP4 output also needs the external **FFmpeg executable** on `PATH`;
RTSP does not. Verify it with `ffmpeg -version`.

### 3. Capture Media

Run this from the directory containing your configured `.env` and `assets/`:

```python
from quii_helper import Camera, load_config

camera = Camera(config=load_config())

print(camera.snapshot())
print(camera.save_video(duration_seconds=15))
```

Both methods return a `pathlib.Path`. Default output goes to `./data/` with
timestamped names. Connection setup and file rendering add time to the media
collection window. See the [API reference](https://github.com/xaer981/quii-helper/blob/main/docs/api.md#capture-methods)
for timeouts, output paths, and capture results.

## RTSP Streaming 📡

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

Open `rtsp://127.0.0.1:8554/live` in VLC after media becomes available.
The context manager stops the server on exit; `session.wait()` reports
background failures and remains interruptible with `Ctrl+C`.

For a trusted LAN, pass `host="0.0.0.0"` and connect to the server's LAN IP,
not `0.0.0.0`. **There is no RTSP authentication or TLS.** Restrict access
with a firewall/VPN and never expose this port publicly.

## Documentation 📚

| I want to... | Read |
| --- | --- |
| Set up an account, assets, and `.env` | [Setup And APK Extraction](https://github.com/xaer981/quii-helper/blob/main/docs/setup.md) |
| Find methods, parameters, results, and errors | [Camera API Reference](https://github.com/xaer981/quii-helper/blob/main/docs/api.md) |
| Read call history | [Incoming Call History](https://github.com/xaer981/quii-helper/blob/main/docs/api.md#incoming-call-history-experimental) |
| Open a door explicitly | [Door Control](https://github.com/xaer981/quii-helper/blob/main/docs/api.md#door-control) |
| Resolve a setup failure | [Troubleshooting](https://github.com/xaer981/quii-helper/blob/main/docs/setup.md#troubleshooting) |
| Check platforms or report a device | [Compatibility](https://github.com/xaer981/quii-helper/blob/main/COMPATIBILITY.md) |
| Contribute or understand internals | [Contributing](https://github.com/xaer981/quii-helper/blob/main/CONTRIBUTING.md), [Protocol Notes](https://github.com/xaer981/quii-helper/blob/main/docs/protocol-notes.md) |

Library imports do not read `.env` or reconfigure application logging.
Use `load_config()` to opt into file loading. Console examples honor
`LOG_LEVEL=info` or `LOG_LEVEL=debug`; embedding applications enable logging
explicitly. See [Configuration](https://github.com/xaer981/quii-helper/blob/main/docs/api.md#library-configuration)
and [Logging](https://github.com/xaer981/quii-helper/blob/main/docs/api.md#logging).

## Safety And Limitations 🔒

- Use only devices, accounts, and APKs you own or are authorized to access.
- Never share `.env`, extracted assets, private keys, raw logs, or camera media.
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
