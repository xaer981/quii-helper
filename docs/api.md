# Camera API Reference

The stable public API is centered around `Camera`.

```python
from quii_helper import Camera, load_config

camera = Camera(config=load_config())
```

`Camera()` reads process environment defaults, not `.env` files. The explicit
`load_config()` call above adds `.env` support without changing `os.environ`.

## Constructor

```python
Camera(config=None, device_host=None, auth_code=None, unlock_password=None)
```

Selected constructor parameters are shown below; the class docstring documents
the complete signature. Keyword arguments override the base configuration.

| Parameter | Purpose |
| --- | --- |
| `config` | Optional `AutonomousConfig`. If omitted, defaults are read from process environment values. |
| `device_host` | Camera LAN IP or hostname for local CGI methods; defaults to `CAMERA_DEVICE_HOST`. |
| `auth_code` | Local CGI authentication code; defaults to `AUTH_CODE`. |
| `unlock_password` | Separate door-opening password; defaults to `UNLOCK_PASSWORD`. |
| `assets_dir` | Application asset directory, default `./assets`. Sets default TLS file paths; individual `ca_path`, `cert_path`, and `key_path` overrides take precedence. |
| `auth_version` | XML cloud-auth version, normally supplied by `CLOUD_AUTH_VERSION` through `load_config()`. |
| `data_dir` | Capture/diagnostic directory, default `./data`. Explicit relative paths are anchored to the working directory when constructing `Camera`. |

## Library Configuration

`AutonomousConfig` is a plain configuration object: constructing it does not
read environment values, `.env`, certificates, or native libraries. Pass it
when the application owns its settings. `Camera` copies the configuration,
so mutable session settings are not shared between camera instances.

Each camera connector also owns its cloud cookie jar. Login, device-token and
device-list requests for that camera share it; another `Camera` does not.
Standalone credential-fetch flows allocate their own jar unless one is passed
explicitly. Alarm login/query retain a separate jar from ordinary userauth.

```python
from pathlib import Path
from quii_helper import AutonomousConfig, Camera

config = AutonomousConfig(
    device_host="192.0.2.10",
    auth_code="your-cgi-auth-code",
    unlock_password="your-door-password",
    assets_dir=Path("/srv/entrance/assets"),
)
camera = Camera(config=config, data_dir="/srv/entrance/captures")
```

Use `load_config(project_root=Path(...), assets_dir=...)` for an application's
`.env` file. Process variables override file values; loading one application's
file never changes another application's environment. Relative `assets_dir`
values are resolved against `project_root`, which defaults to the working
directory. An explicit `env={...}` mapping ignores both `.env` and process
values. `load_env_file=False` reads only the process environment.

TLS files default to `ca.pem`, `client.pem`, and `client.txt` in `assets_dir`.
Relative TLS paths in `AutonomousConfig` are relative to that asset directory.
UST table loading also uses the camera's `assets_dir`; no global asset setting
is needed. Files are read only by operations that need them.

Explicit `output_path` values are honored, including absolute paths outside
`data_dir`. Relative output paths are anchored to the working directory;
omitting the path allocates a timestamped file in `data_dir`. The caller owns
the destination and must validate any paths accepted from untrusted users.
Dots in the requested stem are preserved: `clip.1.mp4` and `clip.2.mp4` are
different captures, and `frame.front.jpg` keeps its full name. Only the final
extension is removed when deriving the shared JPEG/MP4/H.264 base name.

### Async Applications

The API is synchronous. An aiohttp/aiogram application such as `entrance-bot`
can retain a small adapter without embedding XML commands in its handlers:

```python
import asyncio
from quii_helper import Camera, CameraDoorOpenResult

async def open_configured_door(camera: Camera) -> CameraDoorOpenResult:
    return await asyncio.to_thread(camera.open_door, password_mode="sha256")
```

This function sends a real command when called. Choose the explicit password
mode only after verifying the device's requirements. Explicit modes need no
cloud metadata or APK assets for local unlocking. Caller cancellation does not
stop a running thread; never retry an unlock automatically after a timeout.

## Logging

Importing the package does not configure or remove application Loguru sinks.
Library messages are disabled by default. An embedding application may configure
Loguru normally and then call `logger.enable("quii_helper")`.

For an additional library-only console sink, call
`quii_helper.support.log.configure_logging("INFO")`. Repeated calls replace only
the helper's own sink and preserve application sinks. Existing sinks retain
their own filters and levels. `"OFF"` disables library messages without
disabling application messages.

