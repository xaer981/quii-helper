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

See `COMPATIBILITY.md` for a compatibility checklist and device report
template.

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
CLOUD_ACCOUNT=""
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

The table below is a quick index. Detailed extraction steps follow in the next
section.

| Variable | Required for cloud/P2P preview | Where to get it |
| --- | --- | --- |
| `CLOUD_ACCOUNT` | yes | Your mobile-app login. |
| `CLOUD_PASSWORD` | yes | Your mobile-app password or its SHA-256 hex digest. |
| `DEVICE_ID` | yes | Device UID/UMID from the device label, QR code, mobile-app device details, or cloud device list. |
| `CLOUD_CLIENT_UUID` | yes | Generate once locally; the app normally derives this from Android ID or stored `uik`. |
| `CLOUD_AUTH_URL` | yes | Discover from the cloud `userapp` service and append `/auth/user`. |
| `CLOUD_SERVICE_URL` | yes | `AppConfig.SERVER_ADDRESS` + `AppConfig.SERVER_PORT` in the decompiled APK. |
| `CAMERA_OEM` | yes | `AppConfig.OEM_ID`, unless the vendor build overrides it through `SpUtil.getServiceId()`. |
| `CAMERA_APP_ID` | yes | `AppConfig.APP_ID`. |
| `CAMERA_CLIENT_TYPE` | yes | Second argument of `QvAlarmCore.getInstance().initParams(...)` in `QvOpenSDK.java`. |
| `IP_REGION_ID` | yes | Cloud discovery `client-regionid`; can change after auth redirect. |
| `CLOUD_AUTH_VERSION` | conditional | `BuildConfig.AUTH_CODE` mapped through `QvCore.setAuthVersionCode(...)`; empty for auth code `0`. |
| `CAMERA_CHANNEL` | no | Use `1` for single-camera devices; use the channel list for multi-channel devices. |
| `CAMERA_STREAM` | no | Native `ids` stream value: `1` high/HD, `2` low/SD default. |
| `AUTH_CODE` | no | Device model/database `authCode`; only for TCP/CGI probe helpers. |
| `DEVICE_PASSWORD` | no | Local CGI/admin password; only for TCP/CGI probe helpers. |
| `TLS_VERIFY` | no | Keep `true` unless the vendor endpoint has certificate issues. |
| `LOG_LEVEL` | no | `info` for normal use, `debug` for protocol diagnostics. |

## Extracting Values

Most values can be found without Frida. For the tested `vHome 2.2` app, the
required values come from static Java constants plus one cloud service-query
request. Frida is not required for the normal setup flow.

Use these source paths relative to the decompiled APK root:

- Java sources: `java_src/`
- APK assets: `assets/`
- Native libraries: `lib/`

### Account And Device Values

- `CLOUD_ACCOUNT`: the same login used in the mobile app. This is usually an
  email address or phone/account string. `CLOUD_USERNAME` is accepted as a
  legacy alias, but new `.env` files should use `CLOUD_ACCOUNT`.
- `CLOUD_PASSWORD`: the same password used in the mobile app. You can enter
  the plain password; quii-helper hashes it with SHA-256 before sending
  user-auth. If you already have the 64-character SHA-256 hex string, that is
  accepted too.
- `DEVICE_ID`: the device UID/UMID, not the camera LAN IP. You can copy it
  from the QR code, device label, mobile-app device details, or cloud device
  list. In code this is `QvDevice.getUmid()` and it is sent as
  `<device-id>` by `UserAuthRequestHelper.getDevDynamicPwd(...)`.

### APK Constants

Open `java_src/com/quvii/qvfun/publico/common/AppConfig.java`:

- `CAMERA_APP_ID`: use `public static final int APP_ID`.
- `CAMERA_OEM`: use `public static final String OEM_ID`.
- `CLOUD_SERVICE_URL`: build
  `https://{SERVER_ADDRESS}:{SERVER_PORT}` from `SERVER_ADDRESS` and
  `SERVER_PORT`. Do not add `/mst/query`; quii-helper appends that path.

