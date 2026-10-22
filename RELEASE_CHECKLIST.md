# Release Checklist

Use this checklist before publishing a public release.

## Unified Release Gate

Freeze the candidate first: commit the reviewed changes and stop editing it.
Run the local gate with Python 3.10 or 3.11, Git and Go on `PATH`:

```powershell
python -m pip install -e ".[dev]" build twine
python .github/scripts/release_gate.py
```

This command does not publish, tag, call the cloud, or send device commands.
It rejects a dirty worktree, copies only public inputs to an ignored snapshot,
and writes `data/release-gate/<timestamp>/report.json`, source SHA-256 hashes,
archive hashes and individual check logs. It runs dependency checks, lint,
formatting, strict typing, all offline tests, public-source Gitleaks scanning,
workflow validation, build/Twine/archive checks, and fresh wheel **and** sdist
installs. Both installed artifacts run the full suite from a consumer directory
without the source package on the import path, not just an import smoke test.
Tests block non-loopback socket connections/sends as an extra safety check.
The local source scan does not replace CI's Git history scan.

The installed wheel also runs a 2-minute synthetic loopback RTSP test: a fast
TCP viewer, a non-reading viewer, RTP sequence checks, bounded output queues,
repeated server/client shutdown, thread cleanup and retained Python allocations.
The 8 MiB growth guard measures `tracemalloc` allocations after warmup, **not**
total process RSS. This is not a video-decoder quality test or a real camera,
cloud, UDP or ARM64 validation.

For development only, use
`python .github/scripts/release_gate.py --allow-dirty --soak-seconds 5`.
A dirty or shortened run is explicitly reported as
`development_pass_not_release_candidate`, never as release approval. Source or
commit changes during a run fail the gate. A clean full run reports
`automated_pass`; manual camera validation is still marked **pending**.

CI exposes one aggregate **`release-gate`** job. It requires every lint/test,
secret-scan, build, installed-artifact matrix and 2-minute RTSP job to succeed;
failed, cancelled or skipped prerequisites cannot turn it green. Configure this
job as a required branch-protection check in GitHub. The publishing workflow
already depends on the reusable CI workflow, so the same gate must pass before
its separately approved upload. It uses the exact tested archives without
rebuilding them. GitHub protection settings are not changed by this script.

Before approving publication, record an owner-run check on the **same commit**:
snapshot, a recording of the requested duration, RTSP reception/shutdown and the
entrance-bot integration. Do not run door-control commands as part of this gate.
Any new code change invalidates that candidate's validation and requires a new
gate run. A green gate reduces regressions; it is not proof of zero bugs.

## Code

- Run `python -m ruff check .`.
- Run `python -m black --check .`.
- Run `python -m mypy`.
- Run `python -m mypy quii_helper --strict --no-incremental`.
- Run `python -m pytest`.
- Run `python -m pip check`.
- Run package import smoke tests, including `from quii_helper import Camera`.
- Run `go run github.com/zricethezav/gitleaks/v8@v8.30.1 git --config .gitleaks.toml --redact --verbose .`.
- Verify any protocol changes against packet fixtures and native/original-client
  behavior.
- Keep RBUDP regressions green for large KCP frames with a window-obeying sender,
  unknown connections, peer-word changes, malformed tails and error propagation.
- Keep upper QUII tests green for invalid declared lengths, shared byte/stream
  limits, valid fragmented/chained packets, and cleanup after decode failure.
- Check camera-originated disconnects on incremental and legacy receive paths,
  ignoring unrelated IDs/response flags and propagating failure to RTSP waiters.
- Verify dotted output names remain distinct through the actual media writer.

## Packaging

- Verify `pyproject.toml` metadata.
- Assign a new, unused version before publication. Do not upload a local
  rebuild with the already released `0.1.0rc6` version.
- In a clean source copy without real credentials/assets/media, install the
  build tools with `python -m pip install build twine` and run
  `python -m build --outdir data/package-check/dist`. The default command builds
  an sdist first, then builds its wheel from that sdist.
- Run `python -m twine check --strict` on both generated archives. This checks
  metadata and README rendering without uploading either artifact.
- Inspect archive members: the sdist must include documentation, examples,
  tests, and `.env.example`; neither artifact may include real `.env` files,
  extracted certificates/libraries, generated media, or virtual environments.
- Install the wheel and sdist into separate fresh virtual environments and run
  `pip check` plus import/configuration/logging smoke checks from outside the
  source checkout. Confirm that imports use `site-packages`, not editable
  source paths. Do not invoke camera/cloud operations as installation tests.