`configure_logging(replace_existing=True)` intentionally replaces all sinks and
is reserved for standalone programs that own process logging. The entry point
and examples use it, reading `LOG_LEVEL` from their explicit settings file.

## Capture Methods

### `snapshot()`

Captures one JPEG image from the live preview.

```python
result = camera.snapshot()
print(result)
```

Returns a `pathlib.Path`. The default output path is generated under `data/`
with a timestamp-based filename.

### `save_video(duration_seconds)`

Captures a video clip and writes an MP4 file.

```python
result = camera.save_video(duration_seconds=60)
print(result)
```

Returns a `pathlib.Path`. `duration_seconds` is the requested media collection
time after the preview session starts receiving packets.

### `capture(...)`

Lower-level capture method used by `snapshot()` and `save_video()`.

Use it when you need both artifacts or need access to the full capture summary.

```python
result = camera.capture(duration_seconds=15)
print(result.summary)
```

## RTSP Streaming

### `serve_rtsp(host="127.0.0.1", port=8554, path="/live")`

Starts a local RTSP server and forwards camera H.264 frames to connected clients.

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

Open in VLC:

```text
rtsp://127.0.0.1:8554/live
```

The context manager closes the preview session and RTSP server automatically.
Stop the example with `Ctrl+C`. Keep `session.wait()` in a standalone stream:
it reports a background producer failure instead of waiting indefinitely for
terminal input after the listener has stopped.
Waiting stays responsive to `Ctrl+C` on Windows as well as Linux, including
when a timeout is supplied. A timeout alone does not close the stream. Leaving
the context manager closes the listener and requests producer cancellation;
an in-flight connection still has its own network timeout.
Each RTSP client has its own bounded send queue (32 pending access units,
4 MiB including in-flight RTP bytes). A full queue, socket failure, or access
unit delayed more than two seconds disconnects that client instead of blocking
the camera producer or other viewers. This is a best-effort live stream, not a
lossless recording service; a disconnected viewer must reconnect.

The decoded RBUDP payload queue is bounded to 4096 packets / 32 MiB. Consumer
overload or an unexpected UDP receiver failure raises `QuiiConnectionError`
instead of silently dropping packets or leaving an apparently live stream with
no producer. `session.wait()` re-raises producer errors and the RTSP listener
is closed. No automatic camera reconnection or command retry is performed.

RBUDP reordering accepts packet starts only inside the native 64 KiB sequence
window, including uint32 wraparound. Outside-window packets are not cached and
receive the cumulative ACK for the current position. Each reordering cache also
has host-side safety limits of 4096 packets / 128 KiB; exceeding them fails the
session explicitly rather than silently discarding required media.

Transport bytes are drained into a separate KCP assembly buffer before ACK
generation. A partial KCP frame does not occupy the transport receive window;
frames larger than 64 KiB therefore do not stall while awaiting their own tail.
Only registered, nonzero local connection IDs are admitted. Each lane owns one
receive state, even when the peer word changes; unknown IDs allocate no state,
receive no ACK, and deliver no data. These checks are routing, not cryptographic
authentication of a sender.

Complete KCP frames are dispatched one at a time. A malformed next header or
length raises a terminal `QuiiConnectionError`, rather than dropping the valid
prefix silently and carrying on. The prefix reaches the decoder first, but a
terminal receiver failure clears pending application payloads and aborts the
operation: it does not promise a usable partial recording. Incomplete valid
headers/bodies remain buffered. KCP packets are limited to 20 MiB.

Upper QUII assembly also bounds pending data across chained and fragmented
media buffers: 32 logical stream keys / 32 MiB including the next input chunk.
Declared media bodies must be positive and at most 20 MiB. Invalid lengths,
decode errors or a buffer limit abort the operation with `QuiiConnectionError`
and release pending data, rather than silently losing required bytes.
A camera disconnect request for a connected/connecting preview lane likewise
aborts capture; unrelated IDs and response flags are ignored. For RTSP,
`session.wait()` reports the failure and the listener closes. These safety
limits are library policy, not vendor constants or total process-memory limits.

Diagnostic deduplication stores at most 128 SHA-256 fingerprints, never a history of full
frames; disabled RBUDP diagnostics do not calculate those fingerprints or HEX.

The `RTSP stream ready` log appears only after the first assembled H.264 access
unit. `session.url` is an address, not a readiness check.

The default listener accepts local clients only. For a trusted LAN, explicitly
pass `host="0.0.0.0"` and connect using the server's LAN IP. **There is no RTSP
authentication or TLS:** restrict access with a firewall/VPN and do not expose
this port to the Internet. The server allows at most 32 concurrent clients;
headers are limited to 16 KiB, request bodies to 64 KiB, and incomplete messages
expire after 10 seconds.

