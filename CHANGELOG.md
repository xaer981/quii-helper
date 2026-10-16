# Changelog

All notable changes will be documented in this file.

This project follows a pre-`1.0` release model while the public API is still
being stabilized.

## Unreleased

## 0.1.0-rc.4 - 2026-10-16

- Added explicit LAN `Camera.open_door()` control, `UNLOCK_PASSWORD`
  configuration, typed acknowledgements, and native unlock error descriptions.
  Commands are never retried or redirected automatically.
- Select the unlock body password format from native capability 24, with
  explicit `plain`/`sha256` modes when discovery is unavailable. Unknown
  capabilities never trigger an opening command in automatic mode.
- User-confirmed physical door opening in `auto` mode on Tantos Marilyn Wi-Fi s
  (2026-10-16), with capability 24 enabled and device result `error=0`.
- Updated the manual `quii_helper.main` check to print capability 24 and send
  one real door-opening command in `auto` mode.
- Corrected public API examples and aligned package metadata with the release.
- Included the dependency-group update merged after `v0.1.0-rc.3`.

## Earlier Pre-Releases

- Narrowed the root package API to stable user-facing entrypoints.
- Added typed capture and packet summary models.
- Split RTSP server internals into smaller modules.
- Added explicit environment settings loading.
- Added explicit TLS verification configuration and debug-log redaction.
- Added initial packaging and quality-tooling configuration.
- Added pre-release CI smoke checks and RTSP usage documentation.
- Added Gitleaks configuration and CI secret scanning.
- Pinned development tool versions used by CI.
- Added compatibility notes, runnable examples, and GitHub issue/PR templates.
- Expanded `.env` extraction documentation and added cloud discovery helper.
