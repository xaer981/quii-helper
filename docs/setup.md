# Setup And APK Extraction

QUII Helper needs two groups of user-specific inputs:

- Runtime configuration supplied from code, process environment, or an explicit `.env` file.
- Native assets extracted from the Android app for operations that need them.

These values are intentionally not bundled with the project because they can differ by app version, country, cloud region, OEM, and device model.

## Using An Installed Package

Use Python 3.10 or newer and a virtual environment. The currently published
release is [0.1.0rc6](https://pypi.org/project/quii-helper/0.1.0rc6/):

```shell
python -m pip install "quii-helper==0.1.0rc6"
```

Version `0.1.0` is prepared in this checkout but is **not published yet**. After
its publication, `python -m pip install quii-helper` installs the final release;
use `python -m pip install --upgrade quii-helper` to replace an installed RC.
No `--pre` is needed for final releases. To test an unpublished build instead,
install its wheel with `python -m pip install /path/to/quii_helper.whl`.

The wheel installs `quii_helper`, not the repository's `examples/`, `docs/`, or
`.env.example`. Create a separate application directory, download the
[environment template](https://github.com/xaer981/quii-helper/blob/main/.env.example)
matching your release, and save a filled-in copy there as `.env`. Put extracted
assets in that directory's `assets/`. Do not modify `site-packages`.

For example, save this in your application's `app.py`:

```python
from pathlib import Path

from quii_helper import Camera, load_config

application_dir = Path(__file__).resolve().parent
camera = Camera(config=load_config(project_root=application_dir))
print(camera.get_device_info())
```

This example performs a read-only cloud query when run; importing the library
alone performs no cloud/device I/O. You can instead construct `AutonomousConfig`
with explicit values, avoiding `.env` entirely. See
[Library Configuration](api.md#library-configuration).

Commands starting with `python -m examples.` require a repository checkout or
the extracted source distribution, run from its root. They are not installed
as modules by the wheel. Extraction helpers are development tools, not an
implicit part of library installation.

## Media Prerequisites

`Camera.snapshot()` and MP4 output from `Camera.save_video()` / `capture()`
invoke the external `ffmpeg` executable. Install a suitable build using the
[official FFmpeg download page](https://ffmpeg.org/download.html), add its
executable directory to `PATH`, and restart the terminal/service if necessary.
On Windows this is the directory containing `ffmpeg.exe`, not the archive itself.
On Linux, your distribution's FFmpeg package is another option.

Verify from the same terminal or service environment that runs your application:

```text
ffmpeg -version
```

Neither pip nor QUII Helper installs this executable. RTSP forwarding, raw
H.264 output, metadata queries, and door control do not require it. If rendering
fails, the capture result/error reports the failure and retained raw H.264 path;
it does not silently treat a missing JPEG/MP4 as success.

## Installing On Linux ARM64

The Python package is platform-independent. Its cryptography dependencies
contain native code, so use compatible Linux ARM64 wheels rather than copying
Windows/x86 packages or compiling them on the target device. For example,
`python -m pip install --only-binary=:all: /path/to/quii_helper.whl` fails
explicitly if the interpreter/platform has no compatible dependency wheels.
The supported check targets Debian-based Python 3.11 on ARM64, not ARMv7.

The external PyPI `kcp` package is not required: the RBUDP implementation lives
inside `quii_helper.protocols`. `cffi`, if needed by `cryptography`, is resolved
transitively rather than imposed as an independent application dependency.

Embedding applications should install a built wheel or an exact published
version, not copy the source tree into their handlers. Local CGI door control
with an explicit password mode requires neither native APK assets nor FFmpeg.
The published `0.1.0rc6` package contains these library changes. Updating
entrance-bot's dependency and deploying it are separate operations; neither
happens when this package is installed elsewhere.

On 2026-10-20, installation and `pip check` passed in both entrance-bot ARM64
images using Python 3.11.17 under QEMU. Each image also passed 11 mocked
integration tests with networking disabled. The library's 754-test suite
passed separately on Windows in an environment without the external `kcp`
package.

The local wheel was subsequently deployed as an entrance-bot dependency on a
physical Raspberry Pi ARM64. On 2026-10-21, its integration suite passed 140
tests in an isolated container on that device with networking disabled and
fake door openers. This verifies that integration on physical ARM64, not live
preview, FFmpeg rendering, or RTSP capture there. No real door command was
sent by the validation tests. Those ARM64 checks used a local build, not the
subsequently published PyPI package.

On 2026-10-21, wheel and sdist installation checks also passed in fresh Windows
Python 3.11 and Linux x86_64 Python 3.10 environments outside the source tree.
These checks exercised import/configuration/path/logging isolation and a mocked
local door adapter; they did not connect to a camera or log into the cloud.
The sdist includes documentation, examples, tests, and the empty `.env.example`.
Neither artifact includes extracted assets or runtime data. Local validation
artifacts from that initial check used `0.1.0rc5`; do not publish them as a
replacement for the already released version.

On 2026-10-22, all 140 entrance-bot tests (commit `40680ee`) passed with
`quii-helper==0.1.0rc6` downloaded from PyPI into a fresh Windows Python 3.11
environment alongside the consumer's pinned dependencies. `pip check` passed;
imports came from `site-packages`, not the library checkout. Test execution
forbade non-loopback network access and private `.env` reads and used fake door
openers. This proves offline consumer compatibility, not live device behavior
or installation of that exact PyPI artifact on ARM64. The consumer repository
still references its local wheel; it was not modified or deployed by this check.

The next prepared version is `0.1.0`, with planned Git tag `v0.1.0`. Preparation
does not publish it; do not reuse any already published version for a new build.
See [Release Checklist](../RELEASE_CHECKLIST.md) for CI and PyPI setup.

## Required Assets

For the standalone examples, place these files in `assets/` under the working
directory (normally the repository root):

```text
assets/
  ca.pem
  client.pem
  client.txt
  libqv-p2p-v2.so
```

Expected sources after APK extraction:

- `libqv-p2p-v2.so`: use `lib/arm64-v8a/libqv-p2p-v2.so` from the verified vHome 2.2 build, not an arbitrary `lib/<abi>` file.
- `ca.pem`, `client.pem`, `client.txt`: usually under `assets/`, `res/raw/`, or app resource folders depending on the APK build.

The `.so` is read as data, never loaded or executed. Its ABI therefore stays
`arm64-v8a` even on Windows or Linux x86_64. The loader validates ELF64,
little-endian AArch64, and SHA-256 fingerprints of all three 4096-byte tables
at the verified offsets. A truncated file, another ABI, or different tables
raises `AssetMissingError` rather than deriving an incorrect key. The fallback
layout `assets/lib/arm64-v8a/libqv-p2p-v2.so` is also accepted.

Other app builds are **not** automatically supported: native inspection must
confirm table layout/content before adding another profile. See
[Native Crypto Asset Validation](protocol-notes.md#native-crypto-asset-validation).
The fingerprints check compatibility, not the provenance or trustworthiness
of a downloaded APK.

Embedding applications can use their own asset directory with
`Camera(assets_dir=...)` or `load_config(assets_dir=...)`. Nothing needs to be
copied into `site-packages`. Local door control with a verified explicit
password mode does not read these assets; preview/cloud discovery may need them.

## `.env`

Create `.env` from `.env.example`:

```powershell
Copy-Item .env.example .env
```

Fill in the required values:

| Variable | Purpose |
| --- | --- |
| `CLOUD_ACCOUNT` | Mobile app account login. `CLOUD_USERNAME` is accepted as a legacy alias. |
| `CLOUD_PASSWORD` | Mobile app account password. |
| `DEVICE_ID` | Camera/device identifier. |
| `CLOUD_CLIENT_UUID` | Stable per-install client id. Generate once and keep it stable. |
| `CLOUD_AUTH_URL` | Cloud auth URL for your region/app. |
| `CLOUD_SERVICE_URL` | Cloud service discovery URL from the APK. |
| `CAMERA_OEM` | OEM/app family value extracted from the APK. |
| `CAMERA_APP_ID` | App identifier extracted from the APK. |
| `CAMERA_CLIENT_TYPE` | Cloud client type extracted from the APK. |
| `IP_REGION_ID` | Region identifier used by the cloud endpoint. |

Optional values:

| Variable | Purpose |
| --- | --- |
| `CLOUD_AUTH_VERSION` | Auth version mapped from the APK auth code. Empty for auth code `0`. |
| `CAMERA_DEVICE_HOST` | Camera LAN IP/host. Required for local `/tdkcgi` methods, including door control, not for cloud/P2P preview. |
| `CAMERA_CHANNEL` | Default channel index. |
| `CAMERA_STREAM` | Default stream index. |
| `AUTH_CODE` | Device binding/auth code used by local `/tdkcgi` methods and TCP/CGI probes. |
| `DEVICE_PASSWORD` | Local CGI/admin password used by direct TCP/CGI probe helpers. |
| `UNLOCK_PASSWORD` | Door-opening password used only by explicit `Camera.open_door()` calls. Separate from CGI/admin and cloud credentials. The body format follows capability 24, or an explicit `password_mode="plain"` / `"sha256"` argument. |
| `TLS_VERIFY` | Enables/disables TLS certificate verification. Keep `true` unless a vendor endpoint requires otherwise. |
| `LOG_LEVEL` | `info` for normal messages, `debug` for protocol diagnostics. |

Do not commit `.env`.

The entry point and examples explicitly load this file. Library code should
use `Camera(config=load_config(project_root=...))` to opt in, or pass a plain
`AutonomousConfig` without file loading. `Camera()` alone uses process
environment values. `load_config()` uses python-dotenv's non-mutating
`dotenv_values()` reader; unlike `load_dotenv()`, it does not populate
`os.environ`. Applications that already call `load_dotenv()` themselves can
continue doing so before constructing `Camera()`.

Generate `CLOUD_CLIENT_UUID` once:

```powershell
python -c "import uuid; print(uuid.uuid4().hex)"
```

Do not regenerate it on every run.

## Discovering Cloud Values

From a repository checkout or extracted source distribution, run the helper:

```powershell
python -m examples.discover_env_values
```

The script prints candidate values for `.env`, including `CLOUD_AUTH_URL`.

If you manually inspect the Android app traffic or Java code, look for:

- Cloud login/auth URL.
- Region ID.
- OEM/app ID.
- Client type.
- Device ID and device password.

## Cloud Region And Auth URL

`CLOUD_AUTH_URL` should be the base auth endpoint used by your app build and region.

Some app traffic or decompiled constants may show auth URLs with a suffix like:

```text
;jus_duplex=up
```

QUII Helper does not require this suffix in `.env`; use the clean auth URL unless your specific app build fails without it. The discovery helper omits the suffix for the recommended `.env` value.

If authentication fails with `CERTIFICATE_VERIFY_FAILED`, load your application
settings explicitly and override verification for the camera:

```python
from quii_helper import Camera, load_config

camera = Camera(config=load_config(), tls_verify=False)
```

Use this only when required by your environment or extracted certificates. Keeping TLS verification enabled is safer.

## Finding APK Constants

The exact locations vary by APK version, but these are common places to inspect after decompilation:

- `java_src`: Java/Kotlin constants, cloud URLs, OEM values, client type, app IDs.
- `lib`: native `.so` files, including P2P/crypto implementation.
- `assets` or `res/raw`: certificates, client keys, PEM files, and app resources.

Recommended tools:

- `apktool` for resources and smali.
- `jadx` for Java/Kotlin sources.
- `Ghidra` for native `.so` inspection when Java code references native behavior.

## Secret Hygiene

Before publishing or sharing logs:

- Remove `.env`.
- Remove `assets/`.
- Remove `data/`.
- Remove generated `.log`, `.jsonl`, `.h264`, `.mp4`, and `.jpg` files.
- Run a secret scanner such as `gitleaks`.