For `Tantos Marilyn Wi-Fi s` / `vHome 2.2`, the extracted values are:

```dotenv
CAMERA_APP_ID=4083
CAMERA_OEM="G0083"
CLOUD_SERVICE_URL="https://tantos.qvcloud.net:443"
```

Some vendor/debug builds can override `CAMERA_OEM` and `CLOUD_SERVICE_URL`
through app storage. In `java_src/com/quvii/qvfun/publico/sdk/SdkManager.java`
the app reads:

- `SpUtil.getServiceId()` before building the SDK key
  `serviceId&APP_ID&0`.
- `SpUtil.getAppServiceIp()` before falling back to
  `AppConfig.SERVER_ADDRESS`.

If those stored values are empty, use the `AppConfig` constants. If your vendor
build exposes a hidden test/settings screen that changes them, use the runtime
values from that screen instead.

### Auth Version

Open:

- `java_src/com/quvii/qvfun/publico/common/AppConfig.java`
- `java_src/com/quvii/qvfun/core/BuildConfig.java`
- `java_src/com/quvii/core/QvCore.java`

`AppConfig.AUTH_VERSION_CODE` usually delegates to `BuildConfig.AUTH_CODE`.
`QvCore.setAuthVersionCode(...)` maps it to the XML header version:

| `AUTH_VERSION_CODE` | `CLOUD_AUTH_VERSION` |
| --- | --- |
| `0` | empty string |
| `1` | `v1.10` |
| `2` | `v1.13` |

For the tested `vHome 2.2` APK, `BuildConfig.AUTH_CODE = 2`, so:

```dotenv
CLOUD_AUTH_VERSION="v1.13"
```

### Client Type

Open `java_src/com/quvii/openapi/QvOpenSDK.java` and search for
`QvAlarmCore.getInstance().initParams(...)`.

The second argument is the client type used in user-auth headers. In the
tested app the call is:

```java
QvAlarmCore.getInstance().initParams(
    SDKVariates.CID,
    3,
    DataUtils.getUniqueId(application),
    QvLanguageUtil.initMsgNotifyLang()
);
```

Therefore:

```dotenv
CAMERA_CLIENT_TYPE=3
```

### Client UUID

Open `java_src/com/quvii/publico/utils/DataUtils.java` and search for
`getUniqueId(Context context)`.

The original app uses Android `Settings.Secure.ANDROID_ID`; if it is missing or
all zeroes, it generates a UUID and stores it under the encrypted preference key
`uik`.

For quii-helper, this value only needs to be stable between runs. Generate it
once and keep it in `.env`:

```powershell
python -c "import uuid; print(uuid.uuid4().hex)"
```

Then set:

```dotenv
CLOUD_CLIENT_UUID="generated-value-here"
```

Do not regenerate it on every run.

### Cloud Region And Auth URL

`IP_REGION_ID` and `CLOUD_AUTH_URL` are runtime service-discovery values, not
plain `AppConfig` constants.

The original app flow is:

- `QvLocationManager.init()` starts with the stored
  `SpUtil.getAddressGroupId()` value.
- `QvLocationManager.startQueryTargetService(...)` asks the native P2P layer
  for service addresses.
- `libqv-p2p-v2.so` builds a `query-hlrv2` request and parses
  `client-regionid` plus service entries.
- `QvLocationManager` stores `currentIpRegionId` and updates
  `DownChannelManager.changeService(...)`.
- `UserApi` sends login to `/auth/user;jus_duplex=up`.
- `UserLoginResp` can return `redirect-region-id`; if that happens, the app
  switches region and retries login.

The easiest static-plus-cloud path is the included discovery script. First fill
these `.env` values:

```dotenv
CLOUD_SERVICE_URL="https://..."
CAMERA_OEM="..."
CLOUD_CLIENT_UUID="..."
```

Make sure `assets/ca.pem`, `assets/client.pem`, and `assets/client.txt` are in
place, then run:

```powershell
python -m examples.discover_env_values
```

Copy the printed values:

```dotenv
IP_REGION_ID=<printed client-regionid>
CLOUD_AUTH_URL=<printed userapp auth URL>
```

