# Changelog

All notable changes will be documented in this file.

This project follows a pre-`1.0` release model while the public API is still
being stabilized.

## Unreleased

### Added

- Accept named quality profiles in `CAMERA_STREAM`: `high` / `main` / `1`
  resolves to stream 1 and `low` / `sub` / `2` to stream 2. Positive numeric
  ids and the legacy `QUII_STREAM` variable remain supported; the default
  stays stream 2. The standalone main no longer forces high quality, so
  channel/profile settings are honored consistently by the media examples.
- Experimental receive-only `Camera.listen_audio()` for saved-key LAN preview,
  returning encoded `CameraAudioFrame` payloads and per-frame codec, sample
  rate, channels and raw device-local timestamp metadata. It owns a closeable
  synchronous session, has no cloud fallback, and starts no microphone,
  speaker, talk session or file writer. MP4 remains video-only.
- `examples.listen_audio` inspects ten frames without playback or commands.
  Tantos/Pi read-only reception verified 298 G.711 A-law frames at 8000 Hz mono
  in 15 seconds. Vimar audio remains unverified.
- Opt-in `Camera.serve_rtsp(audio=True)` shares one preview/CFrame producer for
  H.264 and G.711 audio, with independent per-track TCP/UDP transports and
  bounded shared viewer queues. Native device timestamps provide the A/V
  timeline; late A/V viewers wait for a keyframe and receive SPS/PPS in SDP.
  FFprobe/FFmpeg A/V decoding was checked on Tantos/Pi. RTSP remains video-only
  by default; the source `quii_helper.main` opts into audio. No talkback or
  guaranteed cross-player lip-sync is introduced.

### Fixed

- Reject unsupported LAN live-play options before camera/RTSP startup instead
  of silently ignoring them. LAN requires `live_play_payload="path"`,
  `live_inner=False`, and `live_newcn=False`; cloud handling is unchanged.
  Remove the ineffective `live_newcn=True` override from the standalone main.
- Normalize RTSP paths, including root and trailing-slash paths, and return
  a `Content-Base` using the client's request authority so relative SDP track
  URLs resolve correctly for both local and remote viewers.
- Stop announcing speculative `RTP-Info` sequence/timestamp values in live
  PLAY responses: keyframe gating and concurrent publication do not guarantee
  that those values describe the first packet actually delivered.
- Encode the selected LAN TCP channel and zero-based stream in the binary
  live-play header, matching native `ParseURL`/`OnSendPlay`. Previously only
  the URL changed while the header always selected channel 1 / stream 1.
- Reject LAN selectors outside the header's 16-bit channel / 8-bit stream
  index range instead of silently truncating them.
- Interpret E3 CPacket audio fields as frequency/channel count instead of
  reporting them as video dimensions/FPS. Preserve video parsing behavior.

### Documentation And Validation

- Extend the installed-wheel RTSP soak and CI to test video-only and combined
  A/V for two minutes each, checking separate track sequences/audio timestamps,
  slow-client eviction, bounded queues and worker cleanup.
