# Camera API Reference

[Documentation](README.md) | [Setup](setup.md) | [Compatibility](../COMPATIBILITY.md)

`Camera` is the public entry point. The API is synchronous; importing the
package or constructing a camera does not connect to a device.

## Contents

- [Constructor](#constructor) and [configuration](#library-configuration).
- [Capture](#capture-methods), [RTSP](#rtsp-streaming), and [logging](#logging).
- [Cloud queries](#cloud-read-only-methods) and [call history](#incoming-call-history-experimental).
- [LAN discovery](#lan-discovery) and [local inspection](#local-device-read-only-methods).
- [Archive queries](#archive-queries), [door control](#door-control), and [errors](#error-codes).
- [Bundled examples](#application-entry-point).

## Constructor

```python
from quii_helper import Camera, load_config

camera = Camera(config=load_config())
```

`config` is an optional `AutonomousConfig`. If omitted, `Camera()` reads
process environment defaults, **not `.env` files**. Every other constructor
argument is keyword-only. A non-`None` keyword overrides the base configuration
for this camera; the supplied configuration is copied.

### Account And Device

| Parameter | Meaning |
| --- | --- |
| `device_id` | Device identifier; `DEVICE_ID` in environment-backed configuration. |
| `cloud_account`, `cloud_username` | Cloud login; `cloud_username` is an alias. |
| `cloud_password` | Cloud account password. |
| `device_host` | Explicit LAN host/IP for local CGI methods. Not discovered implicitly. |
| `auth_code` | Local CGI authentication code, separate from the opening password. |
| `unlock_password` | Door-opening password used only by explicit `open_door()` calls. |
| `channel` | Video-panel channel; base default `1`. |
| `stream` | Numeric stream id; base default `2`. |
| `stream_quality` | Friendly selector such as `"high"` (`1`) or `"low"` (`2`). Mutually exclusive with an explicit `stream`. |

### Cloud And Assets

| Parameter | Meaning |
| --- | --- |
| `client_id` | Stable per-install cloud/UST/MQTT client UUID. |
| `service_url` | Service-discovery base URL. |
| `auth_url` | Region/app user-auth endpoint. |
| `oem`, `app_id`, `client_type`, `ip_region_id` | App/OEM and region values, not universal defaults. |
| `auth_version` | Cloud XML auth version from the app build; base default empty. |
| `assets_dir` | Asset directory; base default `./assets`. Sets default TLS file paths. |
| `ca_path`, `cert_path`, `key_path` | Individual TLS file overrides, taking precedence over asset-directory defaults. |
| `tls_verify` | HTTPS certificate verification; base default `True`. |

### Capture And Advanced Options

| Parameter | Meaning |
| --- | --- |
| `data_dir` | Output/diagnostic directory; default `./data`. |
| `preview_settings` | `PreviewCaptureSettings`; keep defaults unless tuning capture/diagnostics. |
| `emit` | Callback receiving structured diagnostic summaries. |
| `status` | Callback receiving user-facing status strings. |
| `live_play_payload` | Native live-play variant; base default `"path"`. |
| `live_inner`, `live_newcn` | Native packet/connection flags; base defaults `False`. |
| `live_keepalive_interval` | Live keepalive interval; base default `10.0` seconds. |
| `play_sync_iterations` | Extra post-play sync iterations; base default `0`. |
| `enable_play_probes` | Extra play probes; base default `False`. |

Advanced protocol options are compatibility controls, not general performance
presets. Change them only with device/native evidence. The defaults above are
plain configuration defaults; environment settings or a supplied config can
replace them.

## Library Configuration

Choose one configuration source:

| Construction | What it reads |
| --- | --- |
| `Camera(config=load_config())` | `.env` in the working directory, with process environment values taking precedence. |
| `Camera(config=load_config(project_root=...))` | That directory's `.env`; relative `assets_dir` is resolved against it. |
| `Camera()` | Process environment values only. |
| `Camera(config=AutonomousConfig(...))` | Explicit fields; neither `.env` nor process environment values. |
| `load_config(env={...})` | Only the supplied mapping; no `.env` or process values. |
| `load_config(load_env_file=False)` | Process environment only. |

`load_config()` uses python-dotenv's non-mutating `dotenv_values()` reader.
It does not populate `os.environ` or share another application's loaded file.
`**overrides` use `AutonomousConfig` field names, for example `tls_verify=False`.

For application-owned local settings, no cloud credentials are needed:

```python
from quii_helper import AutonomousConfig, Camera

camera = Camera(
    config=AutonomousConfig(
        device_host="192.0.2.10",
        auth_code="replace-with-your-cgi-code",
    )
)
```

The example configures a client only; it does not query or open anything.
See [Setup](setup.md#what-your-operation-needs) for per-operation requirements.

### Paths And Output

Assets default to `./assets`; TLS files default to `ca.pem`, `client.pem`, and
`client.txt` inside it. Relative TLS paths in `AutonomousConfig` are resolved
against `assets_dir`. Asset files are read only by operations needing them.

Default media goes into `./data`, relative to the working directory at camera
construction. `load_config(project_root=...)` does not relocate default output:
pass `data_dir=application_dir / "data"` for that. Explicit `output_path`
destinations are honored, including paths outside `data_dir`; relative output
paths are relative to the working directory. Validate paths from untrusted users.

Automatic filenames use `DD-MM-YYYY_HH-MM-SS` and reserve a unique output base.
Dotted names such as `clip.1.mp4` retain their full stem. JPEG/MP4 normally
does not retain diagnostic JSONL files; failed rendering can retain raw H.264.

## Capture Methods

| Method | Returns | Purpose |
| --- | --- | --- |
| `snapshot(timeout_seconds=5.0, output_path=None)` | `Path` | Save one JPEG; stop when enough decodable media is available. |
| `save_video(duration_seconds, output_path=None)` | `Path` | Collect video for the requested window and render MP4. |
| `record(duration_seconds, output_path=None)` | `Path` | Alias for `save_video()`. |
| `capture(...)` | `CameraCaptureResult` | Select artifacts and inspect the structured summary. |

`duration_seconds` can be positional in `save_video()` / `record()`. All other
capture arguments are keyword-only. Durations must be positive and finite.
Use a `.jpg` output path for `snapshot()` and `.mp4` for `save_video()`.

```python
image_path = camera.snapshot(timeout_seconds=10, output_path="data/front.jpg")
video_path = camera.save_video(15, output_path="data/entrance.mp4")
```

### Timing

The collection window starts after credentials, connection, and live-preview
setup, when the packet-consumption loop begins. It does **not** wait for the
first successfully decoded frame. Connection startup, pending-fragment draining,
and FFmpeg rendering can make the call take longer than the requested window.

`snapshot(timeout_seconds=...)` limits that collection window, not the complete
call including connection and rendering. `save_video()` disables early stopping;
the requested duration is a collection target, not a guarantee of frame count,
delivery quality, or an exact wall-clock return time.

### Capture Settings And Results

| `capture()` argument | Default and purpose |
| --- | --- |
| `duration_seconds=None` | Use `preview_settings.capture_seconds` (`35.0` by default). |
| `output_path=None` | Allocate a timestamped output base in `data_dir`; a requested final extension is removed to derive companion artifact names. |
| `stop_when_decodable=None` | Inherit the preview setting, which defaults to **`True`**. |
| `render_snapshot=True` | Request JPEG rendering. |
| `render_video=True` | Request MP4 rendering. |
| `save_diagnostic_artifacts=None` | Inherit diagnostic saving, disabled by default. |

To request both files across a full collection window, disable early stopping:

```python
result = camera.capture(duration_seconds=15, stop_when_decodable=False)
print(result.snapshot_path, result.snapshot_written)
print(result.video_path, result.video_written)
print(result.summary)
```

`CameraCaptureResult` also exposes `media_written`, `require_snapshot()`, and
`require_video()`. The latter methods return a `Path` or raise
`CameraCaptureError` / `MediaRenderError`. `capture()` reports render failure
in its result; it can still raise configuration, connection, or decoder errors.
`snapshot()` and `save_video()` require their requested artifact to succeed.

## RTSP Streaming

| Method | Returns | Purpose |
| --- | --- | --- |
| `serve_rtsp(host="127.0.0.1", port=8554, path="/live")` | `CameraRtspStream` | Start a listener and background camera producer. |

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

Open `rtsp://127.0.0.1:8554/live` in VLC after media arrives. The helper forwards
the QUII H.264 preview; it does not enable native RTSP on the camera or require
FFmpeg. Each call opens its own preview session.

| Stream handle | Meaning |
| --- | --- |
| `session.url` | Address, **not** a readiness check. |
| `session.stats` | Current RTSP/H.264 counters. |
| `session.wait(timeout=None)` | Wait for completion; re-raise producer failure; remain responsive to `Ctrl+C`. A timeout alone does not close the stream. |
| `session.close()` | Request cancellation and release the listener; also called by the context manager. |

The `RTSP stream ready` log appears after the first assembled H.264 access
unit, if library logging is enabled. A producer failure closes the listener;
there is no automatic camera reconnect. An in-flight cloud/connection call can
finish only at its own timeout during shutdown; subsequent startup stages are
cancelled and overlapping restarts are rejected while the producer is stopping.

Slow viewers are disconnected rather than blocking the producer. This is a
best-effort stream, not lossless recording. See
[Runtime Limits](protocol-notes.md#runtime-limits-and-lifecycle) for queue,
packet-size, and request limits.

The default bind is loopback only. For a trusted LAN, pass `host="0.0.0.0"`
and connect using the server's LAN IP, not the wildcard address.
**There is no RTSP authentication or TLS.** Use a firewall/VPN and never expose
the port directly to the Internet.

## Logging

Library logging is disabled by default. Imports do not remove or reconfigure
the host application's Loguru sinks. If your application already owns logging:

```python
from loguru import logger
from quii_helper import Camera, load_config

logger.enable("quii_helper")
camera = Camera(config=load_config())
```

For an optional library-only console sink, use
`quii_helper.support.log.configure_logging("INFO")`. Repeated calls replace
only this helper's sink and preserve application sinks. `"OFF"` disables library
messages without disabling application messages.

Standalone scripts can call `configure_logging(replace_existing=True)` to
own all sinks and read `LOG_LEVEL` from `.env`. This deliberately replaces
existing sinks; do not use it casually in an embedding application. INFO is
user-facing progress; DEBUG adds protocol counters and diagnostics. Redact
logs before sharing them.

## Cloud Read-Only Methods

These methods use cloud/app services, not the camera's LAN CGI endpoint.
They do not open a preview or send opening commands.

| Method | Returns | Purpose |
| --- | --- | --- |
| `get_device_info()` | `CameraDeviceInfo` | Login, device-token metadata, and best-effort device-list enrichment. |
| `get_device_shadow_info()` | `CameraDeviceShadowInfo` | Cloud shadow/device state where supported. |
| `get_iot_command_support()` | `CameraIotCommandSupportInfo` | Command-support metadata, not command execution. |
| `get_call_events(...)` | `CameraCallEventPage` | Experimental incoming-call journal history. |

Sparse fields in `CameraDeviceInfo` do not necessarily mean parsing failed.
`supports_sha256_password` is `True`, `False`, or `None` when capability data
is missing/invalid. Do not log raw credentials or basedata publicly.

### Incoming Call History (Experimental)

```python
page = camera.get_call_events(page_size=15)
for event in page.events:
    print(event.record_id, event.alarm_id, event.time, event.channel)

next_page = camera.get_call_events(page=1, max_id=page.max_id, page_size=15)
```

| Argument | Default and meaning |
| --- | --- |
| `page` | `0`; zero-based page number. |
| `page_size` | `15`; positive requested page size. |
| `max_id` | `"0"`; native pagination anchor, **not** a since-id cursor. Keep the returned anchor, filters, and page size when reading later pages. |
| `start_time`, `end_time` | Empty; optional `YYYY-MM-DD HH:MM:SS` bounds in the vendor's time convention. No timezone conversion. |

The page exposes `events`, `max_id`, `total_count`, and `unread_count`. Each
event preserves `record_id`, `alarm_id`, device/channel, timestamp text,
alarm/message states, and optional source/resource fields. Only incoming-call
event `19` for this device is returned; event `20` means received/handled.
Resource URLs are not downloaded and are hidden from `repr` because they can
contain private tokens. Do not publish event metadata or URLs.

Each query discovers `alarmapp`, performs ordinary cloud login and a separate
tokenless alarm `client-login`, then reads `UserAlarm`. The stable reader identity
is account-scoped and uses a separate cookie jar. Login may create a reader
record/session, but never registers push, logs out existing clients, marks
records read, deletes them, or changes notification settings.

**This is history access, not a live ringing subscription.** Repeated queries
can return the same rows; no background polling, deduplication, delivery-time
guarantee, face recognition, or door automation is included. For a fresh check,
compare a baseline with `page=0, max_id="0"` after a ring. Do not use history
alone as an automatic door-opening trigger.

Discovery/authentication/response failures raise `QuiiConnectionError`, not
a successful empty page. Error `1012` is the native alarm-session error.
The package does not fall back to an Android push token or control an existing
Android client. See [Protocol Notes](protocol-notes.md#cloud-incoming-call-history)
for request parity and [Compatibility](../COMPATIBILITY.md#validation-scope)
for the observed validation scope.

## LAN Discovery

| Method | Returns | Purpose |
| --- | --- | --- |
| `discover_lan_devices(...)` | `list[LanDeviceCandidate]` | Read HTTP headers and probe native TCP port availability. |

Keyword arguments: `hosts=None`, `local_ips=None`, `subnet_prefix=24`,
`http_port=80`, `stream_port=34567`, `timeout=0.3`, `max_workers=64`, and
`require_qualvision=True`. Explicit `hosts` bypass subnet derivation; otherwise
local addresses determine scan ranges. `timeout` is per probe, not the whole
scan. Only scan networks you administer.

Candidates expose discovery hints such as `Server: Qualvision -HTTPServer`
and open TCP port `34567`. A candidate is not proof of protocol compatibility.
Choose the intended device and set `Camera(device_host=...)` explicitly;
discovery does not silently change the camera's configuration.

## Local Device Read-Only Methods

All methods below query LAN HTTP/CGI directly. Set **`CAMERA_DEVICE_HOST` and
`AUTH_CODE`**, or pass their constructor equivalents. There is no implicit
cloud login or cloud/P2P host discovery. Default `port=80` is the HTTP port,
**not** native TCP port `34567`.

Common keyword-only arguments on these methods are `port=80`, `scheme="http"`,
`auth_code=None`, `verify_tls=None`, and `debug=False`. A per-call auth code
overrides camera configuration; `verify_tls=None` follows the camera setting
for HTTPS. DEBUG exchange logging remains subject to the logging level.
Additional arguments are shown in the tables; arguments with defaults are optional.

Most responses expose `error` and `raw` (parsed response/raw XML or JSON).
`error=0` is success; `-1` with empty content often indicates unsupported/rejected
firmware functionality. Derived tuples do not carry a separate error code.
`get_device_profile()` aggregates multiple queries and command statuses; it
is not a single lightweight request.

[Device/Product](#device-and-product) | [Network/Storage](#network-and-storage) |
[Video](#video-and-encoding) | [Alarms](#alarm-and-detection) |
[Accessories](#accessories-and-device-features) | [Upgrade](#upgrade-information) |
[Archive](#archive-queries)

### Device And Product

| Method | Returns | Purpose |
| --- | --- | --- |
| `get_device_profile()` | `CameraDeviceProfile` | Aggregate common queries and supported/unsupported/failed command lists. |
| `get_device_all_info()` | `CameraDeviceAllInfo` | Broad status fields. |
| `get_product_info()` | `CameraDeviceProductInfo` | Firmware/product metadata. |
| `get_time_info()` | `CameraDeviceTimeInfo` | Timezone/time fields. |
| `get_system_general_info()` | `CameraDeviceGeneralInfo` | General system settings. |
| `get_system_capabilities()` | `CameraDeviceCapabilitiesInfo` | Reported capabilities. |
| `get_qr_code_info()` | `CameraDeviceQrCodeInfo` | QR/binding data; potentially sensitive. |
| `get_stream_key_info()` | `CameraDeviceStreamKeyInfo` | Stream key data; potentially sensitive. |

### Network And Storage

| Method | Returns | Purpose |
| --- | --- | --- |
| `get_storage_info()` | `CameraDeviceStorageInfo` | Disk capacity/state. |
| `get_tf_card_info()` | `CameraDeviceTfCardInfo` | TF/SD-card state. |
| `get_network_info()` | `CameraDeviceNetworkInfo` | Network configuration. |
| `get_network_base_info()` | `CameraDeviceNetworkBaseInfo` | Base network settings/abilities. |
| `get_network_interfaces()` | `tuple[CameraDeviceLanInfo, ...]` | Flattened interfaces from network information. |
| `get_wifi_list()` | `CameraDeviceWifiListInfo` | Visible Wi-Fi networks. |

### Video And Encoding

| Method | Returns | Purpose |
| --- | --- | --- |
| `get_video_config()` | `CameraDeviceVideoConfigInfo` | Encode/video configuration. |
| `get_video_channels()` | `tuple[CameraDeviceVideoChannelInfo, ...]` | Channels from video configuration. |
| `get_stream_profiles(channel_id=None)` | `tuple[CameraDeviceStreamProfile, ...]` | Flattened profiles, optionally filtered by channel id. |
| `get_fps_info(channel_id=-1, stream_id=-1)` | `CameraDeviceFpsInfo` | FPS settings; `-1` requests all channels/streams. |
| `get_json_fps_mode_info()` | `CameraDeviceJsonFpsModeInfo` | JSON FPS-mode information. |
| `get_screen_flip_info()` | `CameraDeviceScreenFlipInfo` | Mirror/rotation state. |
| `get_video_switch_info()` | `CameraDeviceVideoSwitchInfo` | Video on/off state. |
| `get_time_title_info()` | `CameraDeviceTimeTitleInfo` | Time/title overlays. |

### Alarm And Detection

| Method | Returns | Purpose |
| --- | --- | --- |
| `get_alarm_channel_info()` | `CameraDeviceAlarmChannelInfo` | Alarm channels. |
| `get_alarm_input_info(channel_id=-1)` | `CameraDeviceAlarmInputInfo` | Inputs; `-1` requests all channels. |
| `get_alarm_detail_info(alarm_type=...)` | `CameraDeviceAlarmDetailInfo` | Detail settings; requires the native integer alarm type. |
| `get_alarm_status_info()` | `CameraDeviceAlarmStatusInfo` | Current alarm state. |
| `get_alarm_motion_detection_info(channel_id=1)` | `CameraDeviceAlarmMotionDetectionInfo` | Motion alarm settings. |
| `get_alarm_video_lost_info(channel_id=1)` | `CameraDeviceAlarmVideoLostInfo` | Video-lost alarm settings. |
| `get_alarm_video_shelter_info(channel_id=1)` | `CameraDeviceAlarmVideoShelterInfo` | Video-shelter alarm settings. |
| `get_motion_detection_info()` | `CameraDeviceMotionDetectionInfo` | Device motion-detection settings. |
| `get_human_trace_info()` | `CameraDeviceHumanTraceInfo` | Human-trace settings. |
| `get_move_detection_info()` | `CameraDeviceMoveDetectionInfo` | Move-detection settings. |
| `get_alarm_motion_detection_schedule(channel_id=1)` | `CameraDeviceAlarmScheduleInfo` | Motion alarm schedule. |
| `get_alarm_video_lost_schedule(channel_id=1)` | `CameraDeviceAlarmScheduleInfo` | Video-lost schedule. |
| `get_alarm_video_shelter_schedule(channel_id=1)` | `CameraDeviceAlarmScheduleInfo` | Video-shelter schedule. |
| `get_alarm_input_schedule(channel_id=1)` | `CameraDeviceAlarmScheduleInfo` | Alarm-input schedule. |

### Accessories And Device Features

| Method | Returns | Purpose |
| --- | --- | --- |
| `get_device_attachment_info()` | `CameraDeviceAttachmentInfo` | Attached channels, locks, elevators, and switches. |
| `get_ptz_state()` | `CameraDevicePtzStateInfo` | PTZ state; does not move the camera. |
| `get_ptz_presets()` | `CameraDevicePtzPresetInfo` | Existing presets; does not select one. |
| `get_smart_light_info(room=1)` | `CameraDeviceSmartLightInfo` | Smart-light state for a room. |
| `get_sound_light_info(channel_id=1)` | `CameraDeviceSoundLightInfo` | Sound/light alarm settings. |
| `get_audio_volume_info()` | `CameraDeviceAudioVolumeInfo` | Volume settings/ranges. |
| `get_audio_session_info()` | `CameraDeviceAudioSessionInfo` | Audio session metadata; does not start talkback. |
| `get_hardware_info()` | `CameraDeviceHardwareInfo` | Hardware information. |
| `get_light_info()` | `CameraDeviceLightInfo` | Light settings. |
| `get_babysitter_state_info()` | `CameraDeviceBabysitterStateInfo` | Babysitter feature state. |
| `get_pir_config_info()` | `CameraDevicePirConfigInfo` | PIR configuration/schedule. |
| `get_third_party_push_info()` | `CameraDeviceThirdPartyPushInfo` | Existing push settings; does not register push. |
| `get_smart_switch_info()` | `CameraDeviceSmartSwitchInfo` | Switch state/settings. |
| `get_lock_status_info()` | `CameraDeviceLockStatusInfo` | Lock status/settings; does not unlock. |
| `get_floodlight_switch_info()` | `CameraDeviceFloodlightSwitchInfo` | Floodlight state. |
| `get_floodlight_schedule_info()` | `CameraDeviceFloodlightScheduleInfo` | Floodlight schedule. |
| `get_city_coordinate_info()` | `CameraDeviceCityCoordinateInfo` | City/coordinate settings; potentially sensitive. |
| `get_voice_message_info()` | `CameraDeviceVoiceMessageInfo` | Voice-message/file metadata. |

### Upgrade Information

| Method | Returns | Purpose |
| --- | --- | --- |
| `get_upgrade_version_info()` | `CameraDeviceUpgradeVersionInfo` | Available version information. |
| `get_upgrade_status_info()` | `CameraDeviceUpgradeStatusInfo` | Upgrade status. |
| `get_upgrade_process_info()` | `CameraDeviceUpgradeProcessInfo` | Progress information. |

These are queries, not firmware-update commands.

## Archive Queries

These are local CGI methods with the same common arguments and credentials as
[local inspection](#local-device-read-only-methods). They list archive metadata;
they do not download or play stored recordings.

| Method | Returns | Purpose |
| --- | --- | --- |
| `get_record_config_info(channel_id=1)` | `CameraDeviceRecordConfigInfo` | Recording mode, stream, and schedule. |
| `get_record_session_info(start_time=..., end_time=...)` | `CameraDeviceRecordSessionInfo` | Open a read-only archive search session. |
| `get_record_message_info(session_id=...)` | `CameraDeviceRecordMessageInfo` | Read one page for the returned search-session id. |
| `list_record_files(start_time=..., end_time=..., max_pages=32)` | `CameraDeviceRecordListInfo` | Search and collect pages up to a safety cap. |
| `get_record_alarm_info(timestamp=...)` | `CameraDeviceRecordAlarmInfo` | Read archive entries associated with an alarm timestamp. |

Time/session arguments shown as `...` are **required strings**. The search
methods and `get_record_alarm_info()` also accept `channel_id=1`,
`file_type="all"`, `occur_type="all"`, and `stream="all"` (or `"main"` / `"sub"`).
The alarm query additionally accepts `alarm_type=None` and `alarm_id=None`.
Preserve the device's timestamp convention; archive strings and cloud-history
time bounds are different interfaces and must not be assumed interchangeable.

The list result exposes `records`, fetched `pages`, session/status fields, and
completion information. A page cap is not proof of a complete archive search.
Calendar/day/month queries and archive downloading are not exposed by this API.

## Door Control

| Method | Returns | Purpose |
| --- | --- | --- |
| `open_door(...)` | `CameraDoorOpenResult` | Send one local `set.device.opendoor` command. |

Configure `CAMERA_DEVICE_HOST`, `AUTH_CODE`, and the separate `UNLOCK_PASSWORD`.
Default `password_mode="auto"` uses capability 24 (`TYPE_ENCRYPY_SHA256`),
matching the original client. A set flag selects vendor password encoding;
a clear flag sends the opening password unchanged. CGI header authentication
continues to encode `AUTH_CODE` in both modes.

| Argument | Default and meaning |
| --- | --- |
| `channel` | `None`; use the camera channel, sent as native `door`. |
| `lock_number` | `1`; positive lock/relay number. |
| `unlock_password` | `None`; use the camera's opening password. Accepts plain text or a vendor-encoded value. |
| `password_mode` | `"auto"`; cached capability or a read-only cloud metadata lookup. Explicit `"plain"` / `"sha256"` skips that lookup. |
| `port`, `scheme` | `80`, `"http"`; local CGI address, not native port `34567`. |
| `auth_code` | `None`; use the camera's CGI authentication code. |
| `verify_tls` | `None`; follow camera configuration for HTTPS CGI. |
| `debug` | `False`; request redacted DEBUG exchange logging. |

**The following example sends a real opening command:**

```python
from quii_helper import Camera, load_config

camera = Camera(config=load_config())
result = camera.open_door(lock_number=1, password_mode="auto")
print(result.accepted, result.error, result.message)
```

`accepted=True` requires an explicit numeric `<error>0</error>` response.
It means the device acknowledged the command, not that the door physically
moved. Error descriptions are command-specific.

Unknown capability in `auto` mode raises `ConfigurationError` **before** an
opening command. Choose an explicit mode only after verifying the device's
requirements. There is no automatic retry, redirect, alternate-format attempt,
or cloud IoT unlock fallback. After transport/response failure, the physical
outcome can be unknown: do not retry automatically.

On Tantos Marilyn Wi-Fi s, the user confirmed physical opening in `auto`
mode with capability 24 enabled. This does not validate the plain-password
path or all firmware; see [Compatibility](../COMPATIBILITY.md).

### Async Applications

Use a thread adapter when embedding synchronous calls in an async service:

```python
import asyncio

from quii_helper import Camera, CameraDoorOpenResult


async def open_configured_door(camera: Camera) -> CameraDoorOpenResult:
    return await asyncio.to_thread(camera.open_door, password_mode="sha256")
```

Calling this function sends a real command. Cancelling its await does not
stop an already running thread; a caller timeout must not trigger an unlock
retry. Authentication, operation deduplication, and access policy belong to
the embedding service, not this transport library.

## Error Codes

Exceptions and firmware rejection are different outcomes:

| Exception/result | Meaning |
| --- | --- |
| `ConfigurationError` | Missing/invalid configuration; also a `ValueError`. Some argument validators raise plain `ValueError`. |
| `AssetMissingError` | Missing/incompatible required asset; also a `FileNotFoundError`. |
| `QuiiConnectionError` | Cloud/device transport, malformed response, or terminal receive failure; also an `OSError`. |
| `CameraCaptureError` | Requested media artifact could not be produced. |
| `MediaRenderError` | Rendering failed; subclass of `CameraCaptureError`. |
| Nonzero response `error` | The device answered but rejected/does not support that command. Inspect the response instead of assuming an exception. |

`QuiiHelperError` is the common domain base class; not every low-level Python
or argument error is normalized into it. Do not hide programming errors with
unconditional retry loops. Unlock failures require the special caution above.

For numeric error interpretation, the optional helper
`quii_helper.support.error_codes.describe_error_code(code, domain="device_cgi")`
preserves vendor-layer context. Use `domain="device_unlock"` for unlock results;
the same integer can mean different things in different layers. Unknown codes
are retained, not converted to success. Raw responses can contain private data.
See [Troubleshooting](setup.md#troubleshooting) for common setup failures.

## Application Entry Point

Bundled examples require a checkout or extracted source distribution, run
from its root after installation/configuration:

| Command | Effect |
| --- | --- |
| `python -m examples.discover_env_values` | Service discovery; prints candidate cloud settings. |
| `python -m examples.call_events` | Read one history page; may create an alarm reader session. |
| `python -m examples.snapshot` | Capture one JPEG. |
| `python -m examples.save_video` | Record the example's default 30-second collection window. |
| `python -m examples.serve_rtsp` | Serve RTSP on localhost port `8554`. |
| `python -m examples.open_door` | Print capability 24 and send a **real opening command** in auto mode. |

The installed entry point `python -m quii_helper.main` also serves RTSP until
`Ctrl+C`, without opening a door. It currently forces `stream_quality="high"`,
`live_newcn=True`, and **`tls_verify=False`**, overriding `.env` for those
options. Prefer the API example or `examples.serve_rtsp` when configured TLS
verification must be respected.
