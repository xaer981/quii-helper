# Compatibility

This project targets QUII/Qualvision-based cameras and video intercoms used by
the `vHome 2.2` mobile application.

## Discovery Hints

Devices in this family may expose:

- HTTP header: `Server: Qualvision -HTTPServer`
- Open TCP port: `34567`
- Mobile app integration: `vHome 2.2`

These hints are not a guarantee that a device is supported. They are useful
signals for finding compatible firmware families and for search visibility.

## Python Platforms

CI validates Windows x86_64 and Linux x86_64 with Python 3.10 and 3.11,
including clean wheel/sdist installation. These are offline checks, not
camera/cloud interoperability tests. Raspberry Pi ARM64 has separate mocked
entrance-bot integration coverage, not live media/RTSP validation; see
[Setup](docs/setup.md#installing-on-linux-arm64).

The extracted P2P asset must use the verified vHome 2.2 `arm64-v8a` layout on
every host platform. It is read as data, not executed. Other ABIs/builds are
rejected unless their ELF/table profile is supported explicitly. JPEG/MP4
output additionally requires a separate FFmpeg installation on `PATH`.

The package requires `cryptography>=50.0.0`. Since version 49, upstream no
longer provides wheels for 32-bit Windows or Intel (`x86_64`) macOS. Do not
assume this release installs on those platforms; see the
[upstream compatibility changes](https://cryptography.io/en/latest/changelog/#v49-0-0).

## Known Working Devices

| Device | App | Discovery hints | Status | Notes |
| --- | --- | --- | --- | --- |
| Tantos Marilyn Wi-Fi s | vHome 2.2 | `Qualvision -HTTPServer`, TCP `34567` | Working | Snapshot, MP4 capture, RTSP serving, and door opening with `password_mode="auto"` tested. |

## Compatibility Checklist

Before reporting a new device, check:

- The original mobile app can connect to the camera.
- The device is visible in the cloud account used by `.env`.
- Required APK assets are present in `assets/`.
- `.env` contains app-specific values extracted from the same app version.
- `LOG_LEVEL=debug` has been used for a failed diagnostic run.
- Logs are redacted before sharing publicly.

## Reporting A Device

Use the GitHub `Device compatibility` issue template and include:

- Device model and firmware version, if visible.
- Mobile app name and version.
- Whether `Server: Qualvision -HTTPServer` is returned by the device.
- Whether TCP port `34567` is open.
- Which operations work: snapshot, video capture, RTSP.
- Redacted debug logs for failures.
