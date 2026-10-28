# Camera API Reference

[Documentation](README.md) | [Setup](setup.md) | [Compatibility](../COMPATIBILITY.md)

`Camera` is the public entry point. The API is synchronous; importing the
package or constructing a camera does not connect to a device.

## Connection Modes

`connection_mode="lan"` is the default, including when cloud credentials
are present in the environment. It never fetches or renews credentials and has
no cloud/P2P/relay fallback. Cloud metadata/history methods reject this mode
before I/O. Local CGI methods remain available without a stream key; door
`password_mode="auto"` cannot perform a cloud capability lookup in this mode.

LAN `capture()`, `snapshot()`, `save_video()`, `record()`, `serve_rtsp()` and
`listen_audio()` use the direct TCP session and shared CFrame components.
Experimental `talk()` opens a separate active LAN TCP talk connection; it is
never started by preview, recording or RTSP. Experimental `converse()` adds
explicit local microphone/headphones I/O on top of `talk()`.
Invalid LAN settings
fail before connecting (and before RTSP binds a listener). Invalid keys,
unsupported profiles and connection failures never trigger a cloud fallback.
Select `connection_mode="cloud"` explicitly for the cloud/P2P pipeline.

LAN TCP requires an explicit IP, port (default `34567`), `auth_code` and a
saved `stream_key` containing exactly 32 UTF-8 bytes. The key is not hex/base64
decoded, silently padded, fetched through CGI, or loaded implicitly from a file.
AUTH_CODE may be raw or already encoded according to the native client rule.
No cloud account, device id, APK assets or TLS bypass is needed for TCP itself.
Initially only AES-256/SHA256 with media flag 15 equal to zero is supported.
Other profiles fail explicitly; key lifetime and reboot persistence are unknown.

