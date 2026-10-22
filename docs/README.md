# Documentation

[Project Overview](../README.md) | [Setup](setup.md) | [API](api.md) |
[Compatibility](../COMPATIBILITY.md) | [Contributing](../CONTRIBUTING.md)

## Start Here

| Your goal | Guide |
| --- | --- |
| First installation | [Install the package](setup.md#using-an-installed-package), then [prepare assets](setup.md#required-assets). |
| Configure an existing application | [Environment settings](setup.md#environment-settings) and [library configuration](api.md#library-configuration). |
| Capture an image or video | [Capture methods](api.md#capture-methods). |
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

Documentation follows the current source tree. For a pinned package version,
use the files at its matching Git tag, such as
[`v0.1.1`](https://github.com/xaer981/quii-helper/tree/v0.1.1).
Published PyPI descriptions are snapshots of the README at build time, not
live copies of GitHub `main`.
Version `0.1.1` includes the corrected guides. Runtime behavior and public APIs
are unchanged from `0.1.0`; older descriptions may still mention the preceding RC.
