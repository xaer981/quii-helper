# Documentation

[Project Overview](../README.md) | [Setup](setup.md) | [API](api.md) |
[Compatibility](../COMPATIBILITY.md) | [Contributing](../CONTRIBUTING.md)

## Start Here

Start with [Setup](setup.md). On the first run, complete the
[10 required cloud settings and save a key](setup.md#first-run-fetch-and-save).
Already have that key file? Skip cloud setup and use the
[local settings and saved-file example](setup.md#later-runs-load-and-view-locally).
LAN-only is the default; cloud operations require explicit opt-in. Use the
[API Reference](api.md) for individual methods.

| Your goal | Guide |
| --- | --- |
| First installation | [Install from PyPI](setup.md#using-an-installed-package) and [choose operation prerequisites](setup.md#what-your-operation-needs). |
| Configure an existing application | [Environment settings](setup.md#environment-settings) and [library configuration](api.md#library-configuration). |
| Capture an image or video | [Capture methods](api.md#capture-methods). |
| Obtain a stream key, then play locally | [First-run bootstrap and later local starts](setup.md#stream-key-bootstrap-and-local-reuse), [persistence API](api.md#stream-key-bootstrap-and-persistence). |
| Watch a live stream in VLC | [RTSP streaming](api.md#rtsp-streaming). |
| Read device information | [Cloud methods](api.md#cloud-read-only-methods) or [local methods](api.md#local-device-read-only-methods). |
| Read incoming-call history | [Incoming call history](api.md#incoming-call-history-experimental); this is not a live subscription. |
| Open a connected door | [Door control](api.md#door-control); these calls have physical effects. |
| Diagnose a failure | [Troubleshooting](setup.md#troubleshooting) and [error handling](api.md#error-codes). |

## For Contributors

- [Contributing](../CONTRIBUTING.md): development environment and offline checks.
- [Protocol Notes](protocol-notes.md): native parity evidence and implementation limits.
- [Release Checklist](../RELEASE_CHECKLIST.md): validation and protected publication.
- [Changelog](../CHANGELOG.md): released changes and migration notes.
- [Security Policy](../SECURITY.md): sensitive material and vulnerability reporting.

For a pinned package version, use the documentation at its matching Git tag.
