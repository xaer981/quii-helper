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
then a read-only cloud metadata lookup when needed. Explicit `"plain"` and
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
| `quii_helper/protocols/` | RBUDP/QUII protocol implementation. |
| `quii_helper/media/` | Media decoding, frame extraction, and rendering. |
| `quii_helper/streaming/` | RTSP streaming implementation. |
| `quii_helper/config/` | Settings and `.env` loading. |
| `quii_helper/support/` | Shared support utilities such as error-code descriptions. |
