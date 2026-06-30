# Release Checklist

Use this checklist before publishing a public release.

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

## Packaging

- Verify `pyproject.toml` metadata.
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
