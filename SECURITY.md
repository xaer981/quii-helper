# Security Policy

[Project Overview](README.md) | [Setup](docs/setup.md) | [Contributing](CONTRIBUTING.md)

## Supported Versions

`0.1.0` is the first published final release. Security fixes target the latest
`0.2.x` release; older versions do not receive separate backports.
The API remains pre-`1.0`, with experimental features and compatibility limits
documented explicitly. See the [Changelog](CHANGELOG.md).

## Sensitive Material

Users supply credentials and APK assets from software/devices they are
authorized to use. Never share real `.env` files, asset contents, extracted
certificates/private keys/native libraries, account tokens, raw traffic, or
camera media in issues, pull requests, fixtures, or release archives.
Saved stream-credential JSON is also sensitive: it holds a reusable key/auth
pair in plaintext, not an encrypted vault. Keep it in a private ignored
directory (`0600` on Unix; restrict the containing Windows folder ACL).

Git ignores `.env` variants, `assets/*`, `data/*`, and generated media/logs.
The empty `.env.example` and `.gitkeep` files are intentional exceptions.
Ignore rules do not remove material already committed; review history with
a scanner and rotate affected credentials after an exposure.

## Runtime Boundaries

- RTSP has no authentication or TLS. Its default listener is loopback-only;
  restrict any explicit LAN listener and never expose it publicly.
- LAN-only is the default: no cloud login, automatic
  key renewal or P2P fallback. Bootstrap is a separate explicit cloud operation.
  This policy does not block the camera's own WAN traffic or establish a key TTL.
- TLS verification is enabled by default in the library and examples. An
  explicit bypass weakens authenticity; the current `quii_helper.main` entry
  point contains such an override. See [TLS guidance](docs/setup.md#cloud-region-and-auth-url).
- Door commands have physical effects. An acknowledged command is not proof
  of movement; a timeout may leave an unknown outcome. Do not retry blindly.
- Cloud history is not a live subscription or a sufficient access-control
  signal by itself. Authentication, freshness/deduplication, and authorization
  policy belong to the embedding application.
- Validate caller-supplied output paths; explicit paths can leave `data_dir`.
- Native-asset fingerprints check a supported layout, not APK trustworthiness.

## Reporting Vulnerabilities

Do not publish exploit details, secrets, account data, or private camera
material in a public issue. Use the repository's
[Security tab](https://github.com/xaer981/quii-helper/security) to submit a
private report if a **Report a vulnerability** option is available.

If no private channel is available, open an issue **only to request a
private security contact**, without reproduction steps, affected credentials,
or technical vulnerability details. Wait for a private channel before sending
the report. This is a reporting limitation, not an invitation to disclose
sensitive details publicly.
