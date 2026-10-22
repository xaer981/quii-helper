# Changelog

All notable changes will be documented in this file.

This project follows a pre-`1.0` release model while the public API is still
being stabilized.

## Unreleased

## 0.1.0-rc.6 - Unreleased

- Normalize expected paths in installed-package smoke checks, so Windows
  short-path aliases do not cause false installation failures. Runtime path
  handling is unchanged; a noncanonical-working-directory regression covers it.
- Keep RTSP `wait()` responsive to `Ctrl+C` on Windows, with or without a
  timeout, so context-manager cleanup can run without losing a live producer.
- Accept short (1-31 byte) continuations of active QUII media before applying
  the new-header length check. Preserve independent-stream prefixes and chained
  remainders; verified against the native player through GhidraMCP.
- Finalize the same AES context used for encryption/decryption. Malformed full
  blocks now fail instead of silently truncating; valid partial command bodies
  and metadata remain buffered. Valid wire bytes and public APIs are unchanged.
- Add a unified, non-publishing release gate with frozen public-source/archive
  hashes, complete tests of isolated wheel/sdist installs, a 2-minute synthetic
  RTSP backpressure/lifecycle soak and an aggregate required CI result. Dirty
  or shortened local runs cannot be mistaken for release-candidate approval;
  live camera and consumer checks remain an explicit owner-run step.
- Preserve dotted output stems throughout capture/rendering, so numbered
  destinations such as `clip.1.mp4` and `clip.2.mp4` cannot collapse onto
  `clip.mp4`. Automatic name reservation uses the same literal-base rule.
- Bound upper QUII pending assembly across both collectors (32 stream keys /
  32 MiB) and reject invalid or over-20-MiB declared media bodies before body
  decoding. Decode errors fail clearly rather than retaining corrupt prefixes.
  Valid incomplete/chained packets still assemble normally.
- Propagate camera-originated KCP disconnect requests for connected lanes to
  capture/RTSP consumers. Unknown IDs and response flags remain ignored; a
  matched disconnect aborts the session without automatic reconnect. Parsing
  and request matching were checked against native through GhidraMCP.
- Separated RBUDP transport occupancy from incomplete KCP frames. Contiguous
  bytes are drained before ACK generation, so frames larger than 64 KiB no
  longer close the receive window while waiting for their own remaining bytes.
- Reject unknown/zero local connection IDs before allocating receive state,
  acknowledging or delivering data. Each registered lane owns one stream;
  changing the peer word cannot create extra buffers or reset its sequence.
- Dispatch complete KCP frames incrementally before validating the next header.
  Invalid headers/lengths now fail the receiver explicitly instead of silently
  discarding a valid prefix and continuing with already acknowledged bytes.
  The three receive-path fixes were checked against native code through GhidraMCP
  and offline regression tests; no new live camera check was performed.
- Removed unbounded retention of full wrapped-frame HEX strings for debugging.
  Disabled RBUDP diagnostics do no fingerprint/HEX work; enabled deduplication
  keeps only 128 recent SHA-256 fingerprints.
- Matched native 64 KiB RBUDP receive-window admission, including uint32
  wraparound. Reordering caches also have host-side packet/byte limits with
  explicit overflow errors. ACK layout and window formula are unchanged;
  occupancy now refers only to the drained transport buffer, not KCP data.
- Isolated ordinary cloud cookies per camera/credential-fetch flow, preserving
  login-to-token/device-list continuity without a process-global cookie jar.
  Alarm userauth and alarm-service cookies remain separate.
- Always release the tunnel socket even if legacy fragment emission or worker
  joining fails; failed emission no longer retains the partial-fragment map.
- Updated README/API RTSP examples to call `session.wait()` and stop with
  `Ctrl+C`, so producer errors are visible instead of hidden behind `input()`.
- Isolated RTSP client sending from the camera producer with bounded queues,
  per-access-unit deadlines and slow-client disconnection. Closing a client
  interrupts blocked sends and cannot resurrect UDP sockets during SETUP.
- Bounded pending RBUDP application payloads to 4096 packets / 32 MiB. Receiver
  failures and consumer overload now wake readers with `QuiiConnectionError`,
  allowing RTSP to stop its listener instead of hanging without media. Intentional
  closure/timeouts remain non-fatal; wire commands and ACKs are unchanged.
- Validate the verified vHome 2.2 arm64-v8a ELF/table profile before UST key
  derivation. Native table offsets/content were checked through Ghidra; wrong
  ABI/build or truncated assets now fail clearly instead of deriving bad keys.
- Documented installed-wheel setup separately from source-only examples,
  updated Windows/Linux CI coverage, and added FFmpeg prerequisites plus an
  actionable missing-executable error for JPEG/MP4 rendering.
- Fixed premature termination of chained QUII parsing, including remainders
  after fragmented media. Capture stop requests now apply after all complete
  packets in the received buffer are processed; short tails remain buffered.
  Verified against `CQUIIStreamBase::OnRecv` in the original native player.
- RTSP streaming no longer retains decoded payloads indefinitely. Recent frame
  metadata is bounded to 128 entries while lifetime counters remain accurate.
- Clean up UDP/tunnel resources after failed preview startup. RTSP shutdown
  cancels subsequent startup stages, retains a still-stopping worker, rejects
  overlapping restarts, and closes the listener after producer failure.
- RTSP now handles fragmented requests, request bodies and interleaved RTCP;
  rejects malformed/oversized headers, bodies and transport values; expires
  incomplete messages and caps concurrent clients at 32.
