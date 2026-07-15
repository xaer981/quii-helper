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

## Package Layout

Important package areas:

| Path | Purpose |
| --- | --- |
| `quii_helper/camera/` | Public camera API and high-level orchestration. |
| `quii_helper/cloud/` | Cloud authentication and runtime credential APIs. |
| `quii_helper/device/` | Local device read-only APIs and response models. |
| `quii_helper/protocols/` | RBUDP/QUII protocol implementation. |
| `quii_helper/media/` | Media decoding, frame extraction, and rendering. |
| `quii_helper/streaming/` | RTSP streaming implementation. |
| `quii_helper/config/` | Settings and `.env` loading. |
| `quii_helper/support/` | Shared support utilities such as error-code descriptions. |
