# Documentation

[Project Overview](../README.md) | [Setup](setup.md) | [Archive CLI](archive-cli.md) | [API](api.md) |
[Compatibility](../COMPATIBILITY.md) | [Contributing](../CONTRIBUTING.md)

## Start Here

Start with [installation](setup.md#using-an-installed-package), then choose
your task below. LAN-only is the default; cloud operations require explicit opt-in.

### Setup And Live Media

| Your goal | Guide |
| --- | --- |
| Configure an existing application | [Environment settings](setup.md#environment-settings) and [library configuration](api.md#library-configuration). |
| Check LAN settings without connecting | [Offline `doctor` command](setup.md#offline-lan-check). |
| Capture an image or video | [Capture methods](api.md#capture-methods). |
| Get a key for LAN media | [Cloud setup and bootstrap](setup.md#first-run-fetch-and-save). Skip this step if you already have a saved key/auth pair. |
| Watch a live stream in VLC | [LAN settings and saved-file example](setup.md#later-runs-load-and-view-locally) or [Python RTSP API](api.md#rtsp-streaming). |
| Inspect audio frames or send PCM | [Receive-only audio](api.md#receive-only-audio-experimental) and [LAN talk](api.md#lan-talk-experimental). |
| Watch and talk from a computer | [Computer conversation](api.md#computer-conversation-experimental). Uses the same preview plus the optional audio extra, microphone and headphones. |

### Archive And Events

| Your goal | Guide |
| --- | --- |
| List or download saved files from a terminal | [Archive CLI](archive-cli.md): choose a JPEG/MP4 by number or use a JSON list in scripts. |
| Download an archived picture or video from Python | [Archive API and protocol variants](api.md#archive-queries). See [device coverage](../COMPATIBILITY.md) for tested formats and firmware. |
| Read incoming-call history | [Cloud history setup](setup.md#cloud-call-history). No stream key needed; not a live subscription. |
| Watch local archive additions | [Local archive observation](setup.md#local-archive-observations). Requires a LAN host and CGI auth; additions are not confirmed calls. |

### Device And Integration

| Your goal | Guide |
| --- | --- |
| Read device information | [Cloud methods](api.md#cloud-read-only-methods) or [local methods](api.md#local-device-read-only-methods). |
| Open a connected door | [Door control](api.md#door-control); these calls have physical effects. |
| Diagnose a failure | [Troubleshooting](setup.md#troubleshooting) and [error handling](api.md#error-codes). |

## Event Examples

Choose the source before configuring an example. All three are read-only and
send no door command; the cloud examples do perform vendor authentication.
Run these from a configured checkout or extracted source distribution:

| Command | Source and result | Setup |
| --- | --- | --- |
| `python -m examples.call_events` | One cloud incoming-call history page via `get_cloud_call_events()`. | [Cloud account/app settings and assets](setup.md#cloud-call-history). |
| `python -m examples.watch_call_events` | Poll cloud history every five seconds for three minutes, after a baseline. | Same cloud setup; each poll can create an alarm reader session. |
| `python -m examples.watch_archive_events` | Observe new local archive pictures/videos with `watch_archive_events()`. | [LAN host and recording settings](setup.md#local-archive-observations); reuse `data/stream_credentials.json` from the LAN RTSP example. |

The library methods also work in an installed package; `examples` themselves
are not installed by the wheel. See [API usage and limitations](api.md).

## For Contributors

- [Contributing](../CONTRIBUTING.md): development environment and offline checks.
- [Protocol Notes](protocol-notes.md): native parity evidence and implementation limits.
- [Release Checklist](../RELEASE_CHECKLIST.md): validation and protected publication.
- [Changelog](../CHANGELOG.md): released changes and migration notes.
- [Security Policy](../SECURITY.md): sensitive material and vulnerability reporting.

For a pinned package version, use the documentation at its matching Git tag.
