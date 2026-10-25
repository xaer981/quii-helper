# Setup And APK Extraction

[Documentation](README.md) | [API Reference](api.md) | [Compatibility](../COMPATIBILITY.md)

LAN playback needs the camera IP and a saved stream key/auth pair. To acquire
that pair through cloud, you also need account/app settings from your device
and the original Android app. Use only software and devices you are authorized
to inspect.

## Contents

- [Install from PyPI](#using-an-installed-package) or [use a checkout](#using-a-checkout).
- [Choose the inputs for your operation](#what-your-operation-needs).
- [Get a stream key and reuse it locally](#stream-key-bootstrap-and-local-reuse).
- [Extract assets](#required-assets) and [find APK constants](#finding-apk-constants).
- [Fill environment settings](#environment-settings) and [discover cloud values](#discovering-cloud-values).
- [Run a first check](#first-read-only-check) and [install FFmpeg](#media-prerequisites).
- [Handle TLS failures](#cloud-region-and-auth-url), [ARM64](#installing-on-linux-arm64), and [other errors](#troubleshooting).

## Using An Installed Package

Use Python **3.10 or newer**. Install the latest final release from
[PyPI](https://pypi.org/project/quii-helper/).

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
Create `.env` in your application directory using the
[first-run cloud block](#first-run-fetch-and-save) or, if you already have a
saved key, the [later LAN-only block](#later-runs-load-and-view-locally).
The full [environment template](https://github.com/xaer981/quii-helper/blob/main/.env.example)
also covers other operations; not every setting is needed for playback.
For a pinned version, use the template at its matching Git tag.
Do not edit `site-packages`.

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

LAN-only is the default for capture and RTSP. It needs an explicit IP and a
saved key/auth pair, not APK assets or cloud account settings. Cloud queries,
key acquisition and cloud/P2P preview require `connection_mode="cloud"`.

| Operation | Inputs and prerequisites |
| --- | --- |
| LAN snapshot, MP4, RTSP (default) | Reachable `CAMERA_DEVICE_HOST`, TCP port `CAMERA_STREAM_PORT` (default `34567`), saved key/auth pair from JSON or `STREAM_KEY` / `AUTH_CODE`, and channel/stream. JPEG/MP4 also needs FFmpeg. |
| Explicit cloud stream-key bootstrap | Cloud account, device id, app/region settings and auth URL. Shared validation also requires the service URL, but no discovery, P2P assets, FFmpeg or device connection is used. |
| Cloud/P2P snapshot, MP4, RTSP | Explicit cloud mode, cloud/app settings, device id, native assets, and a working preview connection. JPEG/MP4 also needs FFmpeg. |
| `get_device_info()` | Explicit cloud mode, cloud account/device and app settings. It does not start a media session or discover the LAN host. |
| `get_call_events()` | Explicit cloud mode, cloud/app settings and service-discovery TLS assets; no LAN host or FFmpeg. |
| Local CGI inspection | Reachable `CAMERA_DEVICE_HOST` and `AUTH_CODE`; no implicit cloud login, APK assets, or FFmpeg. |
| `open_door()` with an explicit password mode | Local CGI settings and `UNLOCK_PASSWORD`; no cloud lookup, APK assets, or FFmpeg. |
| `open_door(password_mode="auto")` | Local door settings plus known capability 24. An uncached cloud lookup requires explicit cloud mode; LAN mode rejects unknown capability before sending. |
| LAN discovery | Access to the local network; no account login or opening command. |

Do not enter every credential just to perform a local-only query. Conversely,
cloud/P2P preview does not need `CAMERA_DEVICE_HOST`: it selects peers from
the cloud/P2P response. Local CGI methods require that host explicitly.

LAN supports AES-256/SHA256 with no separate media encryption. The key must
contain exactly 32 UTF-8 bytes; it is not hex/base64-decoded or padded. Use its
matching auth code, not the cloud account or door password.

## Stream-Key Bootstrap And Local Reuse

**Fetch once, then reuse locally.** These are separate steps; loading a file
or connecting in LAN mode never fetches or renews a key automatically.

If you already have `stream_credentials.json` for this camera, skip the cloud
setup and go directly to [later LAN-only runs](#later-runs-load-and-view-locally).
Run the snippets below from the application directory containing `.env`;
`data/stream_credentials.json` is relative to that directory.

### First Run: Fetch And Save

**All 10 variables below are required for cloud key acquisition.** The camera's
IP, channel and stream alone are not sufficient. Put these in `.env`, replacing
every `<...>` placeholder before running the Python snippet:

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

`CAMERA_APP_ID`, `CAMERA_CLIENT_TYPE` and `IP_REGION_ID` must be positive
integers from your app/region, not the placeholder text or guessed defaults.
Generate `CLOUD_CLIENT_UUID` once, put the result in `.env`, and keep it:

```shell
python -c "import uuid; print(uuid.uuid4().hex)"
```

The [cloud settings reference](#cloud-and-preview) explains every required
variable. Use your mobile-app account and device id; obtain the app/region
values via [APK inspection](#finding-apk-constants) and, if needed,
[discovery](#discovering-cloud-values). If those values are not known yet,
complete that preparation before requesting the key.

`CLOUD_AUTH_VERSION` is additionally needed for an app using a versioned auth
header; leave it empty only for the unversioned variant. `TLS_VERIFY` defaults
to `true`; use the [TLS guidance](#cloud-region-and-auth-url) for certificate
failures rather than disabling verification by default.

The bootstrap uses ordinary cloud login and `get-device-token`. With a known
auth URL and the complete settings above, it does not read APK assets or contact
the camera. `CLOUD_SERVICE_URL` is still required by shared validation, although
this operation does not send a discovery query. Discovery itself needs the
[TLS assets](#required-assets).

**Not needed for key acquisition:** `CAMERA_DEVICE_HOST`, channel/stream,
`AUTH_CODE`, `STREAM_KEY`, `UNLOCK_PASSWORD`, or FFmpeg. The cloud response
supplies the matching key/auth pair; no door command is involved.

Put this code in `app.py` in your application directory and run `python app.py`:

```python
from quii_helper import Camera, load_config

cloud_camera = Camera(config=load_config(), connection_mode="cloud")
credentials = cloud_camera.fetch_stream_credentials()
saved_path = credentials.save("data/stream_credentials.json")
print(saved_path)
```

This honors `TLS_VERIFY`, saves the matching pair without starting a preview,
and does not edit `.env` or open a door. Re-running it fetches again and replaces
the file; reuse the saved file for normal playback. If fetching or saving fails,
resolve that error before proceeding to the LAN-only step.

### Later Runs: Load And View Locally

Keep the saved JSON for the intended camera. For playback, `.env` needs only
these local settings, with your camera's actual IP/channel/stream:

```dotenv
CAMERA_CONNECTION_MODE=lan
CAMERA_DEVICE_HOST=192.0.2.10
CAMERA_STREAM_PORT=34567
CAMERA_CHANNEL=1
CAMERA_STREAM=2
```

The TCP port defaults to `34567`, channel to `1`, and stream to `2`; adjust
them only as needed for your device. You can remove cloud account/app settings
from this application's `.env`; valid values left there do not cause cloud
requests in LAN mode. `assets/` can also be absent. The JSON supplies device id,
stream key and auth code, so this example needs none of those values in `.env`.
It does not contain the camera IP, which must still be configured above.

Replace the cloud-fetch code in `app.py` with the following and run
`python app.py`. This loads the saved file explicitly and starts RTSP;
do not keep the bootstrap call in this script:

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

Open `rtsp://127.0.0.1:8554/live` in VLC on the same machine once media arrives.
Use `Ctrl+C` to stop. This phase never contacts cloud, even if cloud settings
remain in `.env`. Missing files, invalid keys and connection errors fail without
renewal or fallback. Use `camera.snapshot()` or `camera.save_video(15)` instead
for JPEG/MP4; these also need [FFmpeg](#media-prerequisites).

If you already have the raw pair, you can set `AUTH_CODE` / `STREAM_KEY` in
`.env` and use `Camera(config=load_config())` without a JSON file. Keep
`CAMERA_CONNECTION_MODE=lan`; set `cloud` only to use cloud/P2P preview instead.

In a [checkout](#using-a-checkout), `python -m examples.cloud_key_rtsp` combines
bootstrap/save with RTSP. For later saved-file starts use
`python -m examples.lan_rtsp`. The other media examples use `.env` key/auth
values, not the saved file. See [All Examples](api.md#application-entry-point).

The credential file is plaintext, not an encrypted vault. Keep it outside
version control in a private directory; Unix files use `0600`, while Windows
requires a restricted folder ACL. The file stores no cloud account password,
session or opening password. It also does not store/discover the current IP.
Do not use a file belonging to another device.

Saved-key LAN RTSP has maintainer validation on Tantos and a community success
report on Vimar K40955. Other features are not established by that report;
see [Compatibility](../COMPATIBILITY.md) for per-model scope and prerequisites.
The Tantos key still worked after more than 55 hours, but maximum key lifetime,
reboot persistence and operation with the camera's own Internet access blocked
remain unknown. If a key stops working, bootstrap again only as an explicit
application action.

## Required Assets

For **cloud/P2P** preview/RTSP, put these files in the application's `assets/`
directory. Direct LAN playback with supplied credentials does not read them:

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

The first **10** variables in this table are mandatory for stream-key bootstrap
and the shared cloud configuration. `CLOUD_AUTH_VERSION` is conditional on the
app's auth format. These are not prerequisites for saved-key LAN playback.
See [first-run setup](#first-run-fetch-and-save) for the complete `.env` block.

| Variable | Meaning |
| --- | --- |
| `CLOUD_ACCOUNT` | Your mobile-app account login. `CLOUD_USERNAME` is a legacy alias. |
| `CLOUD_PASSWORD` | Your mobile-app account password. |
| `DEVICE_ID` | The camera/intercom identifier for that account. |
| `CLOUD_CLIENT_UUID` | Stable per-install client identity; generate once as shown in [first-run setup](#first-run-fetch-and-save). |
| `CLOUD_SERVICE_URL` | Service-discovery base URL extracted from the app. |
| `CLOUD_AUTH_URL` | Region-specific auth endpoint; the helper can discover it. |
| `CAMERA_OEM` | App/OEM family identifier from the APK. |
| `CAMERA_APP_ID` | Numeric app identifier from the APK. |
| `CAMERA_CLIENT_TYPE` | Numeric client type from the APK. |
| `IP_REGION_ID` | Numeric cloud region id, returned by discovery. |
| `CLOUD_AUTH_VERSION` | Auth XML version required by that app build; default empty. |

### Local Access And Preferences

| Variable | Meaning and default |
| --- | --- |
| `CAMERA_CONNECTION_MODE` | `lan` by default; set `cloud` explicitly for cloud/P2P operations. |
| `CAMERA_STREAM_PORT` | Native direct LAN TCP port; default `34567`, separate from CGI HTTP/HTTPS. |
| `STREAM_KEY` | Saved 32-byte UTF-8 stream key for LAN TCP; treated as a secret. Never fetched or refreshed automatically. |
| `CAMERA_DEVICE_HOST` | Explicit IP for LAN TCP; LAN host/IP for local CGI queries and door control. No automatic cloud/P2P fallback. |
| `AUTH_CODE` | Authentication code for LAN TCP and local CGI; separate from cloud and door passwords. LAN TCP also accepts its already encoded value. |
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

For a first **local** check, use the
[saved-key playback example](#later-runs-load-and-view-locally) above.

If you separately want to check **cloud metadata**, select
`connection_mode="cloud"` explicitly. This is not a prerequisite for a LAN
session with saved credentials. The default stays LAN-only even when cloud
account settings are present. See [Connection Modes](api.md#connection-modes).

Save this as `app.py` next to your configured `.env` and `assets/`:

```python
from pathlib import Path

from quii_helper import Camera, load_config

application_dir = Path(__file__).resolve().parent
camera = Camera(
    config=load_config(project_root=application_dir),
    connection_mode="cloud",
    data_dir=application_dir / "data",
)
info = camera.get_device_info()
print(info)
```

Run `python app.py`. This logs into the cloud and reads device metadata; it
does not start a preview or open the door. Sparse metadata may be normal for
the firmware. Local `get_product_info()` and similar methods need the separate
LAN host and `AUTH_CODE`; see [Local Methods](api.md#local-device-read-only-methods).

For cloud/P2P media, retain `connection_mode="cloud"`; for local playback,
construct a separate LAN Camera with the saved pair. These are real camera
operations, not offline installation checks. The dedicated `examples.open_door` script sends
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

camera = Camera(
    config=load_config(), connection_mode="cloud", tls_verify=False
)
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
For cloud/P2P, the separately extracted `.so` must still be the verified
**arm64-v8a** asset; supplied-key LAN playback does not read it.
The external PyPI `kcp` package is not needed. FFmpeg is separate.

Earlier ARM64 checks cover installation and mocked entrance-bot integration.
The LAN API was also tested on a physical Pi for capture,
RTSP, cloud bootstrap and saved-key reconnect. See the
[validation matrix](../COMPATIBILITY.md#validation-scope) for scope and limits;
these checks do not certify every PyPI build on ARM64.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `ModuleNotFoundError: quii_helper` | Activate the environment where the package was installed; use that interpreter's `python -m pip`. |
| `No module named examples` | Examples are checkout/source-distribution tools. Run `python -m examples.<name>` from that root, not a wheel-only application. |
| Missing app-specific configuration | Complete the cloud/app values, and pass `config=load_config()` if using `.env`. |
| `connection_mode='cloud'` required | LAN is the default. Select cloud explicitly only for bootstrap, cloud queries or the existing P2P preview. |
| Missing/invalid `STREAM_KEY` | Load a saved key/auth pair explicitly, or bootstrap it deliberately in cloud mode. LAN playback never fetches one for you. |
| Missing `data/stream_credentials.json` | Run the bootstrap example first, or select your application's actual saved path. The LAN example never creates/renews it. |
| `AssetMissingError` | Check `assets_dir`, required files, and the verified vHome ABI/table profile. Do not substitute an arbitrary `.so`. |
| `CERTIFICATE_VERIFY_FAILED` | Follow [TLS guidance](#cloud-region-and-auth-url); do not disable verification silently. |
| Missing `CAMERA_DEVICE_HOST` / `AUTH_CODE` | Supply local settings or the loaded key/auth pair. LAN TCP requires an IP, not a hostname; CGI has separate HTTP settings. |
| LAN crypto/SHA/media profile rejected | Only the verified AES-256/SHA256 profile without separate media encryption is supported; do not guess a different key or fall back silently. |
| Device `error=-1` with empty content | Often an unsupported/rejected firmware command. Inspect the raw response or profile status; do not assume every device implements every query. |
| Missing JPEG/MP4 | Check FFmpeg in the application's environment and inspect the capture error/summary and retained H.264. |
| VLC cannot connect | Wait for media readiness; check the bind host, server LAN IP, firewall, and producer error from `session.wait()`. |
| No console progress in library code | Logging is disabled by default. Enable it explicitly as described in [Logging](api.md#logging). |
| Empty or repeated call history | History is not a live subscription. Read a fresh page and compare record ids; do not infer a new ring from old rows. |

Collect `LOG_LEVEL=debug` diagnostics only when needed. Redact credentials,
tokens, device ids, IPs, and private media before sharing. Do not upload `.env`,
APK resources, or `assets/`; keep originals local rather than deleting them
as a troubleshooting step. See [Security](../SECURITY.md).