- Add the first community-confirmed device beyond Tantos: Vimar K40955,
  firmware `V401R001B002`, with vEye Pro 1.9.4.0.2. The owner confirmed
  saved-key LAN RTSP in [issue #5](https://github.com/xaer981/quii-helper/issues/5#issuecomment-6397243080)
  on 2026-10-25; other features and strict cloud TLS remain unverified.
- Record a Tantos/Pi recheck using the original saved key after 55 h 13 m,
  without client-side cloud requests or renewal. A 10-second capture yielded
  141 H.264 frames decoded without FFmpeg errors. This is not a maximum-lifetime,
  reboot-persistence or camera-WAN-isolation guarantee.
- Align README, setup, API and protocol notes with these evidence boundaries.
  Include vHome and vEye Pro in package search keywords and the compatibility
  issue form.

## 0.2.0 - 2026-10-23

### Changed

- **Breaking:** `Camera` defaults to LAN-only playback. Supply the camera IP
  and a saved stream key/auth pair for snapshots, recording and RTSP. No cloud
  login, automatic key renewal or P2P fallback occurs in this mode.
- To retain the `0.1.x` cloud/P2P behavior, explicitly pass
  `connection_mode="cloud"` or set `CAMERA_CONNECTION_MODE=cloud`. Cloud
  metadata/history methods and key bootstrap also require this opt-in.
- Local CGI methods still work without a stream key. Door `password_mode="auto"`
  cannot look up an unknown capability through cloud in LAN mode; select cloud
  mode for that lookup or a verified explicit password mode.
- LAN recording uses the camera's FPS, without stretching sparse frames to the
  collection window. Recording payload is limited to 256 MiB with explicit
  failure; RTSP does not retain a recording buffer.

### Added

- Direct TCP media transport for the native-checked AES-256/SHA256 profile
  without separate media encryption. Preserve partial reads across timeouts,
  validate packet lengths/digests and reject unsupported profiles explicitly.
- `STREAM_KEY` and `CAMERA_STREAM_PORT` settings; LAN playback needs no cloud
  account or extracted APK assets when credentials are supplied.
- Explicit cloud-only `Camera.fetch_stream_credentials()` and public
  `CameraStreamCredentials.save()` / `load()`. Atomically persist only device id,
  stream key and matching auth code, never cloud passwords or sessions. Secret
  fields are hidden from representations and redacted from diagnostics.
- `examples.cloud_key_rtsp` for cloud fetch/save followed by LAN RTSP, and
  `examples.lan_rtsp` for later saved-file starts without cloud requests.
- Offline regressions for LAN policy, synthetic TCP media, credential storage,
  cancellation, failure propagation and documentation examples.

### Fixed

- Direct TCP play now uses native seconds timestamps and default play flags.
- LAN capture/RTSP suppresses frames before the first keyframe and releases
  startup/receive sockets on shutdown. Existing RBUDP behavior and runtime
  dependencies are unchanged.

### Documentation And Validation

- Simplify the PyPI quick start: obtain/save a key explicitly, then reuse it
  locally. Align setup, API, security and compatibility guides with that flow.
- Separate the complete first-run cloud configuration (all 10 mandatory
  settings) from saved-key LAN starts. Add offline checks for both documented
  configurations and make bootstrap an explicit, non-recurring application step.
- Physical Raspberry Pi checks on Tantos Marilyn Wi-Fi s verified saved-key
  capture/RTSP, cloud bootstrap/save/load, and independent LAN reconnect without
  client cloud requests. A cached key worked after more than two hours; saved
  media decoded without FFmpeg errors. The cloud probe used an explicitly
  authorized temporary TLS bypass; no settings were changed or door commands sent.
- Key lifetime, reboot/rotation persistence, camera-WAN isolation and Vimar
  compatibility remain unverified. This work relates to
  [issue #5](https://github.com/xaer981/quii-helper/issues/5) without
  claiming fully cloud-free key acquisition or support for that device.

## 0.1.1 - 2026-10-23

- Rework README and setup around PyPI installation and a first application;
  separate cloud/preview, LAN inspection, and explicit door-control inputs.
- Align the API reference with all current public Camera methods, arguments,
  result types, capture timing, and firmware/transport error semantics.
- Consolidate compatibility evidence, contributor/release instructions, and
  safety notes. Restore the README GIF through a verified historical URL.
- Add offline documentation regressions for API tables, snippet syntax,
  environment coverage, and repository links/anchors.
- Update Black to `26.10.1` consistently in development requirements and
  pre-commit for GHSA-cg8m-r9f2-5wm2. The affected bundled GitHub Action is not
  used by this repository; CI invokes the formatter CLI directly.
- Include the revised README in the PyPI package description and keep current
  installation instructions independent of a specific release number.
- Runtime behavior, public APIs, protocols, and runtime dependencies are
  unchanged from `0.1.0`.

## 0.1.0 - 2026-10-22

- Published the first final release as `0.1.0` on PyPI and `v0.1.0` on GitHub.
  The library runtime and public API are unchanged from `0.1.0rc6`.
- Validated entrance-bot commit `40680ee` with the published PyPI `0.1.0rc6`
  package in a fresh Windows Python 3.11 environment: dependencies are
  compatible and all 140 integration tests pass using synthetic settings,
  loopback-only networking and fake door openers. The consumer repository and
  deployed services are unchanged.
- Retained pre-release normalization coverage in final-release tag checks.
- Verified published wheel/sdist installation and unpinned pip resolution in
  clean Windows Python 3.11 environments, including dependency and library
  isolation smoke checks. This is offline validation, not a live-device retest.

## 0.1.0-rc.6 - 2026-10-22

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

- Published package version `0.1.0rc6` on PyPI with GitHub pre-release tag
  `v0.1.0-rc.6`. Replaced legacy license metadata with the SPDX `MIT`
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
