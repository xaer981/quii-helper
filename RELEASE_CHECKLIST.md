# Release Checklist

[Documentation](docs/README.md) | [Contributing](CONTRIBUTING.md) |
[Compatibility](COMPATIBILITY.md) | [Security](SECURITY.md)

This is a maintainer workflow, not part of normal library setup. Building,
merging, tagging, creating a GitHub release, and publishing to PyPI are
separate actions. None is implied by a local validation run.

## Contents

- [Prepare the candidate](#prepare-the-candidate).
- [Run the unified gate](#unified-release-gate).
- [Record manual validation](#manual-validation).
- [Check publishing protection](#ci-and-pypi-setup).
- [Publish deliberately](#publication) and [verify the result](#after-publication).

## Prepare The Candidate

- Assign a **new unused version** in `pyproject.toml`. Never replace an already
  published version or move a reviewed release tag.
- Review API compatibility, examples, tests, license metadata, and archive contents.
- Update CHANGELOG and current release statements across README, setup, and
  SECURITY. The README embedded in a release must describe the intended released
  version, not instruct users to install an older RC or say it is unpublished.
- Preserve historical test/RC notes as history, not as current setup guidance.
- Verify README links/images work outside GitHub too; PyPI embeds build-time
  metadata, not a live GitHub README.
- Inspect public inputs for `.env` values, APK assets, private keys, media,
  virtual environments, and generated files. `.env.example` / `.gitkeep` are
  intentional public placeholders.
- Confirm `LICENSE` matches the SPDX metadata and that users provide their own
  authorized assets. Do not redistribute vendor material in a release.
- Commit the reviewed candidate and stop editing it before running the gate.

## Unified Release Gate

Use Python 3.10 or 3.11, Git, and Go on `PATH`:

```shell
python -m pip install -e ".[dev]" build twine
python .github/scripts/release_gate.py
```

The gate does not publish, tag, call the cloud, or send device commands. It
requires a clean candidate and copies only public inputs into an ignored
snapshot. Evidence goes to `data/release-gate/<timestamp>/report.json`, with
source/archive SHA-256 hashes and per-check logs.

| Check | What it proves |
| --- | --- |
| Lint, formatting, strict typing, dependencies | The configured static/dependency checks pass. |
| Source tests | Offline behavioral regressions pass; non-loopback I/O is blocked. |
| Gitleaks and actionlint | Public snapshot/workflows pass checks; CI separately scans Git history. |
| Build, strict Twine, archive validation | sdist and wheel metadata/rendering, SPDX/license, `py.typed`, privacy, and package-source parity. |
| Isolated installs | Wheel and sdist each install outside the source tree and run the full suite, not just imports. |
| RTSP soak | The installed wheel passes separate two-minute video-only and combined A/V synthetic loopback backpressure/lifecycle checks. |

The soaks cover fast and non-reading viewers, per-track RTP sequence and
G.711 sample-clock checks, SDP track URL resolution, bounded
queues, repeated shutdown, thread cleanup, and retained Python allocations.
Its 8 MiB growth guard uses `tracemalloc` after warmup, **not process RSS**.
It does not validate real camera/cloud/UDP behavior, codec quality, or ARM64.

A clean full run reports `automated_pass`, with manual validation still
**pending**. Changes to the candidate during a run fail it. For development
only, a dirty or shortened run can use:

```shell
python .github/scripts/release_gate.py --allow-dirty --soak-seconds 5
```

Its status is `development_pass_not_release_candidate`, never release approval.
A green gate is evidence about that candidate, not a guarantee of zero bugs.

## Manual Validation

Before approving publication, record an owner-run check on the **same commit**:
snapshot, a requested-duration recording, RTSP reception/shutdown, and relevant
consumer integration. Do not send door-control commands as part of the gate.
State whether testing was live, mocked, native-static, loopback, or installed
artifact validation; do not substitute one for another.

For the LAN path, check the two phases separately: explicit cloud
bootstrap/save/load (including the TLS policy), then capture/RTSP and a fresh
process reconnect using only the saved pair. Verify there are no cloud requests
or automatic renewal/fallback during LAN playback. Record the tested profile,
key age and decoded media results without publishing secrets. Do not claim
camera-WAN isolation, a key TTL or reboot persistence unless separately tested.

For protocol changes, verify packet fixtures and original-client/native parity.
Keep regression coverage for reordering/window limits, large/fragmented/chained
messages, short tails, unknown connections, malformed data, disconnects, and
failure propagation. Preserve output-name, resource-cleanup, and backpressure
checks. Any later code change requires a new candidate/gate run.

## CI And PyPI Setup

Verify these external settings without weakening them to ship a release:

1. GitHub requires the aggregate **`release-gate`** result for `main`.
2. Environment **`pypi`** requires a reviewer and limits deployment to release
   tags. Protect release tags against movement/deletion. Environment approval
   is a GitHub setting, not something YAML alone enforces.
3. PyPI Trusted Publisher matches project `quii-helper`, owner `xaer981`,
   repository `quii-helper`, workflow `publish.yml`, environment `pypi`.
   Do not add a long-lived `PYPI_TOKEN` for this OIDC workflow.

`ci.yml` runs on pushes/PRs and is reused by `publish.yml`. The aggregate gate
requires all tests, scans, builds, install jobs, and soak checks to succeed;
failed, cancelled, or skipped prerequisites cannot approve publication.
Linux CI is x86_64, not ARM64. See [Compatibility](COMPATIBILITY.md#validation-scope).

Build-only CI needs no PyPI credentials. It retains the checked archives as
`python-distributions` for seven days. The protected publishing job uses those
**exact tested archives**, without rebuilding, and adds provenance attestations.

## Publication

1. Merge the reviewed candidate into `main` and confirm green CI.
2. Create the matching immutable `vX.Y.Z` release tag from that commit; replace
   `X.Y.Z` with the new package version. RC tag normalization is supported too.
3. Create GitHub release notes and choose final/pre-release status correctly.
   A tag or GitHub release alone does **not** invoke PyPI publishing.
4. When an upload is explicitly intended, dispatch **Publish to PyPI** against
   that release tag, not `main`. For example, with the placeholder replaced:
   `gh workflow run publish.yml --ref vX.Y.Z`.
5. The workflow rejects branch refs, tags not belonging to `main`, and
   tag/package-version mismatches. Review that run's gate results and artifacts
   before the separate environment approval.
6. Only the upload job receives `id-token: write`. It does not skip existing
   files: investigate an interrupted/duplicate upload rather than replacing or
   deleting a working release.

## After Publication

- Confirm the publishing job succeeded and the expected wheel/sdist and version
  exist in PyPI. Check the metadata/description, not only the GitHub release.
- Install the exact new version in a fresh consumer environment. Check
  `pip check`, imports from `site-packages`, configuration/logging isolation,
  and artifact hashes. Do not load private settings or send device commands.
- Verify ordinary `python -m pip install --upgrade quii-helper` resolves the
  expected final release without `--pre`; allow for index propagation delay.
- Review the rendered README on both GitHub and PyPI. Existing PyPI metadata
  is not updated by a GitHub README edit or a replacement upload. Corrections
  for PyPI require a new version; do not move tags or reuse distribution names.
- Record the actual validation scope in Compatibility and close release notes
  in CHANGELOG. Consumer updates and deployments remain separate operations.

References: [Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/),
[PyPI metadata](https://docs.pypi.org/api/json/), and
[setuptools metadata](https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html).
