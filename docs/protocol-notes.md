# Protocol Notes

[Documentation](README.md) | [API Reference](api.md) | [Contributing](../CONTRIBUTING.md)

These are implementation/parity notes for contributors, not the first-run
guide. Start with [Setup](setup.md) to use the library. Native addresses and
findings below refer to the inspected app builds, not every vendor release.

## Contents

- [Connection flow](#connection-flow), [LAN TCP](#lan-tcp-session), [media](#media-capture), and [RTSP](#rtsp-streaming).
- [Runtime limits](#runtime-limits-and-lifecycle).
- [Receive-only audio](#receive-only-audio).
- [LAN talk](#lan-talk).
- [Cloud history](#cloud-incoming-call-history) and [local device APIs](#local-device-apis).
- [Receive parity](#receive-buffer-parity) and [failure/backpressure](#receiver-failure-and-backpressure).
- [Native asset validation](#native-crypto-asset-validation) and [package layout](#package-layout).

## Evidence Boundaries

Static native parity and synthetic regression fixtures do not prove live
camera/cloud behavior. Host-side admission/memory limits below are defensive
policy unless a native constant is explicitly identified. Live observations
and platform validation are summarized in [Compatibility](../COMPATIBILITY.md#validation-scope).

## Connection Flow

The cloud/P2P preview flow, explicitly selected with `connection_mode="cloud"`, is:

1. Fetch runtime credentials from the cloud.
2. Ask the cloud for P2P/LAN candidates.
3. Probe candidate peers.
4. Establish the RBUDP tunnel.
5. Send QUII setup/play commands.
6. Collect media packets.
7. Decode H.264 frames and optionally render JPEG/MP4/RTSP output.

### LAN TCP Session

LAN-only is the default configuration policy. The internal
`LanTcpSession` connects only to the supplied IP/TCP port, sends setup then
encrypted play, and yields normalized decoded messages to Camera capture/RTSP.
The existing cloud RBUDP pipeline is not used in this branch. There is no implicit
key acquisition, cache-file lookup, cloud login, service discovery or fallback.

The implementation was checked against `liblive_player.so` via GhidraMCP:

| Address | Native behavior used by LAN TCP |
| --- | --- |
| `00479814` | Setup status byte 9; command crypto mode byte 10. |
| `0047c0fc` | Live defaults: header flag word at 13 is 1; stream flag is 0. |
| `0047ccac`, `0047d898` | `ParseURL` reads `idc` and `ids - 1`; play header bytes 13-14 contain the channel as little-endian uint16, byte 16 contains the zero-based stream index. |
| `0047d898`, `007f0cc4` | Play timestamp is time_t in seconds; username/password/path body, SHA and separate header/body encryption. |
| `00479d98` | Command SHA covers header only, except type `0xfe` also covers its declared body. |
| `0047e198` | Play status byte 11; byte 12 equal to 1 marks active play. |
| `0047af70`, `0047b1ec` | Stateful media receive; 32-bit size at 11, encrypted command prefix at 9, media offset at 16. |
| `0047b1ec` | Suppress completed frames until the first `FrameIsKey()` packet. |
| `007dc394` | `CPacket::FrameGetFPS()` reads CPacket byte 15 divided by 4.0. LAN MP4 uses this rate, not the requested capture window. |
| `00479020` | Keepalive type 0, empty body, zero play flags, SHA and separate encryption. |
| `0047b914`, `0047b694` | Separate media encryption can use a third key; it must not be guessed from the command key. |

The TCP packet builder encodes channel/stream selectors from the live path in
the binary header as well as the body. Changing only `idc`/`ids` in the body
does not reproduce native selection. LAN configuration accepts channels
1-65535 and streams 1-256; rejecting larger values is host-side validation to
prevent truncation, not evidence that a camera has that many inputs/profiles.
Regression tests decrypt the actual outgoing play packet and check both the
selectors and SHA. Physical panel/profile availability remains device-specific.
On 2026-10-26 the corrected source build was checked on Tantos/Pi using channels
1/2 and streams 1/2/3, with the saved key and no cloud requests. The channels
showed distinct outdoor/indoor views; all six 15-second A/V samples decoded
without errors. Stream 1 resolutions differed by panel; streams 2 and 3 both
returned 640x480. This does not prove independent third-profile support or
simultaneous panel sessions. Earlier probes with the fixed channel-1/stream-1
header did not validate alternate selector values.

LAN sends the verified path-form play with `live_inner=False` and
`live_newcn=False`. Non-default values of these flags or `live_play_payload`
emit a standard Python warning and are ignored, preserving earlier callers.
This is a host-side compatibility policy, not evidence that firmware forbids the flags.
Native `ParseURL` (`0047ccac`) detects `inner=1`; `OnSendPlay` (`0047d898`)
copies that state to header byte 17. Its broader firmware meaning and that of
`newcn=1` remain unconfirmed. The cloud RBUDP handling is unchanged.

The initial supported profile is AES-256 command encryption, SHA256 and media
flag 15 equal to zero, matching the successful device probes. Other profiles
are rejected before media is delivered. A 5 MiB payload cap is host policy,
not a native protocol constant. Partial headers/bodies survive read timeouts;
invalid packets, rejected play, SHA failures and EOF close the session.
One receive timeout covers header and body together, preserving partial bytes.
LAN recording collects at most 256 MiB of combined video/audio payload and
fails explicitly on overflow; this is not a process RSS limit. RTSP retains only bounded assembler
state/history and the server's bounded per-viewer queues, not a recording buffer.
Existing video rendering/retiming remains unchanged. MP4 rendering additionally
collects supported G.711 from the same retained CFrame sequence and encodes AAC.
The first native audio/video timestamp pair provides the offset; subsequent
audio follows sample count to avoid device timestamp jitter. Initial silence
and end padding/trimming follow the produced video duration, not the requested
capture window. Unsupported audio warns and leaves video usable; the LAN 256 MiB
budget includes both payloads. No audio connection or new wire command is added.
Explicit
`Camera.fetch_stream_credentials()` reuses the existing cloud `login` +
`get-device-token` flow and maps `data_encode_key` / `auth_code` into the minimal
`CameraStreamCredentials` model. It introduces no new wire commands or
authentication encoding rules. JSON persistence contains only schema version,
device id and that key/auth pair, never the cloud session or dynamic password.
The application loads that file explicitly before constructing a LAN client;
no bootstrap, file lookup, fallback or renewal occurs inside LAN playback.
Implementation initially used native inspection and offline fixtures only.
An authorized physical Raspberry Pi check on 2026-10-23 then exercised the
candidate's real Camera API: capture and RTSP with a key aged 9167 seconds,
explicit cloud fetch/save/load followed by LAN RTSP, and a fresh saved-file
reconnect without cloud account settings or requests. The refreshed pair
matched the old stream key and native-encoded auth code. All four media samples
decoded without FFmpeg errors. The cloud probe alone used a temporarily
authorized TLS bypass; LAN TCP itself does not use HTTPS or APK assets.

During LAN phases, a process audit guard permitted only camera TCP and the
loopback RTSP client, rejecting cloud HTTP and external DNS. This proves the
observed client's behavior, not OS-level isolation or camera-WAN independence.
RTSP contexts stopped their workers and listeners. No production service or
device setting was changed. A LAN-only recheck on 2026-10-25 reused the original
key after 55 h 13 m and yielded 141 H.264 frames during a 10-second capture;
FFmpeg decoded them without errors. These reuse intervals are lower bounds,
not a TTL, rotation/reboot guarantee or visual-quality certification.

A Vimar K40955 owner confirmed saved-key LAN RTSP with firmware V401R001B002
and vEye Pro 1.9.4.0.2 in
[issue #5](https://github.com/xaer981/quii-helper/issues/5#issuecomment-6397243080).
This is a community report, not independent native/device validation by the
maintainer. It does not establish local key acquisition, other Camera APIs,
strict cloud TLS, two-way audio or local call-event support. See
[Compatibility](../COMPATIBILITY.md#validation-scope) for the exact scope.

## Media Capture

The camera sends H.264 NAL units wrapped inside QUII/RBUDP payloads.

The capture pipeline:

- Filters filler/control packets.
- Reassembles fragmented payloads.
- Extracts media frames.
- Tracks SPS/PPS/IDR context.
- Writes raw H.264 and/or MP4 output depending on the requested operation.

If a video duration is correct but the image contains repeated or corrupted frames, the likely issue is packet ordering, missing fragments, or incomplete H.264 reference frames rather than MP4 container duration.

## Receive-Only Audio

`Camera.listen_audio()` is an experimental LAN-only API, added in 0.3.0, over the
unchanged TCP preview handshake/play. It extracts E3 CPacket audio with the
existing CFrame assembler. It does not use a talk session, change audio
settings, request microphone transmission, or add audio to MP4. The raw
codec and payload are retained; no decoder or sample-rate assumption is used.

The following `liblive_player.so` functions were read via GhidraMCP on
2026-10-26, together with vHome's `AudioPlayerManager`/`QvPlayerCore` Java:

| Address | Receive-audio evidence |
| --- | --- |
| `0043986c`, `0078e5c8`, `0078b74c`, `00799adc` | `QVPanelListen` delegates to the player's decoder. |
| `00799ba8`, `00799dc0` | Start/stop listening creates/deletes a local `IQVAudioPlay` device; it does not issue a new remote play/talk command. |
| `007dc2fc` | `FrameGetCodec`: codec byte at offset `0x0e`. |
| `007dcf90` | `FrameGetChnNum`: channel-count byte at offset `0x0f`, not video FPS. |
| `007dcf48` | `FrameGetFreq`: little-endian sample rate at offset `0x10`, not video width. |
| `007dce28`, `007dcd20`, `007dc508` | Milliseconds at `0x0c`; the word at `0x08` is a packed device-local calendar, not Unix time. Native conversion uses local-time `mktime`. |
| `0043d128` | E3 audio generation; codec ids `4=G.711 A-law`, `5=G.711 mu-law`, `9=PCM`. This identifies payloads; it does not establish a device's negotiated codec. |
| `00548f38` | Decoder selection depends on each frame's codec/frequency/channels; do not fix the format globally. |

The shared parsers report zero video dimensions/FPS for audio and expose
`sample_rate`, `channels`, and `frame_ms` instead. Video interpretation and
capture/RTSP commands are unchanged. Unknown audio codec ids are preserved.
Existing TCP payload and CFrame size limits apply. There is no background
reader/history: only incomplete CFrame state and frames from the latest
decoded message are retained. A read deadline includes discarded video and
control traffic; timeout preserves partial data, while invalid metadata and
connection failure close the stream. This is not a lossless recorder.

Regression fixtures are synthetic native-layout packets plus encrypted
loopback TCP, not captured speech. An authorized read-only Pi probe on
2026-10-26 then received 298 Tantos E3 frames in 15 seconds: codec 4, 8000 Hz,
mono, 95360 payload bytes, no incomplete CFrame resets or malformed headers.
G.711 decoded in memory;
no audio file, cloud request, device setting or outgoing audio was involved.
Vimar audio and legacy non-CPacket audio formats remain unverified.

## LAN Talk

The experimental `Camera.talk()` owns two connections: `LanTcpSession` preview
of the selected panel for incoming audio, then a separate `LanTalkSession`
with selector 65535 for outgoing audio. Neither uses RBUDP. GhidraMCP
comparison on 2026-10-27 covered both original
arm64 binaries: vHome `liblive_player.so` (SHA-256
`22b2b4f14dc8d0886a2f35865876b1db30c3ab4d146ed0c7282d3b3fc4c11556`)
and vEye Pro 1.9.4.0.2 (SHA-256
`574573d0bcd7125fdfed5fd992d6de61219e90c3528167cb8bbb2174054aa61b`).

| Function | vHome | vEye Pro | Shared behavior |
| --- | --- | --- | --- |
| `ParseURL` | `0051b3d4` | `005151f8` | Generic channel 0 becomes 65535. |
| `SendSetup` | `0051b598` | `005153bc` | Plain 32-byte A9; byte 9 is 2 for talk. |
| `SendOpen` | `0051b6ac` | `005154d0` | Type 0B, channel at 13, byte 15 zero; `adminapp2&&password` followed by empty custom id, SHA256 over header/body. |
| `OnRecvOpen` / `GetCodecType` | `0051bd08` / `0051bc68` | `00515cac` / `00515c0c` | Status at 11, codec mask at 12; indices 0/1 map to native codec 4/5. Byte 14 selects compact vs full CPacket output. |
| `SendPlay` / `OnSendRequest` | `0051bf1c` / `0051bfa0` | `00515ec0` / `00515f44` | Send C1 then D1. Request channel at 11, enabled at 13; C includes codec selector at 14 and rate at 15. SHA256 covers the header only. |
| `OnRecvPlay` | `0051c444` | `005163e8` | Check C/D status; successful D, not C alone, establishes ready state. |
| `OnSendData` | `0051ca80` | `00516a24` | A2 header, independently encrypted first 32 body bytes, clear remainder, no media digest. Compact F0 uses tags 0E/0A for A-law/mu-law; full format preserves the E3 CPacket header. |
| `PackFrame` | `0047b1ec` | `0050fdac` | Decrypt a declared aligned prefix, then pass payload to CFramePack; this implementation supports media flag 15 equal to zero only. |
| `OnStop` | `0051b2bc` | `005150e0` | Stop the base transport and release queued packets. |
| JNI `audioToggleEx` | `0042be60` | `0043a220` | With talk-listen disabled, select `QVPlayerListen` and disable `QVTalkListen`; preview and talk are distinct receive sources. |

vEye adds optional client-id/uhid strings in Open when client-id is nonempty;
the no-client-id path matches vHome. This implementation uses that common
path, not vendor-specific HS/IP-device or GLNK fallback. In both Java builds,
`QvPlayerCore.buildTalkConnection()` defaults to `65535`, separately from the
preview panel. `AudioPlayerManager.startSendVoice` disables incoming talk
audio during half-duplex transmission and restores it afterwards; full-duplex
leaves it enabled. These toggles do not stop preview reads in our API.

The coordinator waits for the first supported preview audio frame before
opening talk, queueing that frame and preserving any partial CFrame. The
normal queue bound also applies during startup. A dedicated
preview worker then keeps draining video/audio while the talk worker handles
send pacing, control ACKs and keepalive. Talk-side media is consumed but never
mixed into the incoming preview queue. A missing-audio startup deadline or
failure in either worker closes both sockets and wakes both callers; startup
and thread-start failures release partially opened resources too.
The first-audio gate is host-side readiness policy matching the successful
Pi probe; native Java can preconnect talk once preview reaches state 4 and
does not itself require an E3 frame before that preconnection.

Codec policy is deliberately narrower than native: choose the supported
intersection (A-law first, then mu-law), not the SDK's preference for codec
8 when mask bit 4 is present. No supported bit means negotiation failure.
Outgoing PCM is fixed at 8000 Hz mono, 320 samples/40 ms per frame. Those
chunk sizes and the bounds below are implementation policy, not a claim that
every native codec/device uses them. G.711 has exhaustive PCM16 regression
vectors frozen from CPython 3.11.14 `audioop`, without a runtime dependency.

Each socket has one I/O owner; the preview worker never shares timeouts with
the sender. Partial TCP headers/bodies survive ordinary read timeouts. The
first-audio wait and talk handshake/toggle deadlines cannot be extended by
incoming video/control traffic. Startup bounds apply per stage, not as one
aggregate timeout. Host bounds are 16 early talk messages, 65555 bytes per
talk media message, 5 MiB per preview message/partial CFrame and completed
frame payload, 65535 bytes per audio frame, 64 queued audio frames and one
second of PCM per send call. The larger preview bound permits normal HD video
keyframes; video is discarded after reassembly. Slow audio readers drop the
oldest frames with an explicit counter. This is not lossless recording.
Unknown outcomes are never retried automatically.

Offline tests cover both codecs and outgoing layouts, malformed/NACK/SHA
replies, partial reads, deadlines, pacing, queue limits and shutdown, including
real two-connection loopback TCP. A preceding Pi probe on 2026-10-27 kept
panel-2 preview active (327 audio frames received) and sent 250 G.711 A-law
frames through generic talk 65535. The owner confirmed approximately ten
seconds of tones from that panel. Talk itself returned zero media frames.
Talk selector 2 without preview had ACKs but no audible sound. Preview and
selector were changed together, so their individual necessity is not proven.

The shared-preview coordinator was subsequently checked on physical Tantos/Pi
on 2026-10-29: the owner confirmed intelligible transmitted speech and its
recorded reply, and stopping talk left video running. The probe replaced the
desktop audio device with a clocked PCM file source/sink; it did not test a
physical PC microphone or headphones. Standalone API hardware coverage,
overlapping-speech quality and Vimar talk are not established; echo cancellation
is not implemented. See [hardware coverage](../COMPATIBILITY.md#tantos-lan-talk-speech-and-reply).

## RTSP Streaming

The RTSP server is local-only infrastructure around the decoded camera frames.

It does not ask the camera to enable a native RTSP mode. Instead, it:

- Opens the normal QUII preview stream.
- Receives camera H.264 frames.
- Serves those frames to RTSP clients.

The opt-in `audio=True` branch passes E3 audio from this **same CFrame packer**
to G.711 RTP; it never opens another preview or talk connection. RFC 3551
payload types are 8 (PCMA) and 0 (PCMU), at 8000 Hz mono. Every encoded octet
advances the RTP timestamp by one sample. Other formats fail closed instead of
being mislabeled. Audio/video have separate SSRCs, sequence spaces, SETUP
transports and TCP channels, but share a viewer's queue/byte/lag budget.

Native `CPacket::FrameGetTimeStamp` at `007dc508` was rechecked for the A/V
clock: unpack year/month/day/hour/minute/second and milliseconds, then use
device-relative video deltas at 90000 Hz. Audio starts on the same origin and
then advances at one tick per G.711 sample, not the camera's jittery per-frame
arrival/capture timestamps. No device timezone is inferred.
Video-only timing remains unchanged. SPS/PPS are cached with a 4096-byte cap
per NAL and exposed in SDP; A/V viewers are gated until a fresh keyframe.
RTCP sender reports and cross-player lip-sync guarantees are not implemented.

RTSP DESCRIBE supplies `Content-Base` with a trailing slash and the request's
authority, not the server's loopback fallback. SETUP matches canonical root,
nested and trailing-slash paths for both tracks. Live PLAY omits speculative
`RTP-Info`: skipped P-frames and concurrent publication mean that a snapshot of
the producer's next sequence number need not be the first packet delivered to
that viewer. This avoids false startup metadata without buffering a GOP or
delaying PLAY. No camera-side QUII command or timestamp layout changes here.

On the Pi, FFprobe identified both Tantos streams (H.264 960x576 and PCMA mono
8000 Hz); an eight-second FFmpeg A/V decode to null returned zero with no
decoder messages after the startup/clock fixes. Initial late-viewer trials
exposed missing PPS and arrival-time DTS problems; those were not counted as
successful validation. Remaining null-mux DTS rounding warnings were absent
when the validation encoder preserved the 90000 Hz video timebase; sampled RTP
DTS were strictly increasing. G.711 RTP timestamps use sample count to avoid
the native audio header's timing jitter. No RTSP daemon was deployed or
existing service changed.

## Runtime Limits And Lifecycle

These limits are host-side safety policy, not a claim to reproduce native
queue capacities or bound total process RSS:

| Layer | Limit | On failure/overload |
| --- | --- | --- |
| RTSP listener | 32 clients; 16 KiB headers, 64 KiB bodies; incomplete-request timeout 10 seconds. | Reject/close the affected client. |
| Per-viewer output | 32 pending access units, 4 MiB including in-flight RTP bytes; two-second access-unit deadline. | Disconnect the viewer without blocking the camera producer. |
| RBUDP application payload queue | 4096 packets / 32 MiB. | Fail the session with `QuiiConnectionError`, not silent packet loss. |
| RBUDP receive/reordering | Native 64 KiB start-sequence window; extra cache guard 4096 packets / 128 KiB. | Cumulative ACK outside the window; explicit failure on safety-limit overflow. |
| KCP packet assembly | 20 MiB packet limit; transport bytes drain separately. | Reject malformed/oversized packets; retain valid incomplete input. |
| Upper QUII assembly | 32 logical stream keys / 32 MiB pending payload, including incoming input; positive media body up to 20 MiB. | Abort and release pending buffers. |
| Diagnostics | At most 128 recent wrapped-frame fingerprints and bounded streaming metadata. | No retained full-frame history; disabled diagnostics skip fingerprint/HEX work. |

An unexpected terminal receiver/decoder failure clears pending application
payloads and aborts capture. A valid prefix does not promise a usable partial
recording. RTSP closes the listener and reports producer failure through
`session.wait()`; it does not reconnect the camera automatically.

Shutdown requests producer cancellation and releases sockets/listeners. A
cloud/connection call already in flight still has its own timeout; later
startup stages are skipped. Restart is rejected while that producer is stopping.
Timeouts and intentional closure are not unexpected receiver failures.

The native parity evidence for receive windows, assembly, and disconnects is
recorded below. The public usage/lifecycle contract is in the
[API reference](api.md#rtsp-streaming).

## Cloud Incoming-Call History

The read-only journal path is based on the original Java classes
`AlarmRequestHelper`, `AlarmListQueryReqContent`, `AlarmListFilter`,
`AlarmListQueryResp`, and `QvAlarmCore.queryAlarmInfo`. The native service-name
table includes `alarmapp`; the HTTP interface posts to `UserAlarm`.

GhidraMCP inspection of `libqv-p2p-v2.so` confirmed separate `url`, `uri`, and
`param` fields in `DevClientMst::ParseServer` (`0x0046e3c0`) and their transfer
to Java in `getServiceInfo` (`0x0036e51c`). Java
`QvP2PClientV2.getQvServiceInfo` uses `getAddress() + "/"` for the HTTPS base,
without `uri`; `AlarmApi.queryAlarmList` then posts to relative `UserAlarm`.
The journal endpoint must therefore not reuse the P2P-style `url + uri` route.

Journal HTTP is handled by Java OkHttp, not by the media-player `.so`.
The APK's `okhttp3.internal.http.BridgeInterceptor.intercept` advertises `gzip`
and transparently decompresses the response. The Python transport now follows
that negotiation rather than advertising unsupported deflate/Brotli and passing
compressed bytes to the XML parser. Invalid XML errors include HTTP status,
content type/encoding, and byte count, not the response body. These corrections
are covered offline. The exact body behind the earlier parse failure was not
captured; later user-confirmed history reads supersede the initial local
discovery timeout as evidence that the complete flow works on the tested
installation.

`QvLocationManager.lambda$queryTargetService$0` checks the returned service type
and `QvServerInfo.haveAddress()` (non-empty HTTPS address). A user-reported
discovery response had envelope `result=0`, `alarmapp/query-result=1`, and an
address; the per-service value `1` must not be rejected as an envelope error.
The helper accepts `query_result` values `0` and `1` with a valid address and
still rejects failed envelopes, unsupported service status values, and absent
or invalid addresses. Discovery and the separate journal-login step below are
both needed before history can be queried.

- Command: `client-query-recordlist`; header: `flag=tdkcloud`, `seq=0`, and the
  userauth session id as text.
- Content: `maxid`, `pageno`, `pagelinenum`, and nested `filter/devid/id`,
  `filter/event/type`, `filter/peroid/start` and `end`. The spelling `peroid`
  is intentional.
- Response: `header/result`, `content/maxid`, `content/totoalcnt`,
  `content/unreadcnt`, and `content/record/data`. `totoalcnt` is also intentional.
- `QvPushInfo` defines incoming call as `19` and call received as `20`.
- `MainMessageListPresenter` starts at page `0`, max id `"0"`; it increments
  the page and reuses the server's max id when loading more history.

The user's journal response with ordinary userauth alone returned `1012`, which
`SDKStatus` defines as `ALARM_RESULT_SESSION_ERROR`. The original
`QvAlarmCore.checkLogin` performs `client-login` before querying history.
`AlarmRequestHelper.getLoginReq` supplies client id/type/OEM/app/language and
account id plus the auth-server hostname. `AlarmLoginReqContent.Client.token`
is optional; HS/LT compatibility credentials are optional too.

With explicit authorization, the helper now performs that login with a dedicated
stable reader UUID derived from its client id and account id. It omits token,
HS, and LT fields. `tokentype=0` is the SDK's default Getui enum, **not** a
"push disabled" flag; the request is tokenless because `<token>` is absent.
The login may create a reader-client record/session on the server. It never
copies the Android push token, logs out another client, or sends notification
settings commands.

Java keeps a separate alarm CookieJar. The helper likewise shares a private
cookie jar between alarm login and query, without copying the ordinary auth
Cookie header. Ordinary userauth cookies belong to each camera connector (or
one standalone credential-fetch flow), never a process-global jar. Login,
device-token and device-list calls within that session share cookies, while
different cameras and alarm readers remain isolated. Both XML headers retain
the userauth session id: the original
`QvAlarmCore` login callback does not replace it with an alarm response session.
Rejected logins stop before the history request, without logout/retry fallbacks.
Offline tests cover this sequence and cookie isolation. On 2026-10-19, the
user returned 15 live history records after the tokenless-login fix, confirming
backend acceptance on that installation. On 2026-10-20, a read-only entrance-bot
polling check observed a new incoming-call record. The manual marker followed
observation, so no precise ring-to-record latency can be inferred. Neither
check establishes Android-independent delivery or compatibility with other
accounts, application versions, or firmware. Earlier discovery timeouts are
historical failures, not the latest validation result.

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
then a read-only cloud metadata lookup when needed **only in explicit cloud
mode**. Default LAN mode rejects unknown capability before sending. Explicit `"plain"` and
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

## Receive Buffer Parity

On 2026-10-21, GhidraMCP inspection of the AArch64 `liblive_player.so` verified
`CQUIIStreamBase::OnRecv(fd_set*)` at `004793fc`. The native loop advances by each
successfully consumed packet, continues while buffered bytes remain, and stops
without flushing an incomplete header/body. `CQVString::Flush` removes only the
consumed prefix. The helper now follows this rule for chained QUII packets and
fragmented-media remainders: snapshot/capture thresholds do not discard data
already received. Offline regression tests cover the threshold boundary and
short tails. This is static native parity, not a new live camera validation;
encryption, wire commands and RBUDP acknowledgements were not changed.

## Receiver Failure And Backpressure

GhidraMCP inspection on 2026-10-21 confirmed disconnect propagation in
`liblive_player.so`: `IQUIIChannel::OnDisconnect` (`00481d80`) calls stream
callbacks; `IQUIIDevice::OnDisconnect` (`004846dc`) propagates to channels.
In `libqv-p2p-v2.so`, `DevConnectTcp::OnDisConnect` (`00449b54`) reports `-1`,
and `CTDKSsl::RecvData` (`0054ff8c`) distinguishes retryable reads from fatal
EOF/errors. Native UDP `Server::RecvingLoop` (`0050fa30`) polls and drains
received messages; it does not establish a rule that every UDP error is fatal.

The Python receiver already exited on unexpected `OSError`. It now propagates
that terminal outcome through the application payload queue, preserving the
cause. Timeouts remain retryable and intentional socket closure is not reported
as a failure. Queue overflow also becomes an explicit terminal error rather
than dropping data needed for H.264 reference frames. RTSP clients have isolated
bounded queues and lagging viewers are disconnected. These memory/latency limits
are host-side policy, **not** a claim to reproduce native queue capacities.
RBUDP wire bytes, sequence numbers, ACKs, crypto derivation and camera commands
were not changed in this pass. Validation is offline, not live camera proof.

### Reordering Window And Memory Bounds

Further inspection on 2026-10-21 explicitly targeted AArch64 `libqv-p2p-v2.so`:

- `TDK_F_RB_UDP_PR_CreateLogicConnData` (`005b16f8`) initializes the receive
  window at connection offset `0x58` to `0x10000` bytes.
- `TDK_F_RB_UDP_PR_DoRecvData_CONN_STATE_ESTABLISHED` (`005b1f28`) admits packet
  start sequences in `[next, next + window)`, including uint32 wraparound.
  Outside-window/replayed packets receive a cumulative ACK but are not cached.
- `TDK_F_RB_UDP_PR_AddRecvDataToRecvCacheList` (`005b3230`) deduplicates cached
  starts; `TDK_F_RB_UDP_PR_DoRecvCacheDataList` (`005b33f8`) drains contiguous data.
- `TDK_F_RB_UDP_SP_SendLogicProPacket` (`005b5218`) derives its advertised window
  from the contiguous **transport** buffer length at connection offset `0x6c`,
  **not** from the out-of-order cache or the incomplete KCP packet size.
- `TDK_F_RB_UDP_RecvData` (`005b0590`) removes bytes from that transport buffer.
  `RbUdpConn::OnRbRecv` (`00535738`) drains it into separate upper-layer messages,
  independently of whether `KcpLinkClient::DoRecvData` (`004a17c4`) has a complete
  packet. That parser calls `DoSinglePacketData` for each complete frame before
  inspecting the next header; an incomplete frame returns without discarding it.
- `TDK_F_RB_UDP_PR_InputRecvUdpData` (`005b0fd8`) routes data through the registered
  local connection ID at packet offset `0x04`. An unknown ID takes the no-logic
  path, not the established receive path. The zero-ID branch is for handshake
  traffic, not a new arbitrary receive stream.

The Python receiver follows that admission rule and keeps transport and KCP
buffers separate. Contiguous transport data moves to KCP assembly before the
ACK, while the KCP callback still runs after the ACK so it cannot change lane
send counters prematurely. The ACK formula/layout are unchanged, but its input
now measures transport occupancy only. An 80 KiB KCP frame no longer closes the
64 KiB transport window while waiting for its remaining bytes.

Receive states are keyed by registered lane identity, not by each peer-supplied
word pair. Unknown/zero local IDs are ignored before allocating, acknowledging
or decoding data. Peer-word changes reuse that lane's sequence/cache state,
rather than resetting sequence admission or growing the state map.

Complete KCP frames are yielded and dispatched before validating the next
header. Invalid markers, impossible command-header lengths and oversized packets
raise a terminal connection error rather than clearing an acknowledged stream
and continuing. The minimum command-header check and explicit Python exception
are defensive host policy, not a claim that native validates every short length
identically. Valid partial headers/bodies remain buffered, with a 20 MiB packet
limit. A terminal failure aborts capture and clears pending application payloads;
dispatching a valid prefix does not guarantee a partial recording is returned.

An additional host-side guard limits each reordering cache to 4096 packets /
128 KiB; overflow fails the session rather than dropping required fragments.
These extra limits are defensive policy, not native constants. Offline tests
cover a sender obeying the advertised window with 64+ KiB frames, persistent
gaps, uint32 wraparound, reordered data, unknown IDs, peer-word changes,
independent lanes, malformed tails, and terminal error propagation. This is
static native parity plus simulated receive paths, not live camera validation.

Wrapped-frame debug deduplication now holds only 128 SHA-256 fingerprints and
does not hash/HEX-encode frames when RBUDP debug is disabled. No media history
is retained for diagnostics. Shutdown uses `finally` to release the socket even
if legacy partial-fragment emission or thread joining raises. These are local
resource-management changes, not new camera commands. No live device validation
was performed for this pass.

### Upper QUII Assembly And Remote Disconnect

The 2026-10-21 pass also checked the open AArch64 `liblive_player.so` through
GhidraMCP. `CQUIIStreamBase::OnRecvCommand` (`00479d98`) retains incomplete
commands but returns an error for invalid data. `OnRecvData` (`0047af70`)
reads the signed media length at header offset `0x0b` and rejects non-positive
or overflowing total lengths. The Python decoder now rejects invalid media
lengths before copying/decrypting the body; decode errors are no longer saved
as an indefinitely growing prefix.

Additional Python admission policy caps a declared QUII media body at 20 MiB
and pending assembly at 32 logical stream keys / 32 MiB of payload bytes.
The shared budget counts chained prefixes, fragmented-media headers/bodies
and the incoming chunk before concatenation or append. Exceeding it raises
`QuiiConnectionError` and releases both pending maps. These are host-side
limits, **not** native constants or a bound on total process RSS. Valid partial
headers/bodies and complete chained packets continue to use the existing
assembly paths.

In AArch64 `libqv-p2p-v2.so`, `KcpLinkClient::OnP2PRequDisconect` (`004a1ef8`)
handles `0x120102` only when the flag at packet offset `0x12` is zero, and
looks up both connection IDs at `0x28`/`0x2c` before notifying and closing the
matching connection. The Python handler follows that flag/ID rule for
connected or connecting preview lanes; responses, unknown IDs and lanes whose
logical connect has not been sent do not terminate a stream.
A matched disconnect terminates the current capture/RTSP session with
`QuiiConnectionError`, clears queued payloads and wakes consumers on both
incremental and legacy wrapped paths. The coordinator does not automatically
fail over to another lane or reconnect. `session.wait()` reports the failure
and RTSP closes its listener. Receiver failure also wakes logical-connect
startup waiters so they can report the error instead of timing out.
No new outbound packet or camera command is
introduced. Native parity is static; regression tests use synthetic packets,
not a live camera.

### Short Continuations And AES Context Finalization

The active AArch64 `liblive_player.so` was checked again through GhidraMCP.
`CQUIIStreamBase::OnRecv` (`004793fc`) dispatches an active media continuation
before the `0x20`-byte new-header check. `OnRecvData` (`0047af70`) appends a
positive body tail, including 1-31 bytes, and passes any excess back to the
outer parser. Python now uses that ordering too; another logical stream's
short new header remains buffered independently.

`OnRecvCommand` (`00479d98`) waits for the whole declared command before
decryption. `PackFrame` (`0047b1ec`) decrypts metadata at offset 9 and reads
media starting at offset `0x10` only after assembly. `EncryptData` (`004799c4`)
initializes one AES key/IV per operation and decrypts the supplied region.
The Python helper now uses one cipher context for both `update` and `finalize`,
instead of silently losing a partial final block. Partial command bodies and
metadata wait for enough input; full malformed, non-block-aligned AES regions
raise an error. Rejecting such malformed input is defensive host validation,
not a claim that native OpenSSL rejects every malformed length identically.
Clear mode, the existing IV, valid aligned ciphertext and media's clear tail
are unchanged.

Regression tests use real AES decoding, every 1-31-byte final tail in all
capture phases, every single split/one-byte input, encrypted media and metadata,
independent streams, chained remainders and 1500 seeded command/media/mixed
partitions. These are synthetic parity checks, not new live camera evidence.

## Desktop Conversation Boundary

`Camera.converse()` adds no packet format. It reuses the two-connection talk
coordinator with `full_duplex=True`, selected-panel preview reception and
generic talk 65535 transmission. Both apps' `AudioPlayerManager.startSendVoice`
Java loops skip requestAudio disable/restore in their full-duplex branch.
`audioToggleEx` was rechecked via GhidraMCP at `0042be60` (vHome) and `0043a220`
(vEye Pro): preview and talk reception remain separate sources. This is static
parity, not proof of physical firmware duplex support.

Optional miniaudio supplies local capture/playback and native rate/layout
conversion; the bridge exchanges signed PCM16 LE, 8000 Hz mono. G.711 decode
vectors cover all 256 codewords for both laws against frozen CPython 3.11
audioop results, without depending on audioop at runtime. The 200ms PCM
queue bounds/drop-oldest policy are host-side latency limits, not native
constants. Callback threads perform no socket I/O. Unlike the original
client's optional WebRTC DSP path, this bridge has no AEC/AGC/noise suppression.
Physical PC audio-device testing and overlapping-speech quality remain outstanding.

`CameraRtspStream.start_talk()` reuses the already-running preview. Its single
H264LiveAssembler/CFrame packer forwards completed E3 frame dictionaries to
the attached talk handle; no second socket reader or CFrame assembler is run
for receiving conversation audio. Only generic talk 65535 is opened. Local
microphone/playback is explicit and stops with `stop_talk()`; RTSP is unaffected.
The standalone `Camera.talk()` / `converse()` retain their own-preview behavior.

Both native `audioToggleEx` functions were rechecked, as were talk `OnStop`
(`0051b2bc` / `005150e0`): each stops its base talk transport and releases its
queued packets. Java `QvPlayerCore.breakTalkConnection()` calls `stopTalking`
and resets talk state independently of preview. The shared Python owner follows
that resource boundary. Duplicate starts are rejected; talk failures detach
only conversation, while a parent failure/close cancels it. These host-side
lifecycle/fan-out changes add no wire command or encoding change. Tests cover
startup cancellation, fresh talk restart, unsupported audio isolation and a
still-answering RTSP listener after talk stops. Native comparison remains
static; no device/cloud command was issued for this pass.

Both native `OnSendData` implementations (`0051ca80` / `00516a24`) frame and
send already captured data. Java's blocking `AudioRecord.read()` clocks the
capture loop. Accordingly, the desktop bridge sends one hardware-clocked
640-byte block without an additional 40ms completion wait; on backlog it drops
older complete blocks instead of replaying them in a burst. The public raw
`send_pcm()` path still paces application/WAV input and waits its playback
window. Packet encoding, ACK validation and network deadlines are unchanged.

The 2026-10-29 Tantos/Pi acceptance test used this same shared-preview path
from PR #19 (`679ef71`) with a clocked file adapter, not a physical audio
backend. The owner confirmed clear speech from panel 2 and a clear recorded
reply. Video continued after `stop_talk()`, the RTSP listener still answered,
and parent shutdown released the workers and both camera sockets. No cloud
request, door command or service change occurred during that LAN talk run.
It verifies this device/profile and lifecycle, not Vimar or every PC backend.

## Archive Download (Experimental)

`Camera.download_record()` is a separate LAN file-mode transfer, not live
snapshot capture. The inspected Java picture path is
`PlaybackModel.getPictureFile()` -> `QvFileCore` -> JNI `fileDownloadCreate()`.
The local `filew://...format=jpg` URL selects a writer, not a device endpoint.

Parity was checked through GhidraMCP with explicit program selection:

| Function | `liblive_player.so` (vHome analysis) | `liblive_player_veye_pro_1_9_4_0_2.so` |
| --- | --- | --- |
| `CQUIIStreamFile::ParseURL` | `005196c4` | `0052ac44` |
| `FillFileInfo` | `00519468` | `0052a9e8` |
| `SendOpen` | `00518bcc` | `0052a14c` |
| `SeekTime` | `0051a738` | `0052bce8` |
| `OnRecvEnd` | `0051ae8c` | `0052c43c` |
| `IQVJPGFileW::Write` | `0052da64` | `00537c30` |
| `CQVMP4FileW::Write` | `0051f0cc` | `00530ae4` |
| `CQVMP4FileW::WriteSample` | `00520870` | `005321d8` |

The vHome analysis database references an older Desktop executable path;
its hash identity with the current APK extraction was not established.
The relevant layouts agree with the exact extracted vEye library and Java.

The filename branch parses twenty decimal fields. Open `02` carries a
32-byte header with channel at `+13`, packed filename start time at `+15`,
filename fields 14/16/18/17/15 at `+19/+20/+24/+25/+26`, bit 5 of field 19
at `+27`. ParseURL overwrites the initial rec/pic selector with filename field
18, independently of the CGI `filetype`. FillFileInfo stores its low byte at
`+24`, but tests the full field for zero when choosing the tail at `+28`.
Zero selects the packed filename end time; nonzero selects `idx`. The video
URL supplies no `idx`, so that tail stays zero for video with a nonzero field
18, as observed in Tantos archive filenames. Pictures use their separate
`picture_index`. Field 20 is parsed but not sent. Field 16 retains all 32 bits;
the other flag stores keep their low byte.
The original filename and `entry.url` are not sent as the Open body.
That body is `adminapp2&&<encoded auth>\0\0` (empty custom id), followed by
SHA256(header + body), zero padding, and separately initialized header/body
AES-CBC, matching the existing AES-256/SHA256 LAN profile.

The 2026-10-30 recheck of `ParseURL`, `FillFileInfo` and `SendOpen` in both
libraries confirmed this filename-based Open layout. Their separate
time-range Open `03` path is not implemented by `download_record()`.
CGI archive selectors `idx`, `idf`, `ids` and `idc` may instead be nested in
`address`; the parser uses them when the corresponding flat field is missing
or empty. Nonempty flat fields retain priority, including numeric zero.
Zero-padded `idx` is preserved, and unexposed address fields remain in `raw`.
Offline XML-to-Open vectors cover this layout without a manual `idx` override.
This fixes metadata parsing, not the reported silent Open on Intelbras Allo
wT7: neither an Allo Plus binary comparison nor an Intelbras device test was
performed for this fix. A live session succeeding does not prove file-mode parity.
An isolated LAN-only Tantos/Pi check with this parser downloaded the ten most
recent video entries from nested `address` metadata using a saved key. All ten
MP4s contained H.264 1888x1080 video at about 25 FPS and AAC 8000 Hz mono audio,
lasted about 62 seconds and passed complete FFmpeg decoding without errors.
SHA256 matched after copying them to the local machine. Picture lists on both
channels were empty, so archived JPEG transfer remains unverified. The check
made no cloud requests, door commands or changes to working services.

File Setup is `A9` with byte 9 equal to 1. In the ordinary download path,
`ITDKDownload::OnCheckFile` (`0078420c`) calls the reader's initial Seek.
JNI obtains this time from Java `getStartTime()`, independently of the URI.
Accordingly the Python downloader uses CGI `entry.start_time` when present,
or explicitly falls back to filename start time, without timezone conversion.
After Open succeeds it sends Seek `05` and normal session playback mode
`15` (1/1). These commands do not change persistent device settings.

The JPEG writer copies CPacket data after its 20-byte header directly to the
output. The implementation collects E4 / codec 3 payloads across TCP and
CPacket boundaries, retaining a single bounded JPEG. It requires an
authenticated EOF command `08`, complete CPackets and JPEG SOI/EOI markers;
it does not decode the image or treat a disconnect as EOF. CGI `filesize`
is preserved in its existing units and is not an exact transfer-length check.

`CQVMP4FileW::WriteSample()` uses consecutive `CPacket::FrameGetTimeStamp()`
differences, not an archive-search duration. The Python H.264 collector keeps
these device-local millisecond timestamps and waits for the first IDR, as the
native writer waits for a keyframe. Both native writers allow a zero interval;
the collector retains equal timestamps and all frames. It still rejects
backwards times or gaps over 30 seconds instead of the native writer's clamp
to zero. It also rejects codec/parameter-set/resolution changes and unsupported audio rather than
silently rewriting timing or dropping an unknown track.
Native `FrameIsVideo()` / `FrameIsAudio()` exclude E7/E8 metadata in both
libraries; these packets are consumed without becoming samples. Their bytes
still count toward the budget. NAL-count and frame-count limits prevent many
tiny packets from expanding into unbounded Python metadata.

One private Matroska intermediate carries length-prefixed H.264 access units
and their normalized timestamps. Its structure and AVC initialization follow
the [Matroska elements](https://www.matroska.org/technical/elements.html) and
[AVC mapping](https://www.matroska.org/technical/codec_specs.html).
FFmpeg stream-copies video to MP4 and encodes supported G.711 audio as AAC.
The last sample duration uses reported FPS, falling back to positive observed
intervals (zero intervals do not imply zero duration). Without either source,
export fails explicitly. The MP4 muxer may move equal timestamps apart by a
single container tick; other frame times remain unchanged. No `-r` or
duration-based video retiming, `-fs` truncation, new Python dependency or
per-frame file is used.
Temporary files are removed on success and failure; export shares the network
deadline and only the complete, size-checked MP4 is returned.

The Tantos read-only probe on 2026-10-29 observed empty picture lists and
nonempty video `record/datalist/data`, with `record/page=0`. These nested
list/status fields are parsed explicitly; the wrapper is not a file. Native
Java's pull parser reads the same tags.

Offline synthetic vectors and scripted sockets cover both transfer kinds;
FFmpeg/ffprobe regressions decode baseline/high-profile H.264 I/P frames and
verify variable/equal timestamps, frame counts and audio. Two public-API
Tantos/Pi downloads on 2026-10-29 returned about 30-second H.264 960x576 MP4s
with 749 decoded video frames and AAC 8000 Hz mono audio. Full FFmpeg decoding
with `-xerror` succeeded without errors. The null-output check used
`-fps_mode passthrough -enc_time_base:v 1/1000000` to avoid DTS rounding errors
in the validation output. These were isolated LAN-only tests using the saved
key, with no cloud requests, door commands or service changes.
The owner also reviewed a downloaded MP4 locally and confirmed correct image
and sound. Exact lip-sync and long-run playback quality were not measured.
Archived JPEG transfer, Allo Plus/Intelbras firmware, and simultaneous
archive/live resource availability remain unverified. H.265, AAC input,
interactive/time-range playback, HTTP download and automatic cloud fallback
are not supported by this implementation.

## Native Crypto Asset Validation

Inspection explicitly targeted the open AArch64 `libqv-p2p-v2.so`, independently
of the GUI's selected program. `GenerateSourceData()` (`0053e11c`) copies three
4096-byte constants from `007a5c27`, `007a6c27`, and `007a7c27`. With image base
`00100000` and the first ELF `PT_LOAD` mapping file offset / virtual address
`0`, the verified file offsets are `0x6a5c27`, `0x6a6c27`, and `0x6a7c27`.
`GenerateSeedKeyAndBox` (`0053ddd4`, client-id overload) consumes those tables.

The loader requires ELF64 little-endian AArch64 / `ET_DYN` and compares all
three table SHA-256 fingerprints with this verified profile. It reads only the
header and table ranges, not the entire library. Table contents remain external
assets; only compatibility fingerprints are stored in the source. Synthetic
fixtures cover wrong ABI/header, truncation, each table's mismatch, and asset
directory fallback. No actual extracted secrets are included in the tests.
Other app builds require native layout verification before support is claimed.

## Package Layout

Important package areas:

| Path | Purpose |
| --- | --- |
| `quii_helper/camera/` | Public camera API and high-level orchestration. |
| `quii_helper/cloud/` | Cloud authentication and runtime credential APIs. |
| `quii_helper/device/` | Local device APIs, response models, and explicit control commands. |
| `quii_helper/protocols/` | Native LAN TCP, cloud/P2P RBUDP, QUII codecs and wire formats. |
| `quii_helper/media/` | Media decoding, frame extraction, and rendering. |
| `quii_helper/streaming/` | RTSP streaming implementation. |
| `quii_helper/config/` | Settings and `.env` loading. |
| `quii_helper/support/` | Shared support utilities such as error-code descriptions. |