- **Default change:** RTSP binds to `127.0.0.1`, not every interface. LAN use
  requires an explicit host; the server still has no authentication or TLS.
- Standalone examples now honor configured TLS verification instead of silently
  disabling it. An installation requiring the vendor TLS workaround must
  explicitly opt out with `TLS_VERIFY=false`. The repository's editable
  `main.py` retains an explicit `tls_verify=False` for the owner's tested setup;
  the library and examples verify TLS by default.
- Retain and report raw H.264 when any requested render fails, validate finite
  capture durations, and reserve automatic output names atomically. Ignore
  virtual environments, private `.env.*` variants and build artifacts in Git.

- Prepared package version `0.1.0rc6`; no tag or publication is implied by this
  version change. Replaced legacy license metadata with the SPDX `MIT`
  expression and an explicit license file, using setuptools 77.0.3 or newer.
- Expanded CI to Windows/Linux on Python 3.10/3.11. Build wheel from sdist,
  validate metadata and archive contents, then install both distributions in
  fresh Windows/Linux environments without camera or cloud access.
- Added manual, tag-only PyPI publishing after the same CI gates, using
  a protected `pypi` environment and Trusted Publishing instead of API tokens.
  GitHub environment protection and the PyPI publisher must be configured
  separately before the first upload.

- Completed source distributions with documentation, examples, tests, and the
  empty environment template while excluding private assets and runtime data.
  README documentation links are absolute so they also work on package indexes.
- Kept the optional unlock password empty in `.env.example` and clarified its
  inline comment to avoid a multiline secret-scanner false positive.
- Hid authentication material and raw runtime credentials from dataclass
  `repr` output without changing their fields or values. The call-history
  example's offline test now mocks settings/logging as well as the camera,
  so it cannot read the developer's local `.env`.
- Removed unused external `kcp` and direct `cffi` requirements. The internal
  RBUDP implementation is unchanged; cryptography owns its transitive native
  dependencies. This avoids an unnecessary source build on Linux ARM64.
- Library configuration migration: `Camera()` now reads process environment
  values only; use `Camera(config=load_config())` to opt into `.env`. A plain
  `AutonomousConfig` no longer reads environment values. Explicit file loading
  does not mutate `os.environ` or share cached settings between cameras.
- Added per-camera `assets_dir` and `auth_version`; TLS paths and UST table
  loading follow application configuration rather than the installed package.
  Output paths honor explicit destinations and default to the application's
  working-directory `data/`, rather than a package-installation directory.
- Importing the library no longer loads settings or replaces Loguru sinks.
  Library messages are disabled until explicitly enabled. The optional console
  helper preserves application sinks unless `replace_existing=True` is passed.
  Standalone entry points/examples explicitly opt into file loading and logging.
- Added offline regression tests for isolated configuration, runtime paths,
  installed-library import behavior, and an entrance-bot-style async unlock
  adapter. No live commands are sent by these checks.
- Added a separate tokenless alarm `client-login` before journal queries to
  address native `ALARM_RESULT_SESSION_ERROR` (`1012`). It uses a stable reader
  identity and isolated cookies, without push credentials, notification changes,
  existing-client logout, or retries. The login may create a server-side client
  record/session. The user confirmed successful history reads on the tested
  installation; this is not a push subscription or a guarantee for other
  accounts/firmware.
- Corrected the cloud journal URL to use the discovered address + `UserAlarm`,
  without adding the separate discovery `uri`, matching the original client.
- Aligned cloud XML HTTP transport with OkHttp: advertise only gzip and decode
  compressed responses before XML parsing. Invalid responses now report HTTP
  metadata without dumping private bodies; decoded debug XML redacts alarm
  sessions and media-resource URLs.
- Improved call-history discovery errors to report response/service status
  codes without exposing private service URLs.
- Fixed call-history discovery rejecting `query_result=1` despite a successful
  envelope and a returned service address. The original Java client checks
  service type and address availability; per-service and envelope results must
  not be interpreted as the same error code.
- Added experimental read-only `Camera.get_call_events()` cloud journal access,
  typed call/page models, native event-19 filtering, pagination, and time bounds.
  No push registration, read acknowledgements, media sessions, or door commands
  are issued. After the initial discovery/login fixes, the user confirmed
  history records and observed a new call during the entrance-bot polling
  check. Android-independent delivery and a bounded arrival latency are not
  established by those checks.
- Added `python -m examples.call_events`, protocol parity tests, and documentation
  distinguishing journal history from a live call subscription.
- The library is installed as a local wheel in entrance-bot on a physical
  Raspberry Pi ARM64. Its isolated integration suite passed 140 tests on
  2026-10-21, including the local door adapter and HTTP handlers with fake
  openers. These tests do not verify live preview/media capture on ARM64 or
  send a real door command.

## 0.1.0-rc.5 - 2026-10-16

- Restored RTSP serving in `python -m quii_helper.main`. Moved the real
  door-opening check to the explicit `python -m examples.open_door` example.
- Added regression checks for RTSP context cleanup, absence of door commands
  from the normal entry point, and explicit execution of the door example.
- Updated README and API documentation with the separate entry points.

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
- Included Dependabot PR #2 (`cryptography==50.0.0`) and raised the package's
  minimum version to `50.0.0` so both installation paths avoid older affected
  versions. The upstream update drops wheels for 32-bit Windows and Intel macOS.

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
