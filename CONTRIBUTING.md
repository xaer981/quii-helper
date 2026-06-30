# Contributing

## Development Setup

Use Python 3.10 or newer.

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -e ".[dev]"
.\venv\Scripts\python.exe -m pre_commit install
```

Runtime secrets, extracted certificates, native libraries, and generated media
must stay local. Do not commit `.env`, `assets/*`, or `data/*`.

## Validation

Run the stable local checks before opening a pull request:

```powershell
python -m ruff check .
python -m black --check .
python -m mypy
python -m mypy quii_helper --strict --no-incremental
python -m pytest
```

If you changed packet handling, RBUDP, QUII decoding, or media assembly, add a
unit/regression fixture first and compare behavior against the original client
or captured packet logs. Do not rely on live-device testing as the only
validation step.

## Refactoring Rules

Keep public APIs stable unless a breaking change is explicitly planned before a
release. Prefer small passes: delete dead code, extract helpers, simplify one
control path, then run tests. Avoid mixing protocol behavior changes with
formatting, packaging, or documentation changes.

## Secret Scanning

Before publishing or tagging a release, scan the repository for secrets. At
minimum, verify:

```powershell
git status --short
git ls-files | Select-String -Pattern "\.env|assets/|data/"
```

Use a dedicated scanner such as `gitleaks` or GitHub secret scanning for a real
release gate.