`close()` requests cancellation and waits briefly for the producer. An in-flight
cloud/connection call can remain until its own timeout, but later startup stages
are skipped. A restart is rejected while that producer is still stopping.
`wait()` reports producer failures; the listener closes on failure rather than
remaining available without media. Streaming retains only recent frame metadata,
not the complete packet history.

## Door Control

### `open_door(...)`

Sends one local XML `set.device.opendoor` command through `/tdkcgi`. It does not
open a preview, retry the command, or follow redirects. The default `auto` mode
may query read-only cloud metadata to determine the password format; explicit
modes work without cloud login.

Configure `CAMERA_DEVICE_HOST`, `AUTH_CODE`, and `UNLOCK_PASSWORD` in `.env`.
`UNLOCK_PASSWORD` is the door-opening password, separate from CGI authentication
and the cloud account password. The XML body format is selected using capability
24 (`TYPE_ENCRYPY_SHA256`), matching `QvDeviceApi.deviceUnlock` in vHome: a set
flag applies `EncodeDevicePassword`, while a clear flag sends the exact password.
CGI header authentication continues to use encoded `AUTH_CODE` in both modes.

The following example **sends a real opening command** when executed:

```python
from quii_helper import Camera, load_config

camera = Camera(config=load_config())
result = camera.open_door(lock_number=1)
print(result.accepted, result.error, result.message)
```

To print capability 24 and the command result using `.env` settings, explicitly
run the dedicated example below. It **opens the configured door**; the normal
`python -m quii_helper.main` entry point only starts RTSP.

```powershell
python -m examples.open_door
```

| Parameter | Purpose |
| --- | --- |
| `channel=None` | Video-panel channel, sent as `door`. Defaults to `Camera.channel` / `CAMERA_CHANNEL`. |
| `lock_number=1` | Positive lock/relay number, sent as `locknumber`. |
| `unlock_password=None` | Per-call override of `Camera(unlock_password=...)` / `UNLOCK_PASSWORD`. Accepts plain text or the vendor-encoded password. |
| `password_mode="auto"` | Uses capability 24 from cached metadata or a read-only `get_device_info()` lookup. `"plain"` sends the body password unchanged; `"sha256"` applies the vendor encoding rule. Explicit modes override capability and skip cloud lookup. |
| `port=80`, `scheme="http"` | Local CGI endpoint. HTTPS is available where the device supports it. |
| `auth_code=None` | Per-call CGI authentication override. Defaults to `Camera(auth_code=...)` / `AUTH_CODE`. |
| `verify_tls=None` | HTTPS certificate verification override. Defaults to the camera configuration. |
| `debug=False` | Enables redacted CGI exchange logging at DEBUG level. |

Returns `CameraDoorOpenResult` with `error`, `channel`, `lock_number`, `accepted`,
and `message`. `accepted=True` requires an explicit numeric `<error>0</error>`
response. It confirms the device acknowledgement, not physical door movement.
Unlock errors have command-specific meanings, including incorrect opening
password, busy device, disabled channel, and disabled lock.

Missing settings or invalid parameters raise `ConfigurationError` before sending.
Transport failures and malformed responses raise `QuiiConnectionError`: the
device may already have acted, so the physical outcome is unknown. The package
does not automatically repeat the command or try the other password format.

If cloud metadata is unavailable or capability 24 cannot be decoded, `auto`
raises `ConfigurationError` before sending an opening command. Once the expected
format is known, select it explicitly:

```python
# Sends a real command with the body password unchanged; no cloud lookup.
result = camera.open_door(password_mode="plain")
# Alternatively, password_mode="sha256" selects the vendor-encoded format.
```

`camera.get_device_info().supports_sha256_password` exposes the decoded flag as
`True`, `False`, or `None`. Missing, malformed, or truncated basedata is unknown,
not an indication that plain passwords are supported.

## Cloud Read-Only Methods

These methods use cloud/app APIs and do not require direct LAN access to the camera:

| Method | Purpose |
| --- | --- |
| `get_device_info()` | Returns basic device metadata available from cloud runtime credentials. |
| `get_device_shadow_info()` | Returns cloud shadow/device state where supported. |
| `get_iot_command_support()` | Returns cloud-supported command metadata where supported. |
| `get_call_events(...)` | Experimental read-only incoming-call history from the cloud `UserAlarm` journal. |

Example:

```python
info = camera.get_device_info()
print(info.device_id)
print(info.transparent_basedata)
```

