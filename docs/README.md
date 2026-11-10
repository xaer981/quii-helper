# Documentation

[Project Overview](../README.md) | [Setup](setup.md) | [API](api.md) |
[Compatibility](../COMPATIBILITY.md) | [Contributing](../CONTRIBUTING.md)

## Start Here

Start with [Setup](setup.md) and choose the inputs for your operation.
For LAN media without a saved key, first complete the
[10 required cloud settings and save a key](setup.md#first-run-fetch-and-save).
Already have that key file? Skip cloud setup and use the
[local settings and saved-file example](setup.md#later-runs-load-and-view-locally).
Only need call history? Use the separate [cloud history setup](setup.md#cloud-call-history);
no stream key is needed.
Want to observe new pictures/videos without cloud access? Use
[local archive observation](setup.md#local-archive-observations) with a LAN
host and local auth code. This reports archive additions, not confirmed calls.
LAN-only is the default; cloud operations require explicit opt-in. Use the
[API Reference](api.md) for individual methods.

| Your goal | Guide |
| --- | --- |
| First installation | [Install from PyPI](setup.md#using-an-installed-package) and [choose operation prerequisites](setup.md#what-your-operation-needs). |
| Configure an existing application | [Environment settings](setup.md#environment-settings) and [library configuration](api.md#library-configuration). |
| Capture an image or video | [Capture methods](api.md#capture-methods). |
| Obtain a stream key, then play locally | [First-run bootstrap and later local starts](setup.md#stream-key-bootstrap-and-local-reuse), [persistence API](api.md#stream-key-bootstrap-and-persistence). |
| Watch a live stream in VLC | [RTSP streaming](api.md#rtsp-streaming). |
| Inspect received audio frames | [Experimental receive-only LAN audio](api.md#receive-only-audio-experimental); available since 0.3.0, tested on Tantos. |
| Send sound to an intercom | [Experimental LAN talk](api.md#lan-talk-experimental); available since 0.4.0. Shared-preview speech/reply was confirmed on Tantos panel 2 with a file-backed adapter; see [hardware coverage](../COMPATIBILITY.md#tantos-lan-talk-speech-and-reply). |
| Watch and talk from a computer | [Computer conversation](api.md#computer-conversation-experimental); available since 0.4.0, `session.start_talk()` / `stop_talk()` share the RTSP preview. Optional audio extra, microphone and headphones. |
| Download an archived picture or video | [Archive queries and downloads](api.md#archive-queries); Tantos video image/sound confirmed. Intelbras archive JPEG is community verified with `pipelined`, available since 0.4.1; see [device reports](../COMPATIBILITY.md#intelbras-allo-wt7-community-reports). |
| Read device information | [Cloud methods](api.md#cloud-read-only-methods) or [local methods](api.md#local-device-read-only-methods). |
| Read or poll incoming-call history | [Setup and examples](setup.md#cloud-call-history), [API and limits](api.md#incoming-call-history-experimental); cloud-based, not a live subscription. |
| Watch local archive additions | [Local archive observations](api.md#local-archive-observations); pictures/videos, dependent on recording settings, not confirmed calls. |
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