`CLOUD_AUTH_URL` must be the full POST endpoint, usually:

```dotenv
CLOUD_AUTH_URL="https://<auth-host>:<port>/auth/user"
```

The original Android app declares the upstream auth route as
`/auth/user;jus_duplex=up`, but quii-helper sends `CLOUD_AUTH_URL` exactly as
configured and does not append this suffix automatically. The tested
Tantos/vHome cloud accepts `/auth/user`; if a different vendor endpoint rejects
it, try the native route:

```dotenv
CLOUD_AUTH_URL="https://<auth-host>:<port>/auth/user;jus_duplex=up"
```

If service discovery fails with `CERTIFICATE_VERIFY_FAILED`, the vendor TLS
certificate is not trusted by your local Python installation or does not match
the hostname. For discovery, create the config with TLS verification disabled:

```python
from quii_helper.config import AutonomousConfig

config = AutonomousConfig(ip_region_id=0, tls_verify=False)
```

The included `python -m examples.discover_env_values` helper already uses that
setting for the service-query request. For normal camera usage, the equivalent
`.env` setting is:

```dotenv
TLS_VERIFY=false
```

Use this only for vendor certificate issues; it disables HTTPS certificate
verification.

If the discovery script does not return `userapp`, use the app logs or the
original app's runtime state:

- Search Java for `DownChannelManager.getRequestUrl()`.
- Search logs for `changeService:` or `auth url is null`.
- In a successful login response, check `redirect-region-id` and use it as
  `IP_REGION_ID`.

Frida is only needed as a last resort for unusual vendor builds where the app
hides or rewrites service addresses at runtime. The tested `vHome 2.2` APK does
not require it.

### Optional Values

- `CAMERA_CHANNEL`: camera channel number. Use `1` for a single-panel/single
  camera device. Multi-channel/NVR devices expose channel data in the device
  list/channel list.
- `CAMERA_STREAM`: stream id passed as `ids` in the native live URL.
  `1` requests high/HD quality, `2` is the native low/SD default.
- `AUTH_CODE`: device binding/auth code. It is stored in the app device model
  as `authCode` and database column `authCode`. It is only used by TCP/CGI
  probe helpers, not by normal cloud/P2P preview.
- `DEVICE_PASSWORD`: local CGI/admin password for direct TCP/CGI probe helpers.
  It is not needed for normal cloud/P2P preview.
- `TLS_VERIFY`: keep `true` unless the vendor endpoint has non-public or
  hostname-mismatched certificates.
- `LOG_LEVEL`: use `info` for normal usage and `debug` for protocol
  diagnostics.

For cloud/P2P preview, the camera LAN IP and UDP port are discovered from the
P2P response. A user-provided device IP is not required.

Legacy aliases accepted by the loader:

- `CLOUD_USERNAME` -> `CLOUD_ACCOUNT`
- `CLOUD_OEM` -> `CAMERA_OEM`
- `CLOUD_APP_ID` -> `CAMERA_APP_ID`
- `CLOUD_CLIENT_TYPE` -> `CAMERA_CLIENT_TYPE`
- `VIDEO_PANEL` or `QUII_CHANNEL` -> `CAMERA_CHANNEL`
- `QUII_STREAM` -> `CAMERA_STREAM`
- `CLOUD_TLS_VERIFY` -> `TLS_VERIFY`

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

Runnable examples are available in `examples/`:

- `examples/snapshot.py`
- `examples/save_video.py`
- `examples/serve_rtsp.py`

`snapshot(timeout_seconds=...)` waits up to that many seconds for a decodable
frame. `save_video(duration_seconds=...)` reads the live stream for the
requested duration before writing the MP4.

Set `LOG_LEVEL=debug` to enable protocol diagnostics, packet summaries, and
full capture summaries. The default `LOG_LEVEL=info` prints short progress
messages such as connection, media receiving, and completion status.

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

<p align=center>
  <a href="url"><img src="https://github.com/xaer981/xaer981/blob/main/main_cat.gif" align="center" height="40" width="128"></a>
</p>