### Incoming Call History (Experimental)

```python
page = camera.get_call_events(page_size=15)
for event in page.events:
    print(event.record_id, event.alarm_id, event.time, event.channel)

# Next page of the same query; keep the filters and page size unchanged.
next_page = camera.get_call_events(page=1, max_id=page.max_id, page_size=15)
```

The method discovers `alarmapp`, performs cloud login and a separate alarm
`client-login`, then makes one `client-query-recordlist` request to `UserAlarm`.
It does not require the camera LAN IP or start a media session. Existing
cloud/app settings and the TLS assets from [Setup](setup.md) are used.
The alarm login uses a dedicated, stable, account-scoped reader id and a
separate cookie jar; no Android push token or HS/LT credentials are supplied.
It may create a reader-client record/session on the server, but never logs out
existing clients or changes notification settings.

| Parameter | Purpose |
| --- | --- |
| `page=0` | Zero-based page number, matching the original client. |
| `page_size=15` | Positive number of records requested per page. |
| `max_id="0"` | Native pagination anchor; pass the returned value on later pages. Not a since-id cursor. |
| `start_time=""`, `end_time=""` | Optional time bounds as `YYYY-MM-DD HH:MM:SS` in the vendor's time convention. No timezone is assumed or converted. |

Returns `CameraCallEventPage` with `events`, `max_id`, `total_count`, and
`unread_count`. Each `CameraCallEvent` preserves journal `record_id`, original
`alarm_id`, device/channel, timestamp text, alarm/message states, and optional
source/resource fields. Only native event `19` for this device is returned;
event `20` means call received/handled, not another incoming call. Resource URLs
are not downloaded and are omitted from object `repr` because they may contain
private access tokens. Avoid publishing event metadata or URLs.

Reading never marks records read, deletes them, registers push, changes alarm
settings, answers a call, or opens a door. Invalid parameters raise
`ConfigurationError`; transport, malformed responses, and server rejection raise
`QuiiConnectionError`, never a successful empty page.

If discovery reports `did not return a usable alarmapp service`, include the
complete error text in a bug report. It contains the discovery `result` and
returned service names, per-service `query_result`, and URL-presence flags,
but omits private URLs. This failure happens before cloud login and does not
indicate whether the account can read call history.

If a response is not valid XML, the error reports HTTP status, content type,
content encoding, and byte count instead of the private body. Gzip responses
are decoded automatically; unsupported encodings are reported explicitly.
The journal URL uses the discovered address plus `UserAlarm`, not its separate
P2P `uri` field.

**This is history access, not a live ringing subscription.** Cloud and alarm
login are performed on each query. Error `1012` is the native
`ALARM_RESULT_SESSION_ERROR`: the alarm-service session is missing or invalid.
A rejected login stops the request; the helper does not retry with a push token,
modify notifications, or fall back to controlling an existing Android client.
Tokenless login and history reads were user-confirmed for the tested
installation on 2026-10-19. A subsequent entrance-bot polling check observed a
new call. The manual marker was entered after the record was already visible,
so it does not provide a reliable delivery-latency measurement. These results
do not prove delivery with Android fully disconnected, guarantee availability
on other backends, or turn history into a live subscription. Do not use history
alone as an automatic door-opening trigger.

Run the standalone read-only check with:

```powershell
python -m examples.call_events
```

To check whether new calls are logged without Android, close the app, read a
baseline page, ring the doorbell, then query a fresh page (`page=0`, `max_id="0"`).
Compare `record_id` values and timestamps; old history is not evidence of a new
ring. Repeating a query may return the same records. No deduplication, background
poller, face recognition, or door automation is included.

## LAN Discovery

| Method | Purpose |
| --- | --- |
| `discover_lan_devices()` | Searches the local network for compatible Qualvision-style devices. |

Discovery hints:

- Compatible devices may return `Server: Qualvision -HTTPServer`.
- TCP port `34567` is commonly open on compatible cameras.

## Local Device Read-Only Methods

These methods query the device directly over LAN. They require a reachable device IP, usually resolved from cloud/P2P data.

### Device And Product

| Method | Purpose |
| --- | --- |
| `get_device_profile()` | Aggregates commonly useful local device information. |
| `get_device_all_info()` | Requests the broad all-info command where supported. |
| `get_product_info()` | Reads firmware/product version fields. |
| `get_time_info()` | Reads device timezone/time fields. |
| `get_system_general_info()` | Reads general system settings where supported. |
| `get_system_capabilities()` | Reads capability flags where supported. |
| `get_qr_code_info()` | Reads QR/device binding data where supported. |
| `get_stream_key_info()` | Reads stream key data where supported. |

