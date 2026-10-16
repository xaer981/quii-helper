# Camera API Reference

The stable public API is centered around `Camera`.

```python
from quii_helper import Camera

camera = Camera()
```

By default, `Camera()` loads settings from `.env` and assets from `assets/`.

## Constructor

```python
Camera(config=None, device_host=None, auth_code=None, unlock_password=None)
```

Selected constructor parameters are shown below; the class docstring documents
the complete signature. Keyword arguments override the base configuration.

| Parameter | Purpose |
| --- | --- |
| `config` | Optional configuration object. If omitted, settings are loaded from `.env`. |
| `device_host` | Camera LAN IP or hostname for local CGI methods; defaults to `CAMERA_DEVICE_HOST`. |
| `auth_code` | Local CGI authentication code; defaults to `AUTH_CODE`. |
| `unlock_password` | Separate door-opening password; defaults to `UNLOCK_PASSWORD`. |

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

### `serve_rtsp(port=8554, path="/live")`

Starts a local RTSP server and forwards camera H.264 frames to connected clients.

```python
from quii_helper import Camera

camera = Camera()

with camera.serve_rtsp(port=8554) as session:
    print(session.url)
    input("Press Enter to stop...")
```

Open in VLC:

```text
rtsp://127.0.0.1:8554/live
```

The context manager closes the preview session and RTSP server automatically.

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
from quii_helper import Camera

camera = Camera()
result = camera.open_door(lock_number=1)
print(result.accepted, result.error, result.message)
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

Example:

```python
info = camera.get_device_info()
print(info.device_id)
print(info.transparent_basedata)
```

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

## Bulk Probe

For local development, `quii_helper.main` can be temporarily edited or used as a scratch entry point to call multiple read-only methods and inspect which ones your device supports.

```powershell
python -m quii_helper.main
```
