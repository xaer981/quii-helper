# Local Archive CLI

[Documentation](README.md) | [Setup](setup.md) | [Archive Python API](api.md#archive-queries)

In your virtual environment, run:

```shell
python -m pip install --upgrade quii-helper
quii-helper archive --help
```

For styled tables and status messages, install the optional extra with
`python -m pip install --upgrade "quii-helper[cli]"`. The commands and
prompts also work without it. Redirected output stays plain; set `NO_COLOR`
to disable terminal colors.

## What It Does

List pictures and videos already saved by the device, then optionally export
their metadata to JSON. This command uses **local CGI only**, with no preview,
cloud login, key refresh, download, door command or recording-setting change.
It does not need FFmpeg or the optional audio dependencies.

`archive download` retrieves one picture or video over the device's native
LAN TCP port. Choose it directly from a LAN search, or use an exported JSON
list to skip the CGI search and prompts. Use the Python API for
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
`--credentials data/stream_credentials.json` to the command. Listing uses only
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

For a whole day, use `--date YYYY-MM-DD` instead of `--from` and `--to`.

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

## Download One Record

Before downloading:

- Use the device's numeric IP in `CAMERA_DEVICE_HOST`.
- Provide a saved key/auth pair: `STREAM_KEY` and `AUTH_CODE`, or add
  `--credentials data/stream_credentials.json` to either download command.
  The CLI checks the pair before searching; it never requests a new key.
- For MP4, install FFmpeg on PATH and use a writable private `data/`
  directory. JPEG downloads do not require FFmpeg.

### In A Terminal

```shell
quii-helper archive download --date 2026-11-27 --type video
```

Choose a row by number. If there are more rows, use `n` or `p` to move between
pages. Enter a destination path or press Enter to use the suggested filename;
pass `--output FILE` to skip the path prompt. Type `q` or press Ctrl+C to cancel.
The command downloads the selected record from the displayed result, without
repeating the CGI search or writing a JSON list. Prompts and status go to stderr.

### From A Script

Export a complete list with `archive list --output records.json`. Then use the
row number in that exact file. For example, if row 2 is a video:

```shell
quii-helper archive download --from-list records.json --index 2 --output media/clip.mp4
```

Use a new `.jpg` or `.jpeg` output for a picture, or `.mp4` for a video.
Use a list you exported yourself. Its host and any nonempty device ID must
match the current configuration. Row numbers are not device IDs; if a record
has disappeared since listing, download can fail. A malformed, mismatched,
oversized (over 16 MiB) or empty list cannot start a transfer.

The native TCP port comes from `CAMERA_STREAM_PORT` (default 34567), not
the CGI port. The command
uses only the configured device address, never a URL from the list, and
does not log in to cloud, refresh credentials, or start live preview.

The default media limits are 30 seconds for
setup, transfer and remux and 16 MiB for received data/returned bytes.
Increase with `--timeout SECONDS` or `--max-bytes BYTES` where needed.
Output is saved privately and atomically without replacing any existing
file, using the same filesystem rules as the JSON export. A failed transfer
creates no output.

The CLI uses the default protocol. Firmware requiring `pipelined`
(e.g. some Intelbras models) still needs the
[Python API with explicit file-channel credentials](api.md#archive-downloads-and-metadata).
Real-device support depends on the firmware; see [device coverage](../COMPATIBILITY.md).

## Filters And Transport

These filters apply to `archive list` and the interactive download search,
not to `archive download --from-list`:

| Option | Meaning |
| --- | --- |
| `--type all`, `video`, `picture` | Default `all` searches video and pictures and requires both searches to complete. Select one type if the other is unsupported. |
| `--channel N` | Defaults to `CAMERA_CHANNEL` (including its existing aliases), or 1 if unset. The flag overrides it. Channel mappings depend on firmware. |
| `--occur-type VALUE` | Native occurrence filter; default `all`, examples `manual` and `event`. Firmware-specific values are passed through, not interpreted as confirmed calls. |
| `--stream all`, `main`, `sub` | Archive stream filter; default `all`. This is not the live-quality setting `CAMERA_STREAM`. |
| `--max-pages N` | Positive page cap per native whole-day search/type; default 32. A narrow interval can still need multiple pages. If the result is incomplete, no successful list is emitted; deliberately increase the cap if appropriate. |
| `--scheme http`, `https` | Default HTTP uses port 80; HTTPS uses 443. `--cgi-port N` overrides that port, separately from `CAMERA_STREAM_PORT`. |
| `--credentials FILE` | Explicit existing key/auth JSON, used for CGI auth and device identity, and for the stream key when downloading. Available in both download modes. No automatic lookup or fallback. |

HTTP sends CGI authentication without transport encryption: use it only on
a trusted LAN. Archive CGI calls connect directly to the configured camera:
they ignore system HTTP(S) proxies and do not follow redirects. HTTPS uses
configured TLS verification; failures do **not** trigger an insecure retry
or cloud fallback. A warning is printed if
`TLS_VERIFY=false` is already explicitly configured.

If search fails, check the device's CGI address, authentication and TLS
settings. A transfer failure is separate: check the saved key/auth pair
and the download limits. A save error points to the destination, including
write permissions and filesystem support for hard links.

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

For `list`, `--output` requires a new `.json` path. Neither command replaces an existing file,
including symlinks. `.env` paths and unsafe Windows filenames (including
parent folder names) are rejected before reading from the camera when
provided on the command line, or before transfer when entered at the prompt.
Missing parent directories are created when saving the result, after the
search or download succeeds. A private temporary file is atomically linked into
place, protecting against another writer creating the same target. The target
filesystem must support hard links; there is no unsafe overwrite fallback.
On POSIX the file is owner-only; on Windows check the parent directory's ACL.
Use a private application directory, not a shared writable directory.

Exit codes: `0` complete result, `1` configuration/query/transfer/output failure,
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