### Network And Storage

| Method | Purpose |
| --- | --- |
| `get_storage_info()` | Reads storage state. |
| `get_tf_card_info()` | Reads TF/SD card state. |
| `get_network_info()` | Reads network summary. |
| `get_network_base_info()` | Reads base network configuration. |
| `get_network_interfaces()` | Reads available network interfaces. |
| `get_wifi_list()` | Reads visible Wi-Fi networks where supported. |

### Video And Encoding

| Method | Purpose |
| --- | --- |
| `get_video_config()` | Reads encode/video configuration. |
| `get_video_channels()` | Reads channel information. |
| `get_stream_profiles()` | Reads stream profile settings. |
| `get_fps_info()` | Reads FPS configuration. |
| `get_json_fps_mode_info()` | Reads JSON FPS mode information where supported. |
| `get_screen_flip_info()` | Reads mirror/rotation state where supported. |
| `get_video_switch_info()` | Reads video on/off state where supported. |
| `get_time_title_info()` | Reads time/title overlay settings where supported. |

### Alarm And Detection

| Method | Purpose |
| --- | --- |
| `get_alarm_channel_info()` | Reads alarm channel information. |
| `get_alarm_input_info()` | Reads alarm input information. |
| `get_alarm_detail_info()` | Reads alarm detail information. |
| `get_alarm_status_info()` | Reads current alarm status. |
| `get_alarm_motion_detection_info()` | Reads alarm motion-detection settings. |
| `get_alarm_video_lost_info()` | Reads video-lost alarm settings. |
| `get_alarm_video_shelter_info()` | Reads video-shelter alarm settings. |
| `get_motion_detection_info()` | Reads motion detection configuration. |
| `get_human_trace_info()` | Reads human-trace settings where supported. |
| `get_move_detection_info()` | Reads move-detection settings where supported. |

Schedule variants:

| Method | Purpose |
| --- | --- |
| `get_motion_detection_schedule()` | Reads motion detection schedule. |
| `get_video_lost_schedule()` | Reads video lost schedule. |
| `get_video_shelter_schedule()` | Reads video shelter schedule. |
| `get_alarm_in_schedule()` | Reads alarm input schedule. |
| `get_human_trace_schedule()` | Reads human trace schedule. |

### Accessories And Device Features

| Method | Purpose |
| --- | --- |
| `get_device_attachment_info()` | Reads accessory/attachment data. |
| `get_ptz_state()` | Reads PTZ state where supported. |
| `get_ptz_presets()` | Reads PTZ presets where supported. |
| `get_smart_light_info()` | Reads smart light settings. |
| `get_sound_light_info()` | Reads sound/light settings. |
| `get_audio_volume_info()` | Reads audio volume settings. |
| `get_audio_session_info()` | Reads audio session settings. |
| `get_hardware_info()` | Reads hardware information. |
| `get_light_info()` | Reads light settings. |
| `get_babysitter_state_info()` | Reads babysitter state where supported. |
| `get_pir_config_info()` | Reads PIR configuration where supported. |
| `get_third_party_push_info()` | Reads third-party push settings where supported. |
| `get_smart_switch_info()` | Reads smart switch settings where supported. |
| `get_lock_status_info()` | Reads lock status where supported. |
| `get_floodlight_switch_info()` | Reads floodlight switch state where supported. |
| `get_floodlight_schedule_info()` | Reads floodlight schedule where supported. |
| `get_city_coordinate_info()` | Reads city/coordinate settings where supported. |
| `get_voice_message_info()` | Reads voice-message settings where supported. |

### Upgrade And Recording

| Method | Purpose |
| --- | --- |
| `get_upgrade_version_info()` | Reads available upgrade version info where supported. |
| `get_upgrade_status_info()` | Reads upgrade status where supported. |
| `get_upgrade_process_info()` | Reads upgrade process information where supported. |
| `get_record_files()` | Reads recording file list where supported. |
| `get_record_days()` | Reads days with recordings where supported. |
| `get_record_months()` | Reads months with recordings where supported. |

## Error Codes

Local device calls may return numeric device errors such as `-1` or `-8`.

The package maps known codes to human-readable descriptions where available. Unknown codes are preserved in the raw response so unsupported commands can still be diagnosed.

## Application Entry Point

The default entry point starts RTSP on port `8554` until interrupted with
`Ctrl+C`. It does not send door-opening commands.

```powershell
python -m quii_helper.main
```
