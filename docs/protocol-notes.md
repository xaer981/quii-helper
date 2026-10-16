# Protocol Notes

This project is based on observed behavior of the original Android client and native libraries.

## Connection Flow

The high-level preview flow is:

1. Fetch runtime credentials from the cloud.
2. Ask the cloud for P2P/LAN candidates.
3. Probe candidate peers.
4. Establish the RBUDP tunnel.
5. Send QUII setup/play commands.
6. Collect media packets.
7. Decode H.264 frames and optionally render JPEG/MP4/RTSP output.

## Media Capture

The camera sends H.264 NAL units wrapped inside QUII/RBUDP payloads.

The capture pipeline:

- Filters filler/control packets.
- Reassembles fragmented payloads.
- Extracts media frames.
- Tracks SPS/PPS/IDR context.
- Writes raw H.264 and/or MP4 output depending on the requested operation.

If a video duration is correct but the image contains repeated or corrupted frames, the likely issue is packet ordering, missing fragments, or incomplete H.264 reference frames rather than MP4 container duration.

## RTSP Streaming

The RTSP server is local-only infrastructure around the decoded camera frames.

It does not ask the camera to enable a native RTSP mode. Instead, it:

- Opens the normal QUII preview stream.
- Receives camera H.264 frames.
- Serves those frames to RTSP clients.

## Local Device APIs

Many read-only device methods use local HTTP/CGI-style endpoints.

Compatibility depends on device firmware. Some commands return `error=-1` even though the same package works for preview capture. This usually means the specific command is unsupported or requires a different firmware/app command variant.

### Door Opening

`Camera.open_door()` uses local XML `set.device.opendoor` with `door`,
`locknumber`, and the opening `password` directly inside `body/content`.
The header uses `adminapp2`, encoded `AUTH_CODE`, and `passwordencode=1`.
This matches `DeviceRequestHelp.deviceUnlock`, `DeviceUnlockContent`, and the
LAN branch of `DeviceRequestHelp.initHeader` in the decompiled Java client.
Password selection follows `QvDeviceApi.deviceUnlock`: capability 24
(`TYPE_ENCRYPY_SHA256`) enables `EncodeDevicePassword`; a clear bit keeps the
body password unchanged. `QvDevice.getQvDeviceAbility` sources the bitmap from
Base64 `transparent_basedata`. `QvDeviceAbility.initData` skips two header bytes;
`getSupportStatus(24)` then reads bit 0 of payload byte 3 (decoded byte 5).
`CameraDeviceInfo.supports_sha256_password` exposes this as a tri-state flag.

`password_mode="auto"` uses cached device metadata/runtime credentials first,
then a read-only cloud metadata lookup when needed. Explicit `"plain"` and
`"sha256"` modes skip discovery. The `sha256` mode preserves the vendor's
already-encoded-password rule, matching the existing entrance-bot integration.
Unlike the original client's default-false bitmap for missing/invalid data,
unknown capability in auto mode raises before sending and requires an explicit
mode. This avoids silently choosing a wire format when the flag is unavailable.

Command result meanings follow `QvOpenComHelper.dealWithUnlockResult`, rather
than generic CGI error meanings. Both passwords are redacted from DEBUG logs.
Missing or invalid acknowledgement codes are treated as an unknown outcome.
Commands are never retried or redirected automatically, and success does not
prove physical movement of the door. Cloud IoT unlock is not implemented.
Live door opening with `Camera.open_door(password_mode="auto")` was confirmed
by the user on **Tantos Marilyn Wi-Fi s** on **2026-10-16**. Capability 24 was
`True`, selecting the vendor-encoded password format; the device returned
`error=0`, and the user confirmed that the door physically opened. This verifies
the automatic encoded-password path on this device, not the plain-password path
or other firmware variants.

## Package Layout

Important package areas:

| Path | Purpose |
| --- | --- |
| `quii_helper/camera/` | Public camera API and high-level orchestration. |
| `quii_helper/cloud/` | Cloud authentication and runtime credential APIs. |
| `quii_helper/device/` | Local device APIs, response models, and explicit control commands. |
| `quii_helper/protocols/` | RBUDP/QUII protocol implementation. |
| `quii_helper/media/` | Media decoding, frame extraction, and rendering. |
| `quii_helper/streaming/` | RTSP streaming implementation. |
| `quii_helper/config/` | Settings and `.env` loading. |
| `quii_helper/support/` | Shared support utilities such as error-code descriptions. |
