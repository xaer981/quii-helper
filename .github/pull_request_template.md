## Summary

- TBD

## Validation

- [ ] `python -m black --check .`
- [ ] `python -m ruff check .`
- [ ] `python -m mypy`
- [ ] `python -m mypy quii_helper --strict --no-incremental`
- [ ] `python -m pytest`
- [ ] `python -m pip check`
- [ ] `gitleaks git --config .gitleaks.toml --redact --verbose .`

## Notes

- [ ] No secrets, `.env` values, private keys, APK assets, generated captures, or raw logs are committed.
- [ ] Protocol changes were validated against fixtures, native behavior, or real-device logs where applicable.
- [ ] Documentation, API examples, and navigation match the changed behavior.