- Verify `pip install -e ".[dev]"` in a clean virtual environment.
- Confirm `quii_helper/py.typed` is included in package data.

## Secrets

- Confirm `.env`, `assets/*`, and `data/*` are not tracked.
- Run a secret scanner such as `gitleaks`.
- Review generated logs for credentials, tokens, IPs, and private media.

## Legal

- Confirm `LICENSE` and package metadata match the intended release terms.
- Confirm the README explains that users must provide their own extracted
  assets and credentials from software/devices they are authorized to use.

## CI And PyPI Setup

Before distributing a candidate, also verify the installed-package instructions
without a checkout: the wheel intentionally excludes `examples` and the env
template. JPEG/MP4 users need an external FFmpeg executable on `PATH`. Verify
asset rejection tests for unsupported ELF/table profiles; do not claim support
for arbitrary APK ABIs/builds without native inspection. RTSP backpressure and
UDP receiver failures must remain covered by offline regression tests.

The prepared version is `0.1.0`, with planned release tag `v0.1.0`. It has not
been published. The previous `0.1.0rc6` is already on PyPI; its wheel/sdist
installation checks passed, and all 140 entrance-bot tests passed against it
in a fresh Windows Python 3.11 environment on 2026-10-22. This was offline
consumer validation, not a deployment or a new ARM64/device check. See
[Setup](docs/setup.md#installing-on-linux-arm64) for the precise scope.

Updating metadata does not create a tag, GitHub release or PyPI upload. Freeze
and run the full gate on the final `0.1.0` commit before requesting publication;
manual validation must still be recorded separately. Do not replace any
published version's artifacts with different source code.

`ci.yml` runs on pushes and pull requests, and is reused by `publish.yml`:

- Test/lint/type checks on Windows and Linux, Python 3.10 and 3.11.
- Gitleaks history scan and actionlint workflow validation; no production
  settings or device requests.
- Build sdist, then wheel from that sdist; strict Twine checks, SPDX/license,
  type marker, archive privacy and package-source parity checks.
- Install wheel and sdist separately in clean Windows/Linux Python 3.10/3.11
  environments outside the checkout; run the full suite against each installed
  artifact, check dependencies and library isolation.
- Run the 2-minute synthetic RTSP soak against the same checked wheel, then
  require the aggregate `release-gate` job before publication approval.
- Retain the checked archives as `python-distributions` for seven days.

Linux CI is x86_64. Earlier ARM64 integration results do not replace testing a
new release on ARM64. CI does not exercise camera/cloud/door commands.

For each publication, verify these external settings (not changed by CI).
They were configured for the first `0.1.0rc6` upload; do not recreate them:

1. Verify the GitHub environment **`pypi`** in this repository. Require an
   approving reviewer and restrict deployments to release tags. Protect release
   tags with repository rules; do not permit tags to be moved after review.
2. In PyPI, verify the existing Trusted Publisher:
   project **`quii-helper`**, owner **`xaer981`**, repository **`quii-helper`**,
   workflow **`publish.yml`**, environment **`pypi`**. Confirm project ownership
   and that the new package version is unused.
   Do not create or store a long-lived `PYPI_TOKEN` for this workflow.
3. Merge reviewed source changes into `main`, confirm green CI, then create the
   matching immutable release tag from that commit. Creating a tag or GitHub
   release alone never invokes this publishing workflow.
4. Only when an upload is explicitly intended, dispatch **Publish to PyPI**
   against the release **tag**, not `main`:
   `gh workflow run publish.yml --ref v0.1.0`. The workflow must already
   exist on the default branch for manual dispatch to be available.
5. The workflow rejects branches, tags not belonging to `main`, and tag/package
   version mismatches. It reruns all CI gates, then waits for environment
   approval. Review that run's artifacts before approving.
6. Only the upload job gets `id-token: write`. It downloads the exact archives
   tested in that run, does not rebuild them, and publishes with provenance
   attestations. It does not skip already-existing files: investigate an
   interrupted or duplicate upload rather than silently replacing artifacts.
7. After a successful authorized upload, check the PyPI page and install
   `quii-helper==0.1.0` in a fresh consumer environment. For final releases,
   `python -m pip install --upgrade quii-helper` needs no `--pre`. Updating
   entrance-bot is a separate deploy.

Environment approval is a GitHub setting, not something YAML enforces by
itself. Do not run the publishing workflow until protection and the Trusted
Publisher are configured. The build-only CI requires no PyPI credentials.

References: [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/),
[first project via a pending publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/),
and [setuptools SPDX metadata](https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html).
