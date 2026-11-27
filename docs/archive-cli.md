# Local Archive CLI

[Documentation](README.md) | [Setup](setup.md) | [Archive Python API](api.md#archive-queries)

**Development version:** `quii-helper archive list` is not included in PyPI
version 0.8.0. For now, install from the development checkout in your virtual
environment with `python -m pip install .`, then check
`quii-helper archive list --help`. See [development setup](../CONTRIBUTING.md).
A release version has not been assigned.

## What It Does

List pictures and videos already saved by the device, then optionally export
their metadata to JSON. This command uses **local CGI only**, with no preview,
cloud login, key refresh, download, door command or recording-setting change.
It does not need FFmpeg or the optional audio dependencies.

The CLI currently provides `archive list` only. Use the existing Python API
for [downloads](api.md#archive-queries) and
[observation of new entries](api.md#local-archive-observations).

## Configure Once

From your application directory, provide these `.env` settings:

```dotenv
CAMERA_CONNECTION_MODE=lan
CAMERA_DEVICE_HOST=192.0.2.10
AUTH_CODE=your-local-auth-code
```

Replace the example IP and auth code. `AUTH_CODE` is local CGI authentication,
not your cloud account password or door-unlock password. A stream key, cloud
account and APK assets are **not** required to list metadata.

**Already have a saved key/auth JSON?** Keep only the LAN mode and host
settings above, omit `AUTH_CODE`, and explicitly add
`--credentials data/stream_credentials.json` to the command. It reads only
the device ID and auth code from that file; it never requests a new key.
If `DEVICE_ID` is configured, it must match the file. With `--credentials`,
the file's auth code takes precedence over `AUTH_CODE`.

The CLI parses the **entire `.env`**, so a malformed unused setting can also
stop the command. `CAMERA_CONNECTION_MODE=cloud` is rejected, not silently
overridden. Settings are not changed or copied by this command.

## List And Save

Choose an interval using the **device's clock**, not the computer's timezone:

```shell
quii-helper archive list --from "2026-11-27 00:00:00" --to "2026-11-27 23:59:59" --type video --output records.json
```

Replace the dates with your interval. Bounds must use
`YYYY-MM-DD HH:MM:SS`, with `--from` strictly before `--to`. The CLI generates
the native lowercase `t`/`z` form internally, without a UTC conversion.
Both bounds are inclusive; an end at midnight is valid. The library searches
whole calendar days, then returns only records overlapping your original
interval. Pictures use their start time; videos can start before the interval
and still overlap it. Do not manually change `--to` to `23:59:59` unless you
actually want the whole day. Firmware can omit recordings that began before
the searched calendar days. Unusable/ambiguous record times fail the query
rather than silently dropping entries.

The table shows a one-based index, type, channel, start/end times, occurrence,
size in **KiB** (or `?`), and filename. Times and identifiers come from the
device; entries are not assumed to be chronologically sorted. Indexes refer
to this particular result only, not stable device IDs.

`--output` additionally saves the complete list. Omit it for a table only.
For machine-readable stdout instead of a table:

```shell
quii-helper archive list --from "2026-11-27 00:00:00" --to "2026-11-27 23:59:59" --type picture --json
```

Warnings and status go to stderr, not into JSON stdout.

## Filters And Transport

| Option | Meaning |
| --- | --- |
| `--type all`, `video`, `picture` | Passed to `Camera.list_record_files()`: default `all` combines video then picture, with both searches required to complete. The CLI delegates once, not twice. Select one type if the other is unsupported. |
| `--channel N` | Defaults to `CAMERA_CHANNEL` (including its existing aliases), or 1 if unset. The flag overrides it. Channel mappings depend on firmware. |
| `--occur-type VALUE` | Native occurrence filter; default `all`, examples `manual` and `event`. Firmware-specific values are passed through, not interpreted as confirmed calls. |
| `--stream all`, `main`, `sub` | Archive stream filter; default `all`. This is not the live-quality setting `CAMERA_STREAM`. |
| `--max-pages N` | Positive page cap per native whole-day search/type; default 32. A narrow interval can still need multiple pages. If the result is incomplete, no successful list is emitted; deliberately increase the cap if appropriate. |
| `--scheme http`, `https` | Default HTTP uses port 80; HTTPS uses 443. `--cgi-port N` overrides that port, separately from `CAMERA_STREAM_PORT`. |
| `--credentials FILE` | Explicit existing key/auth JSON, used only for CGI auth and device identity. No automatic lookup or fallback. |

HTTP sends CGI authentication without transport encryption: use it only on
a trusted LAN. HTTPS uses configured TLS verification; failures do **not**
trigger an insecure retry or cloud fallback. A warning is printed if
`TLS_VERIFY=false` is already explicitly configured.

No more than 10,000 distinct records are exported. Query errors, incomplete
pages and the record cap fail rather than silently truncating a successful
result. A completed empty list is valid; it does not prove that no one called.

## Private JSON And File Safety

The version-1 snapshot contains:

- `version`, `device` (configured host and device ID), and `query` (bounds and filters).
- `records` with native file selectors, timestamps, occurrence, stream, frame rate, and `file_size_kib`.

`file_size_kib` is the native size hint, **not an exact byte count**. Missing
selectors remain empty; metadata is not invented. Raw XML, raw response
fields, URLs, auth codes, stream keys and account passwords are not exported.
The JSON still contains **private device metadata**: do not post it publicly
without reviewing the host, device ID, filenames and timestamps.

`--output` requires a new `.json` path and never replaces an existing file,
including symlinks. `.env` paths and unsafe Windows filenames (including
parent folder names) are rejected before loading settings or reading from
the camera. Missing parent directories are created only
after successful queries. A private temporary file is atomically linked into
place, protecting against another writer creating the same target. The target
filesystem must support hard links; there is no unsafe overwrite fallback.
On POSIX the file is owner-only; on Windows check the parent directory's ACL.
Use a private application directory, not a shared writable directory.

Exit codes: `0` complete result, `1` configuration/query/output failure,
`2` invalid arguments, `130` interrupted. If writing stdout fails after a file
was saved, that file can already exist; check it before retrying with a new path.

## Limits

The archive depends on storage availability and the device's existing
recording settings. This command does not enable recording or recover missing
files. `manual` can mean a call-triggered recording **or** a manual recording;
it is not a reliable call notification by itself. Entry availability can be
delayed until recording ends. See
[archive limitations](api.md#local-archive-observations) and
[device coverage](../COMPATIBILITY.md).