Use the separate [cloud bootstrap API](#stream-key-bootstrap-and-persistence)
to obtain/save the key explicitly, then create a LAN Camera with the loaded
key/auth pair. The LAN client itself never contacts cloud, discovers a saved
file, changes `.env`, or renews expired credentials.

## Contents

- [Constructor](#constructor) and [configuration](#library-configuration).
- [Connection modes](#connection-modes), including direct LAN playback.
- [Stream-key bootstrap and persistence](#stream-key-bootstrap-and-persistence).
- [Capture](#capture-methods), [RTSP](#rtsp-streaming), and [logging](#logging).
- [Receive-only audio](#receive-only-audio-experimental); no talkback or playback.
- [LAN talk](#lan-talk-experimental); explicit active operation, not RTSP backchannel.
- [Computer conversation](#computer-conversation-experimental); microphone and headphones.
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
| `connection_mode` | `"lan"` by default; `"cloud"` is explicit opt-in to cloud/P2P operations. |
| `stream_port` | Native LAN TCP port; default `34567`, not the CGI HTTP port. |
| `stream_key` | Saved 32-byte UTF-8 LAN stream key; secret, hidden in config representations and diagnostics. |
| `device_id` | Device identifier; `DEVICE_ID` in environment-backed configuration. |
| `cloud_account`, `cloud_username` | Cloud login; `cloud_username` is an alias. |
| `cloud_password` | Cloud account password. |
| `device_host` | Explicit IP for LAN TCP; LAN host/IP for local CGI methods. Not discovered implicitly. |
| `auth_code` | LAN TCP/CGI authentication code, separate from the opening password. |
| `unlock_password` | Door-opening password used only by explicit `open_door()` calls. |
| `channel` | Video-panel channel; base default `1`. LAN accepts `1-65535`; the device determines which inputs actually exist. |
| `stream` | Numeric stream id; base default `2`. LAN accepts `1-256`, but available profiles are device-specific. |
| `stream_quality` | Friendly selector such as `"high"` (`1`) or `"low"` (`2`). Mutually exclusive with an explicit `stream`. |

For environment-backed configuration, use the same profiles in `CAMERA_STREAM`:
`high` / `main` / `1` selects stream 1, `low` / `sub` / `2` selects stream 2
(default). Other positive numeric ids remain available for device-specific
profiles. `load_config()` resolves the value to an integer; the numeric
`AutonomousConfig.stream` field and wire format do not change. Exact resolution
depends on firmware. An explicit `Camera(..., stream_quality=...)` or `stream=...`
overrides the loaded value; `channel` independently selects the panel.

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
| `live_play_payload` | Advanced cloud live-play variant: `"path"` (default) or `"oem"`. LAN always uses `"path"`. |
| `live_inner`, `live_newcn` | Advanced cloud packet/URL flags; defaults `False`. LAN always uses both `False`. |
| `live_keepalive_interval` | Live keepalive interval; base default `10.0` seconds. |
| `play_sync_iterations` | Extra post-play sync iterations; base default `0`. |
| `enable_play_probes` | Extra play probes; base default `False`. |

Advanced protocol options are compatibility controls, not general performance
presets. Change them only with device/native evidence. The defaults above are
plain configuration defaults; environment settings or a supplied config can
replace them.

LAN playback emits a standard Python `UserWarning` for non-default values of
`live_play_payload`, `live_inner`, and `live_newcn`, then uses the verified
default profile. Older examples keep working, without silent overrides or a
cloud fallback. Leave these options at their defaults; they do not select the
panel or quality. Invalid IPs, keys and selector ranges still raise errors.
The cloud path retains its existing handling, but support for alternative
combinations depends on the device and is not universally verified. Native
`inner=1` sets a play-header flag; the full firmware meaning of `inner` and
`newcn` is not established.

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

LAN MP4 uses the first accepted video frame's FPS (or FFmpeg's H.264 timing
when it is zero); sparse frames are **not stretched** to the collection window.
Frames before the first keyframe are suppressed like the native player.
Recording buffers up to 256 MiB of combined video/audio payload, then raises
`CameraCaptureError` instead of returning a silently shortened clip. Use shorter
recordings or RTSP for long-running viewing. Variable-FPS preservation is not
implemented. The budget is payload size, not a bound on total process RSS.
RBUDP message limits, post-capture drain and sample-file diagnostics are not
used in LAN mode; its summary includes TCP, CFrame and NAL statistics instead.

### MP4 Audio

`save_video()`, `record()`, and MP4-producing `capture()` calls automatically
include available G.711 A-law/mu-law audio at 8000 Hz mono from the **same
preview connection**. FFmpeg copies H.264 and encodes audio as AAC; no second
session, microphone or talk command is started. RTSP remains video-only unless
`audio=True` is explicitly requested.

Audio is anchored to the first retained video frame using native timestamps;
leading samples are trimmed, a late start gets initial silence, and the tail
is padded/trimmed to the produced video's duration. Short audio never truncates
video, and video frames are not repeated to fill the requested window. Native
audio timestamp jitter is handled with a continuous sample clock, as in RTSP;
lost samples are not reconstructed. Precise lip-sync is not guaranteed.

Without audio, MP4 remains video-only. Unsupported/changed audio formats,
unusable timestamps, or unknown video duration cause a `UserWarning` and
video-only output; encoding/file errors remain render failures. The artifact's
`summary["audio"]` reports `included`, `source_codec`, `samples`,
`offset_seconds`, and `skipped_reason`. Private temporary audio is placed next
to the output and removed after rendering, including on failure. Snapshots
do not retain an audio recording. Live cloud/Vimar MP4 audio remains unverified.

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

## Receive-Only Audio (Experimental)

This API is available since **0.3.0**. Tantos G.711 A-law reception
was tested on a physical Pi; Vimar audio remains unverified. It reads E3 frames from a LAN preview
using the same saved key/auth pair as video. It never fetches or renews keys,
contacts cloud, opens a talk connection or activates a microphone/speaker.
Cloud mode is rejected before connecting. Each call opens a separate preview
session and discards its video; avoid unnecessary simultaneous sessions on a
resource-constrained intercom.

| Method | Returns | Purpose |
| --- | --- | --- |
| `listen_audio()` | `CameraAudioStream` | Open receive-only encoded audio over a separate LAN preview session. |

```python
from quii_helper import Camera, CameraStreamCredentials, load_config

saved = CameraStreamCredentials.load("data/stream_credentials.json")
camera = Camera(
    config=load_config(),
    connection_mode="lan",
    stream_key=saved.stream_key,
    auth_code=saved.auth_code,
)
with camera.listen_audio() as audio:
    frame = audio.recv_frame(timeout=5.0)
    print(frame.codec_name, frame.sample_rate, frame.channels, len(frame.data))
```

| Handle / field | Meaning |
| --- | --- |
| `audio.recv_frame(timeout=5.0)` | Wait at most this many seconds for one complete `CameraAudioFrame`, including time spent receiving video/control messages. |
| `audio.close()` | Close the owned socket and discard queued/partial frames; repeat calls are safe. A closed handle cannot reopen. |
| `frame.data` | Encoded audio bytes without the CPacket header, **not necessarily PCM or a WAV file**. Hidden from the frame's representation. |
| `frame.codec`, `frame.codec_name` | Original codec id; verified names are `4=g711_alaw`, `5=g711_mulaw`, `9=pcm`. Other ids remain `codec_N`; no decoding is attempted. |
| `frame.sample_rate`, `frame.channels` | Values reported by each frame; a stream may change format. |
| `frame.frame_stamp`, `frame.milliseconds` | Raw packed device-local calendar and its millisecond component, **not a Unix timestamp**. No timezone conversion is guessed. |

`TimeoutError` means no complete audio arrived within the deadline. The
connection and partial frame remain available for another read. Successful
video does not guarantee audio; a silent/unsupported device may time out.
Invalid audio metadata, EOF and connection errors raise `QuiiConnectionError`
and close the stream. Invalid timeouts raise `ValueError` before reading.
Use one reader per handle; another thread may call `close()` to cancel I/O.
The stream has no background reader or retained history: drain it promptly.
It is not a lossless recording API or a local playback/PCM decoder.

Run `python -m examples.listen_audio` to print metadata for ten frames with
saved credentials. It writes no files and sends no audio or door commands.
For combined A/V, use `serve_rtsp(audio=True)` instead of opening a separate
`listen_audio()` connection. JPEG has no audio; MP4 recording automatically
includes supported audio as described in [MP4 Audio](#mp4-audio).

## LAN Talk (Experimental)

**Unreleased.** A saved-key Pi probe on Tantos confirmed sound from panel 2
with preview active and generic talk selector `65535`; this updated API
coordinator has offline/native checks, not a fresh hardware test. Vimar talk,
normal conversation and echo cancellation remain unverified.
`talk()` is **not read-only**: opening the
session reserves audio resources and may interrupt an intercom call even
before samples are sent. It never opens the door or starts a local microphone
or speaker. Receive-only users should keep using `listen_audio()` or RTSP.

| Method | Returns | Purpose |
| --- | --- | --- |
| `talk(channel=None, full_duplex=False)` | `CameraTalkSession` | Own two LAN connections: selected-panel preview for receiving audio, generic talk for sending. Saved credentials only; no cloud fallback. |

| Parameter / field | Meaning |
| --- | --- |
| `channel` | Preview panel, `1-65535`, defaulting to the Camera's channel. The Camera configuration is not mutated. Talk always uses `65535`; `channel=0` is no longer a generic-talk override. `stream`/quality affects preview only, not the outgoing codec. |
| `full_duplex=False` | SDK-style talk-side receive disable/restore requests around each `send_pcm()` batch, with ACK checks. Preview audio continues to be drained and remains available to the caller. |
| `full_duplex=True` | Skip talk-side receive toggles. Incoming audio still comes from preview, not talk; this does not guarantee hardware duplex or echo cancellation. |
| `talk.send_pcm(pcm)` | Block while sending **640-16000 bytes**, a multiple of **640**, signed PCM16 little-endian, **8000 Hz mono**. The library encodes G.711 and paces 320-sample frames at 40 ms, without catch-up bursts. |
| `talk.recv_frame(timeout=5.0)` | Return encoded G.711 from the selected panel's preview, never mixed with talk-socket media. A finite positive read timeout preserves both connections. May run alongside the single sender. |
| `talk.codec` | Negotiated outgoing codec: `4` (A-law) or `5` (mu-law). Unsupported codec masks fail before audio transmission. |
| `talk.frames_sent`, `talk.dropped_frames` | Outgoing frame count and incoming queue losses. At most 64 received frames are retained; a slow reader loses the oldest. |
| `talk.close()` | Interrupt both sockets, wake waiting callers, discard buffers and join both workers. Idempotent; a closed session cannot reopen. |

Startup opens preview first and waits at most `connect_timeout` for its first
supported audio frame after preview transport startup. That frame is queued,
not consumed solely as a readiness signal; the normal 64-frame drop policy
still applies during talk startup. Only then does generic talk connect and negotiate. Video and
control traffic cannot extend the audio-readiness deadline. Missing audio,
invalid data or failure of either connection closes **both**; there is no
fallback to talk-side reception. Each handle owns its own preview; do not
open `listen_audio()` as well for the same conversation.

Use the Camera configured with the saved key/auth pair from the LAN example
above. Supply your own already converted PCM; the core API does not decode
WAV/MP3, resample, pad incomplete blocks or capture a microphone:

```python
# Active operation: this sound will be sent to the intercom speaker.
pcm = bytes(640)  # 40 ms of silence; replace with your converted PCM source.
with camera.talk(channel=2) as talk:
    talk.send_pcm(pcm)
    incoming = talk.recv_frame(timeout=5.0)
    print(incoming.codec_name, len(incoming.data))
```

Only one sending caller is allowed. One bounded batch is retained; callers
must buffer/chunk their source and avoid unbounded producer queues. A return
from `send_pcm()` confirms transport completion and the receive-restoration
ACK, **not audible playback**. In full-duplex mode there is no restoration
request. Connection/protocol errors raise `QuiiConnectionError`, close the
pair and wake both directions; no automatic reconnect or retransmission
occurs. `connect_timeout` bounds each transport startup, the initial preview
audio wait, and each talk control/send operation; it is not one aggregate
deadline for the entire two-connection startup.

The supported wire profile is AES-256/SHA256, G.711 A-law/mu-law at 8000 Hz
mono, CPacket incoming audio, and either compact or full CPacket outgoing
audio as negotiated by Open. Other codecs/profiles fail explicitly. The
native client's optional vEye Pro `client_id`/`uhid` metadata and legacy
HS/GLNK fallback are not implemented. See [native parity notes](protocol-notes.md#lan-talk).

`python -m examples.talk` sends **`data/talk.wav`** using saved credentials.
It validates an uncompressed PCM16 LE, 8000 Hz mono WAV before connecting,
reads at most one second per batch and explicitly pads the last block with
less than 40 ms of silence. `CAMERA_CHANNEL` selects its preview panel;
generic talk is selected automatically. It does not run from the default main. Test on
your own hardware only when talk activation is safe; do not assume a working
video or receive-only audio stream proves outgoing talk support.

## Computer Conversation (Experimental)

**Unreleased source checkout.** Start preview normally with `serve_rtsp()`,
then explicitly enable conversation through its returned session. Video and
incoming sound share **one preview, one reader and one CFrame packer**; only
generic talk `65535` is added for sending microphone audio. No WAV, FFmpeg,
cloud request or door command is needed. Starting preview alone neither
accesses audio devices nor reserves talk. Physical PC duplex/Vimar quality
has not been confirmed; current session integration checks are offline.

Install the optional dependency in your checkout's virtual environment:

```shell
python -m pip install -e ".[audio]"
python -m examples.converse --list-devices
python -m examples.converse --channel 2
```

The example uses `data/stream_credentials.json` and the same LAN `.env`
settings as `examples.lan_rtsp`. It serves video-only RTSP first. Open that URL
in VLC after media is ready, then press Enter to enable the microphone and
local incoming-audio playback. Press Enter again to stop conversation; video
continues until Ctrl+C. `--seconds N` limits conversation instead of the second
Enter; it still requires the first confirmation. `--port` defaults to 8554.
Default devices come from the OS. To choose a headset explicitly, copy exact
names from `--list-devices`:

```shell
python -m examples.converse --channel 2 --input-device "Headset microphone" --output-device "Headphones"
```

For library use, configure `camera` with a local IP and saved key/auth pair as
in [LAN setup](#connection-modes). The preview's panel/stream are used for
conversation too; configure `Camera(channel=2, ...)` to select panel 2, not
`start_talk(channel=2)`. Your application decides when to activate talk:

```python
with camera.serve_rtsp(port=8554) as session:
    # The application can call start_talk() from its Talk button.
    conversation = session.start_talk()
    try:
        conversation.wait(timeout=10)
    finally:
        session.stop_talk()  # Microphone off; video is still running.
    session.wait()
```

| Preview session | Meaning |
| --- | --- |
| `session.start_talk(input_device=None, output_device=None)` | Wait for audio/talk readiness, then return a nonblocking `CameraConversationSession`. Explicitly activates the PC microphone/playback; adds only generic talk, no second preview. LAN only. |
| `session.stop_talk()` | Stop/cancel microphone, local playback and talk, leaving preview/RTSP alive. Idempotent. A later start creates a fresh talk session. |
| `session.talk_active` | Whether local audio is active; False during startup/after stop. |
| `session.talk_error` | Last isolated talk failure, cleared on the next start attempt. Preview failure is separate and raised by `session.wait()`. |
| `conversation.wait(timeout=None)` | Wait interruptibly and raise asynchronous talk/audio errors. A finite nonnegative timeout leaves the handle active; it is not a recording duration. |
| `conversation.active`, `conversation.error` | Active state and first asynchronous error of this particular handle. |
| `conversation.close()` | Same ownership boundary as `stop_talk()`; also called by `with session.start_talk() as conversation:`. Never closes the parent preview. |

Duplicate/parallel starts are rejected rather than opening multiple
microphones or talk connections. Starting from a producer/status callback
is rejected because a blocking readiness wait would deadlock that reader;
call it from the application's control thread. Missing audio times out before
the talk handshake: the shared-preview first-audio gate allows at most
`2 * connect_timeout`, including an already-starting preview. The subsequent
talk handshake has its own `connect_timeout`. Stopping during startup cancels
talk without closing preview. Local device initialization follows OS/driver
timing; it has no separate hard cancellation guarantee.

Talk/device failures close only conversation and remain available through
`conversation.wait()` / `session.talk_error`; `session.wait()` still waits for
the preview, not talk. Parent preview failure or `session.close()` stops both.
No automatic restart occurs. If RTSP has `audio=True`, mute VLC while the
conversation plays incoming sound locally to avoid hearing it twice.
RTSP `audio=True` retains its own strict codec/timestamp checks; an invalid
RTSP audio profile can still stop the parent independently of talk.

For a standalone blocking conversation without RTSP, `Camera.converse()` is
still available. It creates its own preview; **do not start it alongside an
existing RTSP session** when you want shared media. The lower-level `talk()`
API remains for application-supplied PCM without local audio devices.

| Method | Returns | Purpose |
| --- | --- | --- |
| `converse(channel=None, input_device=None, output_device=None, duration_seconds=None, stop_event=None)` | `None` | Blocking computer conversation until Ctrl+C, cancellation, duration or error. Both local audio and the two LAN sessions are closed on exit. |

| Parameter | Meaning |
| --- | --- |
| `channel` | Selected preview panel, defaulting to the Camera's channel; same validation as `talk()`. |
| `input_device`, `output_device` | Exact OS device names, or `None` for defaults. Missing/ambiguous explicit names are errors, not silent fallback. |
| `duration_seconds` | Standalone `Camera.converse()` only: finite positive duration after audio starts. Session `start_talk()` has no duration; stop it explicitly. |
| `stop_event` | Optional `threading.Event`; set it from another thread to stop. A pre-set event starts neither audio nor a connection. Startup TCP stages still have their own `connect_timeout` bounds. |

**Use headphones.** This is simultaneous transmit/receive (`full_duplex=True`),
not push-to-talk, and does not implement acoustic echo cancellation, automatic
gain control or noise suppression. Speakers can produce feedback. Firmware
may impose its own half-duplex behavior; the physical PC path still needs
validation. OS microphone permission and working local audio drivers are
required. The optional `miniaudio` backend handles device-rate conversion to
8000 Hz mono signed PCM16. A missing physical backend is an error, not a
successful silent session.

Native audio callbacks never wait for network I/O. Each PCM queue is bounded
to 200ms and drops the oldest samples on overload; when capture falls behind,
only its newest complete 40ms block is sent, not a burst of stale speech.
Capture is clocked by the audio device, without adding the raw PCM sender's
playback wait a second time. This is real-time voice, not lossless recording.
Microphone capture starts only after talk is ready.
Ctrl+C propagates as `KeyboardInterrupt` after cleanup (the example catches
it for a quiet exit). Local failures raise `AudioDeviceError`; camera failures
retain `QuiiConnectionError`. Neither causes automatic reconnect/replay.
Captured audio is not saved or logged. Other Camera methods and imports do
not activate local audio and do not require the optional dependency.
Audio devices belong to the machine running Python, not the RTSP viewer.
Running this on a headless Pi does not give it access to a laptop microphone.

## RTSP Streaming

| Method | Returns | Purpose |
| --- | --- | --- |
| `serve_rtsp(host="127.0.0.1", port=8554, path="/live", audio=False)` | `CameraRtspStream` | Start a listener and one background preview producer; audio is opt-in. |

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

Since 0.3.0, pass **`audio=True`** for H.264 plus G.711
A-law/mu-law, 8000 Hz mono. Both tracks use **the same camera connection and
CFrame assembler**; do not open `listen_audio()` as well. `serve_rtsp()` alone
starts no audio decoding, resampling, microphone, speaker or talk connection;
those are explicit opt-ins through `session.start_talk()`.
The library default remains video-only; `quii_helper.main` opts into audio.

RTSP paths are normalized (`"/live/"` becomes `"/live"`; `"/"` is supported).
DESCRIBE returns a `Content-Base` matching the authority used by the viewer,
so relative SDP track URLs work without relying on player-specific URL rules.
Live PLAY responses do not announce `RTP-Info` sequence/timestamp values that
cannot be known before the next keyframe; timestamps remain in the RTP packets.

With audio enabled, SDP advertises track 0 (H.264) and track 1 (PCMA/PCMU) only
after actual audio format and H.264 parameters are available. An early DESCRIBE
can wait up to ten seconds, then return `503`/`Retry-After`. Unknown audio
profiles, a codec change or invalid device timestamps fail explicitly and stop
the producer; use `audio=False` on unsupported cameras. A joining/resuming
viewer waits for a keyframe rather than receiving undecodable P-frames.
Source timestamps are mapped to a common device-relative A/V timeline, but
precise lip-sync is not guaranteed across players: RTCP sender reports are not
implemented yet. TCP interleaving and separate per-track UDP transports are
covered by offline tests; Tantos combined A/V was decoded on a Pi over TCP and UDP.
Vimar/cloud audio and subjective sound quality remain unverified.

| Stream handle | Meaning |
| --- | --- |
| `session.url` | Address, **not** a readiness check. |
| `session.stats` | Current RTSP/H.264 counters and `talk_active`. |
| `session.wait(timeout=None)` | Wait for completion; re-raise producer failure; remain responsive to `Ctrl+C`. A timeout alone does not close the stream. |
| `session.close()` | Request cancellation and release the listener; also called by the context manager. |
| `session.start_talk()` / `session.stop_talk()` | Explicit PC conversation on the same LAN preview; see [computer conversation](#computer-conversation-experimental). Preview alone never opens audio devices. |

The `RTSP stream ready` log appears after the first assembled H.264 access
unit (and known audio format/SPS/PPS when enabled), if library logging is enabled.
A producer failure closes the listener;
there is no automatic camera reconnect. An in-flight cloud/connection call can
finish only at its own timeout during shutdown; subsequent startup stages are
cancelled and overlapping restarts are rejected while the producer is stopping.
For LAN, closing the stream also shuts down its TCP socket during setup or
receive; a still-running connect must return at its configured timeout. Each
restart creates a fresh session; a closed session is not reused.

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

These operations require an explicitly selected `connection_mode="cloud"`;
the default LAN-only client rejects them without network access.

These methods use cloud/app services, not the camera's LAN CGI endpoint.
They do not open a preview or send opening commands.

| Method | Returns | Purpose |
| --- | --- | --- |
| `get_device_info()` | `CameraDeviceInfo` | Login, device-token metadata, and best-effort device-list enrichment. |
| `get_device_shadow_info()` | `CameraDeviceShadowInfo` | Cloud shadow/device state where supported. |
| `get_iot_command_support()` | `CameraIotCommandSupportInfo` | Command-support metadata, not command execution. |
| `get_call_events(...)` | `CameraCallEventPage` | Experimental incoming-call journal history. |
| `fetch_stream_credentials()` | `CameraStreamCredentials` | Fresh cloud login + device-token query; return a minimal key/auth pair for explicit LAN playback. |

Sparse fields in `CameraDeviceInfo` do not necessarily mean parsing failed.
`supports_sha256_password` is `True`, `False`, or `None` when capability data
is missing/invalid. Do not log raw credentials or basedata publicly.

### Stream-Key Bootstrap And Persistence

`Camera.fetch_stream_credentials()` is a deliberate cloud operation, rejected
in default LAN mode before I/O. It always performs a fresh `login` and
`get-device-token`, not a cached metadata lookup. It honors configured TLS
verification; it does not silently disable TLS, discover P2P services, register
push notifications, open a preview or send device/door commands. The existing
cloud account/device/app settings and auth URL are required; with those values
already configured, this flow does not read APK assets. The shared config
validator still requires `CLOUD_SERVICE_URL`, even though no discovery query
is sent here.

Before calling this method, complete the
[first-run cloud configuration](setup.md#first-run-fetch-and-save):
`CLOUD_ACCOUNT`, `CLOUD_PASSWORD`, `DEVICE_ID`, `CLOUD_CLIENT_UUID`,
`CLOUD_AUTH_URL`, `CLOUD_SERVICE_URL`, `CAMERA_OEM`, `CAMERA_APP_ID`,
`CAMERA_CLIENT_TYPE` and `IP_REGION_ID`. Local IP/channel/stream values alone
are not sufficient. The setup guide distinguishes these required values from
conditional auth-version/TLS options and the much smaller
[later LAN-only configuration](setup.md#later-runs-load-and-view-locally).

`CameraStreamCredentials` contains `device_id`, secret `stream_key` and secret
`auth_code`. The last two are hidden from `repr`, but can be accessed explicitly
for application use. The returned auth code comes from the same cloud response
as the key, **not** from an older `.env` value. Raw/encoded auth code handling
matches the existing LAN session. This API is distinct from the local CGI
`get_stream_key_info()` query, which depends on firmware support.

| Credential operation | Effect |
| --- | --- |
| `credentials.save(path)` | Write minimal versioned JSON atomically; create parent directories and replace an existing file. Return its absolute `Path`. |
| `CameraStreamCredentials.load(path)` | Read and validate that file (up to 4 KiB); perform no network request or refresh. |

Acquire and save credentials without starting a preview:

```python
from pathlib import Path

from quii_helper import Camera, load_config

config = load_config()
cloud_camera = Camera(config=config, connection_mode="cloud")
credentials = cloud_camera.fetch_stream_credentials()
saved_path = credentials.save(Path("data/stream_credentials.json"))
```

This step needs cloud access. The later LAN application can run separately,
without a cloud account or environment configuration:

```python
from quii_helper import AutonomousConfig, Camera, CameraStreamCredentials

saved = CameraStreamCredentials.load("data/stream_credentials.json")
camera = Camera(
    config=AutonomousConfig(
        device_host="192.0.2.10",
        device_id=saved.device_id,
        stream_key=saved.stream_key,
        auth_code=saved.auth_code,
        channel=1,
        stream=2,
    )
)
with camera.serve_rtsp(port=8554) as session:
    session.wait()
```

Use the correct camera IP/channel/stream for the device identified by
`saved.device_id`; the file does not discover the camera's current address.
`AutonomousConfig` defaults to LAN and reads neither process values nor `.env`.
To use `.env` for the local IP/channel/stream instead, use `config=load_config()`
and explicitly pass `connection_mode="lan"` and the loaded key/auth fields.
The same LAN Camera can call `snapshot()` or `save_video(15)` instead of
`serve_rtsp()`. JPEG/MP4 needs FFmpeg; RTSP does not.

In a checkout, `python -m examples.cloud_key_rtsp` performs the mixed first-run
flow. For later starts, `python -m examples.lan_rtsp` loads the saved JSON and
forces LAN mode, honoring the configured camera IP/channel/stream. The usual
`examples.serve_rtsp` / `snapshot` / `save_video` scripts instead read the
key/auth pair from configuration, not this file. None implicitly searches for
a saved file or fetches a missing key.

On the tested Tantos/Pi, a fresh cloud fetch returned the same key/encoded-auth
pair as the older cache, and independent LAN sessions worked without cloud
requests. The original saved key still worked after 55 h 13 m in a later
capture check. A Vimar K40955 owner also confirmed saved-key LAN RTSP; the same
key lifetime has not been measured on that device. These are observations,
not an immutability/rotation guarantee. Maximum key lifetime, reboot persistence
and the effect of fetching another key on existing sessions are unknown.
A load/playback failure must not cause an automatic cloud login. Call the
bootstrap API again only explicitly.
LAN-only applies to this client; the camera's own WAN access was not blocked
in these tests. See [Validation Scope](../COMPATIBILITY.md#validation-scope).

**Storage:** JSON is plaintext, not encryption or a credential vault. No cloud
password, session id, dynamic password or raw response is written. New files
have Unix owner-only permissions (`0600`); Windows uses the containing folder's
ACL, which the application owner must restrict. Keep files in an ignored private
directory, do not share them or serialize the fields into diagnostics. The
standard `stream_credentials.json` name is also ignored by this repository.
Missing/unreadable files raise `OSError`; invalid schema/values/size raise
`ConfigurationError`. A failed save does not replace the previous file.

### Incoming Call History (Experimental)

```python
from quii_helper import Camera, load_config

camera = Camera(config=load_config(), connection_mode="cloud")
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
| `get_stream_key_info()` | `CameraDeviceStreamKeyInfo` | Firmware-dependent local `get.device.streamkey` response; not a guaranteed alternative to cloud bootstrap. Potentially sensitive. |

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
| `password_mode` | `"auto"`; cached capability or, in explicit cloud mode only, a read-only cloud metadata lookup. Explicit `"plain"` / `"sha256"` skips that lookup. |
| `port`, `scheme` | `80`, `"http"`; local CGI address, not native port `34567`. |
| `auth_code` | `None`; use the camera's CGI authentication code. |
| `verify_tls` | `None`; follow camera configuration for HTTPS CGI. |
| `debug` | `False`; request redacted DEBUG exchange logging. |

**The following example sends a real opening command:**

```python
from quii_helper import Camera, load_config

camera = Camera(config=load_config(), connection_mode="cloud")
result = camera.open_door(lock_number=1, password_mode="auto")
print(result.accepted, result.error, result.message)
```

`accepted=True` requires an explicit numeric `<error>0</error>` response.
It means the device acknowledged the command, not that the door physically
moved. Error descriptions are command-specific.

Unknown capability in `auto` mode raises `ConfigurationError` **before** an
opening command. The example permits the cloud capability query deliberately;
it does not start a preview. A default LAN-only Camera never performs that
lookup and needs known capability or a verified explicit password mode.
Choose an explicit mode only after verifying the device's
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
| `AudioDeviceError` | Explicit computer conversation could not initialize or maintain microphone/speaker I/O; no automatic retry. |
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
| `python -m examples.cloud_key_rtsp` | Explicit cloud login/key fetch, save/reload `data/stream_credentials.json`, then serve LAN-only RTSP. Each run contacts cloud first. |
| `python -m examples.lan_rtsp` | Load `data/stream_credentials.json` and serve LAN-only RTSP; never fetch or renew a key, even if cloud settings are present. |
| `python -m examples.listen_audio` | Experimental: inspect ten encoded LAN audio frames using the saved credentials; metadata only, no playback or talkback. |
| `python -m examples.talk` | Unreleased active talk: start preview of `CAMERA_CHANNEL`, then send user-provided `data/talk.wav` through generic talk 65535. Not read-only; no microphone or door command. |
| `python -m examples.converse` | Unreleased shared-preview RTSP plus explicit PC conversation. Enter starts/stops talk; video continues afterwards. Requires saved LAN credentials and the `audio` extra; `--list-devices` only enumerates names. |
| `python -m examples.open_door` | Print capability 24 and send a **real opening command** in auto mode. |

The installed entry point `python -m quii_helper.main` also serves RTSP until
`Ctrl+C`, without opening a door. It honors `CAMERA_CHANNEL` and `CAMERA_STREAM`,
including named quality profiles, and no longer forces `live_newcn=True`.
It still forces **`tls_verify=False`**, overriding `.env` for that option,
but does not select cloud mode or load a saved JSON automatically.
For saved-file LAN starts use `examples.lan_rtsp`; for environment-supplied
keys and configured TLS policy use `examples.serve_rtsp`. The main entry point's
TLS override is unrelated to native LAN TCP, which does not use HTTPS.
