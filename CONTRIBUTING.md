# Contributing

[Project Overview](README.md) | [Documentation](docs/README.md) |
[Release Checklist](RELEASE_CHECKLIST.md) | [Security](SECURITY.md)

Keep changes small, preserve the public API unless a migration is explicit,
and separate protocol behavior from formatting or documentation work.

## Development Setup

From a checkout, create and activate a Python 3.10+ environment. On Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pre_commit install
```

On Linux/macOS, use `source .venv/bin/activate` for activation. Run all commands
below with that environment active, or use its full interpreter path.
Git and Go are also needed for the release/secret-scanning tools.

Offline tests do not need your `.env`, APK assets, or a camera. Keep extracted
material and generated output in ignored `assets/` / `data/` directories.
Never add real credentials, native libraries, keys, or media to fixtures.

## Local Checks

```shell
python -m ruff check .
python -m black --check .
python -m mypy
python -m mypy quii_helper --strict --no-incremental
python -m pytest
python -m pip check
```

The suite blocks non-loopback connections/sends; it is not a live camera test.
For documentation changes, regression tests also check API tables, Python
examples, environment-template coverage, and repository links/anchors:

```shell
python -m pytest tests/package/test_documentation.py tests/package/test_examples.py
```

Before publication, use the [unified release gate](RELEASE_CHECKLIST.md#unified-release-gate)
on a clean committed candidate rather than treating individual green checks
as release approval.

## Protocol And API Changes

Add a reproducible regression fixture before changing RBUDP, QUII, crypto,
or media assembly. Compare wire behavior with the original native/client code
or an authorized packet capture. Synthetic tests and static parity are not
proof of live interoperability; state what was and was not verified.

Update callers, type hints, examples, documentation, and regression tests
together. Do not add speculative abstractions or a dependency for a task the
standard library already handles. Do not use door-opening commands as tests.

## Documentation Style

- Keep documentation in English, with descriptive Title Case headings.
- Keep README short and task-oriented; link detailed setup and API material.
- Use absolute GitHub links in README so its PyPI description also works.
- Keep internal document links relative and preserve existing public anchors.
- Use `python -m examples.<name>` for checkout examples; label physical effects.
- Document defaults, mandatory arguments, return values, and operation-specific inputs.
- Keep historical validation in Compatibility/Protocol Notes, not the first-run path.
- Update current release statements before building; do not rewrite historical release notes.

## Secrets And Pull Requests

Run the pinned history scanner before sharing a release candidate:

```shell
go run github.com/zricethezav/gitleaks/v8@v8.30.1 git --config .gitleaks.toml --redact --verbose .
```

Review `git diff`, `git status --short`, and `git ls-files` before a commit.
`.env.example`, `assets/.gitkeep`, and `data/.gitkeep` are expected public
placeholders; real `.env` variants, asset contents, logs, and media are not.
Scanner success is not a substitute for reviewing what you share.

A pull request should state the user-visible outcome, validation performed,
and remaining gaps. Follow the [Code Of Conduct](CODE_OF_CONDUCT.md).
