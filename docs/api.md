# Camera API Reference

The stable public API is centered around `Camera`.

```python
from quii_helper import Camera

camera = Camera()
```

By default, `Camera()` loads settings from `.env` and assets from `assets/`.

## Constructor

```python
Camera(config=None, connector=None)
```

| Parameter | Purpose |
| --- | --- |
| `config` | Optional configuration object. If omitted, settings are loaded from `.env`. |
| `connector` | Optional preview connector. Mainly useful for tests or custom integrations. |

## Capture Methods

### `snapshot()`

Captures one JPEG image from the live preview.

```python
result = camera.snapshot()
print(result.path)
```

The output path is generated under `data/` with a timestamp-based filename.

### `save_video(duration_seconds=15)`

Captures a video clip and writes an MP4 file.

```python
result = camera.save_video(duration_seconds=60)
print(result.path)
```

`duration_seconds` is the requested media collection time after the preview session starts receiving packets.

### `capture(...)`

Lower-level capture method used by `snapshot()` and `save_video()`.

Use it when you need both artifacts or need access to the full capture summary.

```python
result = camera.capture(duration_seconds=15)
print(result.media_result)
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
