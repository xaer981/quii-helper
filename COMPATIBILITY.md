# Compatibility

[Project Overview](README.md) | [Setup](docs/setup.md) | [API Reference](docs/api.md)

QUII Helper targets the QUII / Qualvision protocol family used by cameras and
video intercoms with apps such as **vHome 2.2** and **vEye Pro**. Support for one
device does not establish support for every product sharing the protocol or
app name. Maintainer tests and community reports are distinguished below.

## Known Working Devices

| Device | App | Confirmed features and evidence |
| --- | --- | --- |
| Tantos Marilyn Wi-Fi s | vHome 2.2 | Maintainer media tests and user-confirmed door/call checks: JPEG snapshot, MP4 capture, RTSP, physical door opening in `auto` mode, and incoming-call history on the tested account/backend. |
| Vimar K40955, firmware `V401R001B002` | vEye Pro 1.9.4.0.2 | Saved-key LAN RTSP through `lan_rtsp`, [reported by luigi-pi on 2026-10-25](https://github.com/xaer981/quii-helper/issues/5#issuecomment-6397243080). Not independently tested by the maintainer. |

Physical Pi checks with Tantos on 2026-10-23 also verified direct LAN capture,
saved-key RTSP, cloud bootstrap/save/load, and independent LAN reconnect without
client cloud requests. These tests did not send a door command.

An unreleased source-checkout check on 2026-10-26 verified corrected LAN TCP
selector headers on Tantos/Pi. Channel 1 showed an outdoor view and channel 2
an indoor corridor. Stream 1 produced 960x576 and 1888x1080 respectively;
streams 2 and 3 both produced 640x480 on each channel. Six 15-second MP4
samples with AAC audio decoded without FFmpeg errors. Matching dimensions do
not establish whether streams 2 and 3 are separate encoder profiles or aliases.
The same saved key was reused without cloud requests; services and device
settings were unchanged. These channel/profile results do not apply to Vimar
without a separate test, and do not verify simultaneous two-panel playback.

On Tantos, door opening was confirmed on 2026-10-16 with capability 24 enabled
and `error=0`. This verifies the encoded-password path, not the plain-password path
or all firmware. Call-history reads and observation of a new call were
confirmed on 2026-10-19/20. Those checks establish neither a delivery-time
guarantee nor delivery with Android fully disconnected.

### Vimar K40955: Community Report

The report confirms LAN video with a saved cloud key/auth pair, not every
Camera API. JPEG/MP4 capture, door control, cloud call history, two-way audio,
reboot persistence, and playback with the intercom's WAN blocked remain
unverified on this model. Two-way audio and local-only call detection are not
implemented by this library.

The unreleased `Camera.listen_audio()` API and `serve_rtsp(audio=True)` were
tested on Tantos via a Raspberry Pi on 2026-10-26. A 15-second receive probe
collected 298 G.711 A-law frames, 8000 Hz mono, decoded in memory. FFprobe
identified H.264 960x576 and `pcm_alaw` audio in the combined RTSP stream;
FFmpeg decoded both tracks over TCP and UDP to a null output without errors
after startup/timing fixes. Both operations used saved credentials; the combined stream had one
preview connection, not separate audio/video connections. No cloud request,
door command, microphone transmission, recording, or service reconfiguration
was performed. Vimar audio, subjective sound quality, and precise lip-sync
remain unverified. These receive/RTSP probes did not exercise the new native
MP4 audio writer; earlier AAC samples were recorded externally through FFmpeg.
This is not two-way audio.

A separate candidate-wheel MP4 check on Tantos/Pi on 2026-10-26 used a new
private Python 3.11 ARM64 venv and the host's FFmpeg. Both panels with `high`
and `low` profiles produced H.264 + AAC 8000 Hz mono files, decoded without
errors. Audio/video track durations matched: 3.20, 2.25, 3.70 and 3.15 seconds
from four six-second collection windows. Keyframe/startup delay remains part
of that window; no video stretching was introduced. Legacy LAN live flags
warned without aborting the two low-profile captures. Each capture used one
saved-key TCP session with cloud/HTTP and door calls blocked; no service or
device settings changed. Temporary audio was removed after muxing. Subjective
sound quality, exact lip-sync and cloud/Vimar MP4 audio remain unverified.

Local `get.device.streamkey` has not succeeded in the reported Vimar tests or
our Tantos investigation; this does not establish a firmware-level ban.
Initial key acquisition still uses cloud. The reporter's cloud TLS workaround
disabled hostname checking, so strict-TLS cloud success is not established.
See [TLS troubleshooting](docs/setup.md#cloud-region-and-auth-url); do not
treat a CA file or disabled verification as proof of server identity.

## Discovery Hints

Related devices may expose:

- HTTP header `Server: Qualvision -HTTPServer`.
- Native TCP port `34567`.
- Integration with mobile apps such as vHome 2.2 or vEye Pro.

These are search/discovery hints, not compatibility or authentication checks.
Local CGI uses HTTP port `80` by default; do not substitute native port `34567`.

## Python Platforms

The package declares Python **3.10 or newer**. CI exercises Windows x86_64 and
Linux x86_64 on Python **3.10 and 3.11**, including wheel/sdist installation.
Other Python/platform combinations are not covered by that matrix.

`cryptography>=50.0.0` is a runtime dependency. Upstream version 49 removed
wheels for 32-bit Windows and Intel (`x86_64`) macOS; do not assume a binary
installation works there. See the
[upstream compatibility changes](https://cryptography.io/en/latest/changelog/#v49-0-0).

For cloud/P2P preview, the extracted asset must have the verified vHome 2.2 **arm64-v8a** layout
on every host. It is read as data, not executed. Other ABIs/builds require
explicit native verification. JPEG/MP4 additionally needs FFmpeg on `PATH`;
RTSP and local CGI do not.

Direct LAN TCP playback uses supplied IP/auth code/stream key and
does not require that asset. Only the AES-256/SHA256 profile without separate
media encryption is implemented. Both isolated probes and the current Camera
integration have physical Pi validation, in addition to offline loopback tests.
The Tantos key has been reused after more than 55 hours, but maximum key
lifetime, reboot persistence, and playback with the camera's WAN blocked are
not established. The same lifetime has not been verified on Vimar.

## Validation Scope

| Check | Evidence | Does not establish |
| --- | --- | --- |
| Windows/Linux CI | Offline tests and isolated wheel/sdist installation on Python 3.10/3.11. | Live camera/cloud compatibility. |
| RTSP release soak | Two-minute synthetic loopback test of sending, backpressure, shutdown, and retained Python allocations. | Real UDP delivery, camera quality, codec correctness, ARM64 behavior, or process RSS bounds. |
| Linux ARM64 under QEMU, 2026-10-20 | Installation and `pip check` in two entrance-bot Python 3.11 images; 11 mocked integration tests per image. | Native-speed performance or live media. |
| Physical Raspberry Pi ARM64, 2026-10-21 | Earlier local wheel in entrance-bot; 140 isolated tests with fake door openers and networking disabled. | A fresh installation of every later PyPI release or live ARM64 preview/RTSP. |
| PyPI consumer check, 2026-10-22 | Published `0.1.0rc6` with entrance-bot commit `40680ee`: 140 tests in a fresh Windows Python 3.11 environment, `pip check`, no private settings/non-loopback access. | Deployment, physical door behavior, or ARM64 installation of that artifact. |
| Published `0.1.0`, 2026-10-22 | Fresh Windows Python 3.11 wheel/sdist installs and default pip resolution; dependency/import/configuration/logging smoke checks. | A new live-device test. |
| LAN API on physical Raspberry Pi ARM64, 2026-10-23 | Isolated local wheel: saved-key capture/RTSP, cloud bootstrap/save/load, then independent LAN reconnect. Four samples decoded at 960x576 / 20 fps without errors; RTP checks found no sequence gaps and contexts closed. | Visual scene quality, long-run soak, maximum key lifetime, reboot/rotation persistence, camera-WAN isolation, LAN JPEG rendering on this device, or other hardware. |
| Tantos saved-key recheck on physical Pi, 2026-10-25 | The original saved key still worked after 55 h 13 m without renewal. A 10-second LAN TCP capture yielded 141 H.264 frames at 960x576 / 20 fps; FFmpeg decoded them without errors. The process guard allowed only camera TCP and blocked cloud/HTTP and external DNS. | An indefinite key lifetime, reboot/rotation persistence, camera-WAN isolation, or Vimar key lifetime. |
| Vimar K40955 community report, 2026-10-25 | The owner confirmed `lan_rtsp` video in [issue #5](https://github.com/xaer981/quii-helper/issues/5#issuecomment-6397243080), after troubleshooting cloud bootstrap. | Independent maintainer testing, strict cloud TLS validation, JPEG/MP4, door control, call history, two-way audio, or other firmware. |

The earlier entrance-bot checks cover dependency integration, not media.
The separate physical LAN tests cover that tested build/device only; they do not
certify every PyPI build on ARM64. The test process blocked cloud requests
during LAN phases, but the camera's own WAN access remained unchanged.
Installing this package does not update or deploy entrance-bot. Older artifacts
are evidence, not replacement uploads for an already published version.

During the 2026-10-23 Tantos check, a fresh cloud fetch returned the same
key/encoded-auth pair as the 2 h 32 m cache. The later 55-hour recheck reused
the original saved file read-only, without fetching a key or loading cloud
settings. These observations are lower bounds, not an expiry guarantee.
Cloud TLS verification was temporarily disabled with explicit authorization
only for the earlier cloud probe because the vendor chain failed; strict-TLS
cloud success is not claimed. No production service, device setting or door
state was changed.

## Reporting A Device

Use the [Device compatibility issue form](https://github.com/xaer981/quii-helper/issues/new?template=device_compatibility.yml).
Include the model, firmware, app version, platform, discovery hints, and which
operations you actually tested. Read-only failures can be firmware-specific;
include the command and error, not only whether preview works.

Do not open a door just to complete a compatibility checklist. Only report
physical control if it was explicitly authorized and observed. Redact logs,
device ids, network addresses, credentials, and private media before sharing.
See [Setup](docs/setup.md#troubleshooting) and [Security](SECURITY.md).
