# Setup And APK Extraction

[Documentation](README.md) | [API Reference](api.md) | [Compatibility](../COMPATIBILITY.md)

QUII Helper is a library, not a replacement mobile-app installer. Some setup
values must be obtained from your account/device and the original Android app.
Use only software and devices you are authorized to inspect.

## Contents

- [Install from PyPI](#using-an-installed-package) or [use a checkout](#using-a-checkout).
- [Choose the inputs for your operation](#what-your-operation-needs).
- [Extract assets](#required-assets) and [find APK constants](#finding-apk-constants).
- [Fill environment settings](#environment-settings) and [discover cloud values](#discovering-cloud-values).
- [Run a first check](#first-read-only-check) and [install FFmpeg](#media-prerequisites).
- [Handle TLS failures](#cloud-region-and-auth-url), [ARM64](#installing-on-linux-arm64), and [other errors](#troubleshooting).

## Using An Installed Package

Use Python **3.10 or newer**. Version `0.1.0` is available on
[PyPI](https://pypi.org/project/quii-helper/0.1.0/).

Create an application directory and a virtual environment. On Windows:

```powershell
mkdir my-camera-app
cd my-camera-app
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install quii-helper
```

On Linux/macOS, activate the environment with `source .venv/bin/activate`
instead. Check platform restrictions in [Compatibility](../COMPATIBILITY.md).
Use `python -m pip install --upgrade quii-helper` to upgrade an existing
installation; no `--pre` is needed for final releases.

The wheel installs `quii_helper`, not `examples/`, `docs/`, or `.env.example`.
Download the [environment template](https://github.com/xaer981/quii-helper/blob/main/.env.example)
and save a filled-in copy as `.env` in your application directory. For a pinned
version, use the template at its matching Git tag. Do not edit `site-packages`.

## Using A Checkout

A checkout is needed for bundled examples and the discovery helper. This is
separate from installing the library into your own application:

```powershell
git clone https://github.com/xaer981/quii-helper.git
cd quii-helper
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
Copy-Item .env.example .env
```

On Linux/macOS, use `source .venv/bin/activate` and `cp .env.example .env`.
Run `python -m examples.<name>` from this checkout's root. The extracted source
distribution also contains examples; a wheel installation does not.
Contributor tooling is covered in [Contributing](../CONTRIBUTING.md).

## What Your Operation Needs

| Operation | Inputs and prerequisites |
| --- | --- |
| Snapshot, MP4, RTSP | Cloud/app settings, device id, native assets, and a working preview connection. JPEG/MP4 also needs FFmpeg. |
| `get_device_info()` | Cloud account/device and app settings. It does not start a media session or discover the LAN host. |
| `get_call_events()` | Cloud/app settings and service-discovery TLS assets; no LAN host or FFmpeg. |
| Local CGI inspection | Reachable `CAMERA_DEVICE_HOST` and `AUTH_CODE`; no implicit cloud login, APK assets, or FFmpeg. |
| `open_door()` with an explicit password mode | Local CGI settings and `UNLOCK_PASSWORD`; no cloud lookup, APK assets, or FFmpeg. |
| `open_door(password_mode="auto")` | Local door settings plus cloud metadata if capability 24 is not already cached. |
| LAN discovery | Access to the local network; no account login or opening command. |

Do not enter every credential just to perform a local-only query. Conversely,
cloud/P2P preview does not need `CAMERA_DEVICE_HOST`: it selects peers from
the cloud/P2P response. Local CGI methods require that host explicitly.

## Required Assets

For preview/RTSP, put these files in the application's `assets/` directory:

```text
assets/
  ca.pem
  client.pem
  client.txt
  libqv-p2p-v2.so
```

| File | Source and purpose |
| --- | --- |
| `ca.pem` | Vendor CA material used for service discovery; look in APK assets/resources. |
| `client.pem` | Vendor client certificate for mutual TLS service discovery. |
| `client.txt` | Matching client private key; do not publish or paste its contents. |
| `libqv-p2p-v2.so` | `lib/arm64-v8a/libqv-p2p-v2.so` from the verified vHome 2.2 build; read for crypto tables. |

Use [JADX](https://github.com/skylot/jadx) for Java sources and
[Apktool](https://apktool.org/docs/cli-parameters/) for resources. For example,
with these tools already installed, decode an authorized `vendor.apk` into
ignored working directories:

```shell
jadx -d data/apk-java vendor.apk
apktool d vendor.apk -o data/apk-resources
```

In these outputs, inspect `data/apk-java/sources/` for Java classes and
`data/apk-resources/assets/`, `res/raw/`, and `lib/arm64-v8a/` for resources.
Some other decompilers name the source directory `java_src/`. Resource names
can vary; follow the application's certificate-loading code rather than
renaming an unrelated key or certificate.

The `.so` is read as data, **never loaded or executed**. Use the verified
`arm64-v8a` file on every host architecture. The loader validates its ELF/table
profile; another ABI, truncated file, or incompatible build raises
`AssetMissingError`. The fallback location
`assets/lib/arm64-v8a/libqv-p2p-v2.so` is also accepted.

Other APK builds are not automatically supported. The fingerprints validate
compatibility, not APK provenance. See
[Native Crypto Asset Validation](protocol-notes.md#native-crypto-asset-validation).
You can choose another application asset directory with `load_config(assets_dir=...)`
or `Camera(assets_dir=...)`; nothing belongs inside `site-packages`.

## Finding APK Constants

Begin with the app that successfully connects to your device. Do not copy
another user's account details, device id, or region-specific constants.

| Value | Where to look |
| --- | --- |
| `CLOUD_SERVICE_URL` | The base address passed to native service discovery (`/mst/query`), not the user-login URL. Trace P2P/service initialization. |
| `CAMERA_OEM`, `CAMERA_APP_ID`, `CAMERA_CLIENT_TYPE` | Application/SDK initialization and cloud request headers. Search for OEM, app-id, and client-type setters and trace their callers. |
| `CLOUD_AUTH_URL`, `IP_REGION_ID` | The app's selected cloud region or the [discovery helper](#discovering-cloud-values). |
| `CLOUD_AUTH_VERSION` | The XML header version selected by the app's auth implementation; leave empty only where that app uses the unversioned variant. |
| `DEVICE_ID` | Your device's account entry, label/QR data, or app device details. Do not confuse it with a client UUID. |
| `AUTH_CODE` | The device binding/CGI authentication value used by the app's local request header; not the cloud password or door password. |
| `UNLOCK_PASSWORD` | The separately configured door-opening password. Needed only for explicit door control. |

Useful classes in the inspected vHome source include `QvP2PClientV2`,
`UserApi`, and the userauth request `Header`. Class/package names and
obfuscation vary between builds. An IDE's find-references view helps trace
an initializer value back to the app configuration.

The discovery helper does **not** decompile the APK or recover every setting.
Extract its prerequisite values and TLS assets first. If the app keeps a value
only in native code, inspect that build in Ghidra rather than guessing a default.
Do not paste extracted passwords, private keys, or account traffic into an issue.

## Environment Settings

Start from `.env.example`. Keep one `.env` per application, outside
`site-packages` and out of version control.

### Cloud And Preview

These values configure cloud-backed operations and preview:

| Variable | Meaning |
| --- | --- |
| `CLOUD_ACCOUNT` | Your mobile-app account login. `CLOUD_USERNAME` is a legacy alias. |
| `CLOUD_PASSWORD` | Your mobile-app account password. |
| `DEVICE_ID` | The camera/intercom identifier for that account. |
| `CLOUD_CLIENT_UUID` | Stable per-install client identity, generated once below. |
| `CLOUD_SERVICE_URL` | Service-discovery base URL extracted from the app. |
| `CLOUD_AUTH_URL` | Region-specific auth endpoint; the helper can discover it. |
| `CAMERA_OEM` | App/OEM family identifier from the APK. |
| `CAMERA_APP_ID` | Numeric app identifier from the APK. |
| `CAMERA_CLIENT_TYPE` | Numeric client type from the APK. |
| `IP_REGION_ID` | Numeric cloud region id, returned by discovery. |
| `CLOUD_AUTH_VERSION` | Auth XML version required by that app build; default empty. |

Generate the client UUID once, copy it into `.env`, and keep it between runs:

```shell
python -c "import uuid; print(uuid.uuid4().hex)"
```

### Local Access And Preferences

| Variable | Meaning and default |
| --- | --- |
| `CAMERA_DEVICE_HOST` | LAN host/IP for local CGI queries and door control. No automatic cloud/P2P fallback. |
| `AUTH_CODE` | CGI authentication code. Required for local CGI queries and door control. |
| `UNLOCK_PASSWORD` | Separate opening password. Used only by explicit `open_door()` calls. |
| `DEVICE_PASSWORD` | Password for low-level development/probe helpers; not a `Camera` unlock setting. |
| `CAMERA_CHANNEL` | Default video-panel channel; `1`. |
| `CAMERA_STREAM` | Default stream id; `2` (lower bandwidth). `1` selects the high-quality stream on the tested device. |
| `TLS_VERIFY` | Certificate verification; `true`. Disabling it weakens cloud/device trust. |
| `LOG_LEVEL` | Standalone/example console level; `info`, or `debug` for diagnostics. |

For an explicit high/low selector in code, use
`Camera(config=load_config(), stream_quality="high")` or `"low"`.
Device support can differ. `stream` and `stream_quality` are
mutually exclusive overrides.

`load_config()` reads `.env` explicitly through python-dotenv's non-mutating
`dotenv_values()` reader. Process environment values take precedence.
`Camera()` alone uses process environment values, not `.env` files; a plain
`AutonomousConfig` reads neither. See [Library Configuration](api.md#library-configuration)
for precedence, paths, and embedding.

## Discovering Cloud Values

Run this only from a [checkout](#using-a-checkout) or extracted source
distribution. Before running, fill **`CLOUD_SERVICE_URL`, `CAMERA_OEM`, and
`CLOUD_CLIENT_UUID`** in `.env`, and install the TLS files in `assets/`.
This discovery step does not need the cloud account password.

```shell
python -m examples.discover_env_values
```

Copy the returned `IP_REGION_ID` and recommended `CLOUD_AUTH_URL` into `.env`.
The script also prints raw service addresses for inspection; those are not
all interchangeable with the auth URL. It does not discover your app id,
client type, device credentials, or door password.

For a pip-only application, use a separate checkout to run this helper, then
transfer only the needed settings/assets into your application directory.
Do not edit the installed library to add personal constants.

## First Read-Only Check

Save this as `app.py` next to your configured `.env` and `assets/`:

```python
from pathlib import Path

from quii_helper import Camera, load_config

application_dir = Path(__file__).resolve().parent
camera = Camera(
    config=load_config(project_root=application_dir),
    data_dir=application_dir / "data",
)
info = camera.get_device_info()
print(info)
```

Run `python app.py`. This logs into the cloud and reads device metadata; it
does not start a preview or open the door. Sparse metadata may be normal for
the firmware. Local `get_product_info()` and similar methods need the separate
LAN host and `AUTH_CODE`; see [Local Methods](api.md#local-device-read-only-methods).

After this succeeds, try `snapshot()`, `save_video()`, or the
[RTSP example](api.md#rtsp-streaming). These are real camera operations, not
offline installation checks. The dedicated `examples.open_door` script sends
a **real opening command** and must never be used as a read-only smoke test.

## Media Prerequisites

JPEG/MP4 rendering invokes the external **FFmpeg executable**. Install a build
from [FFmpeg](https://ffmpeg.org/download.html) or your Linux package manager,
put its executable directory on `PATH`, and restart the terminal/service if
needed. On Windows, that directory must contain `ffmpeg.exe`.

Check from the same environment that runs your application:

```shell
ffmpeg -version
```

Neither pip nor QUII Helper installs FFmpeg. RTSP, raw H.264, metadata queries,
and door control do not need it. Rendering failures report the failure and
retained raw H.264 path rather than claiming a missing JPEG/MP4 was saved.

## Cloud Region And Auth URL

Use the auth endpoint selected by your app build/region. Decompiled traffic
may include `;jus_duplex=up`; the helper omits this suffix from its recommended
`.env` value. It is not required for the tested flow. Do not append it to every
service address or replace a discovery base URL with an auth endpoint.

For `CERTIFICATE_VERIFY_FAILED`, first check the system clock, vendor hostname,
and certificate files. If your vendor endpoint still needs an explicit bypass:

```python
from quii_helper import Camera, load_config

camera = Camera(config=load_config(), tls_verify=False)
```

The configuration class is **`AutonomousConfig`**, not `AnonymousConfig`;
its equivalent option is `AutonomousConfig(tls_verify=False, ...)`.
For examples/the discovery helper, opt in with `TLS_VERIFY=false` in `.env`.

**Disabling verification permits interception or spoofing of server responses.**
Keep verification enabled where possible, especially if cloud history informs
an access-control application. A per-camera override does not update `.env`.

## Installing On Linux ARM64

Use an ARM64-compatible Python environment and current pip. Prefer compatible
binary dependency wheels rather than copying Windows/x86 packages or building
native dependencies on a small device:

```shell
python -m pip install --only-binary=:all: quii-helper
python -m pip check
```

This fails explicitly if compatible wheels are unavailable for that platform.
The separately extracted `.so` must still be the verified **arm64-v8a** asset.
The external PyPI `kcp` package is not needed. FFmpeg is separate.

Earlier ARM64 checks cover installation and mocked entrance-bot integration,
not live media capture. See the [validation matrix](../COMPATIBILITY.md#validation-scope)
for the exact scope; they do not certify every new PyPI build on ARM64.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `ModuleNotFoundError: quii_helper` | Activate the environment where the package was installed; use that interpreter's `python -m pip`. |
| `No module named examples` | Examples are checkout/source-distribution tools. Run `python -m examples.<name>` from that root, not a wheel-only application. |
| Missing app-specific configuration | Complete the cloud/app values, and pass `config=load_config()` if using `.env`. |
| `AssetMissingError` | Check `assets_dir`, required files, and the verified vHome ABI/table profile. Do not substitute an arbitrary `.so`. |
| `CERTIFICATE_VERIFY_FAILED` | Follow [TLS guidance](#cloud-region-and-auth-url); do not disable verification silently. |
| Missing `CAMERA_DEVICE_HOST` / `AUTH_CODE` | Local CGI settings are separate from cloud/P2P credentials. Supply the host explicitly. |
| Device `error=-1` with empty content | Often an unsupported/rejected firmware command. Inspect the raw response or profile status; do not assume every device implements every query. |
| Missing JPEG/MP4 | Check FFmpeg in the application's environment and inspect the capture error/summary and retained H.264. |
| VLC cannot connect | Wait for media readiness; check the bind host, server LAN IP, firewall, and producer error from `session.wait()`. |
| No console progress in library code | Logging is disabled by default. Enable it explicitly as described in [Logging](api.md#logging). |
| Empty or repeated call history | History is not a live subscription. Read a fresh page and compare record ids; do not infer a new ring from old rows. |

Collect `LOG_LEVEL=debug` diagnostics only when needed. Redact credentials,
tokens, device ids, IPs, and private media before sharing. Do not upload `.env`,
APK resources, or `assets/`; keep originals local rather than deleting them
as a troubleshooting step. See [Security](../SECURITY.md).
