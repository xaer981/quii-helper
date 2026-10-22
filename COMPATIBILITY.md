# Compatibility

[Project Overview](README.md) | [Setup](docs/setup.md) | [API Reference](docs/api.md)

QUII Helper targets the QUII / Qualvision protocol family used by **vHome 2.2**
cameras and video intercoms. Support for one device does not establish support
for every product sharing the protocol or app name.

## Known Working Devices

| Device | App | User-confirmed features |
| --- | --- | --- |
| Tantos Marilyn Wi-Fi s | vHome 2.2 | JPEG snapshot, MP4 capture, RTSP, physical door opening in `auto` mode, and incoming-call history on the tested account/backend. |

Door opening was confirmed on 2026-10-16 with capability 24 enabled and
`error=0`. This verifies the encoded-password path, not the plain-password path
or all firmware. Call-history reads and observation of a new call were
confirmed on 2026-10-19/20. Those checks establish neither a delivery-time
guarantee nor delivery with Android fully disconnected.

## Discovery Hints

Related devices may expose:

- HTTP header `Server: Qualvision -HTTPServer`.
- Native TCP port `34567`.
- Integration with the vHome 2.2 mobile app.

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

The extracted P2P asset must have the verified vHome 2.2 **arm64-v8a** layout
on every host. It is read as data, not executed. Other ABIs/builds require
explicit native verification. JPEG/MP4 additionally needs FFmpeg on `PATH`;
RTSP and local CGI do not.

## Validation Scope

| Check | Evidence | Does not establish |
| --- | --- | --- |
| Windows/Linux CI | Offline tests and isolated wheel/sdist installation on Python 3.10/3.11. | Live camera/cloud compatibility. |
| RTSP release soak | Two-minute synthetic loopback test of sending, backpressure, shutdown, and retained Python allocations. | Real UDP delivery, camera quality, codec correctness, ARM64 behavior, or process RSS bounds. |
| Linux ARM64 under QEMU, 2026-10-20 | Installation and `pip check` in two entrance-bot Python 3.11 images; 11 mocked integration tests per image. | Native-speed performance or live media. |
| Physical Raspberry Pi ARM64, 2026-10-21 | Earlier local wheel in entrance-bot; 140 isolated tests with fake door openers and networking disabled. | A fresh installation of every later PyPI release or live ARM64 preview/RTSP. |
| PyPI consumer check, 2026-10-22 | Published `0.1.0rc6` with entrance-bot commit `40680ee`: 140 tests in a fresh Windows Python 3.11 environment, `pip check`, no private settings/non-loopback access. | Deployment, physical door behavior, or ARM64 installation of that artifact. |
| Published `0.1.0`, 2026-10-22 | Fresh Windows Python 3.11 wheel/sdist installs and default pip resolution; dependency/import/configuration/logging smoke checks. | A new live-device test. |

The ARM64 integration uses the library as a dependency; it is not a claim of
tested ARM64 media capture. Installing this package does not update or deploy
entrance-bot. Older validation artifacts are evidence, not replacement uploads
for an already published version.

## Reporting A Device

Use the [Device compatibility issue form](https://github.com/xaer981/quii-helper/issues/new?template=device_compatibility.yml).
Include the model, firmware, app version, platform, discovery hints, and which
operations you actually tested. Read-only failures can be firmware-specific;
include the command and error, not only whether preview works.

Do not open a door just to complete a compatibility checklist. Only report
physical control if it was explicitly authorized and observed. Redact logs,
device ids, network addresses, credentials, and private media before sharing.
See [Setup](docs/setup.md#troubleshooting) and [Security](SECURITY.md).
