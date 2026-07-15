# Setup And APK Extraction

QUII Helper needs two groups of user-specific inputs:

- Runtime configuration in `.env`.
- Native assets extracted from the Android app in `assets/`.

These values are intentionally not bundled with the project because they can differ by app version, country, cloud region, OEM, and device model.

## Required Assets

Place these files in the repository `assets/` directory:

```text
assets/
  ca.pem
  client.pem
  client.txt
  libqv-p2p-v2.so
```

Expected sources after APK extraction:

- `libqv-p2p-v2.so`: usually under `lib/<abi>/libqv-p2p-v2.so`.
- `ca.pem`, `client.pem`, `client.txt`: usually under `assets/`, `res/raw/`, or app resource folders depending on the APK build.

The package loads these files automatically from `assets/`; no explicit asset path is required.

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
| `CAMERA_DEVICE_HOST` | Camera LAN IP/host. Required for local read-only `/tdkcgi` helpers, not for cloud/P2P preview. |
| `CAMERA_CHANNEL` | Default channel index. |
| `CAMERA_STREAM` | Default stream index. |
| `AUTH_CODE` | Device binding/auth code used by local read-only `/tdkcgi` helpers and TCP/CGI probes. |
| `DEVICE_PASSWORD` | Local CGI/admin password used by direct TCP/CGI probe helpers. |
| `TLS_VERIFY` | Enables/disables TLS certificate verification. Keep `true` unless a vendor endpoint requires otherwise. |
| `LOG_LEVEL` | `info` for normal messages, `debug` for protocol diagnostics. |

Do not commit `.env`.

Generate `CLOUD_CLIENT_UUID` once:

```powershell
python -c "import uuid; print(uuid.uuid4().hex)"
```

Do not regenerate it on every run.

## Discovering Cloud Values

Run the helper:

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

If authentication fails with `CERTIFICATE_VERIFY_FAILED`, pass `tls_verify=False` through the config object:

```python
from quii_helper import AnonymousConfig, Camera

camera = Camera(config=AnonymousConfig(tls_verify=False))
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
