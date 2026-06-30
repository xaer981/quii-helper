# Security Policy

## Sensitive Files

This project expects users to provide their own local `.env` values and assets
extracted from their own application/device environment. These files are
intentionally ignored by git:

- `.env`
- `assets/*`
- `data/*`
- generated `*.mp4`, `*.jpg`, `*.h264`, `*.jsonl`, and `*.log` files

Do not open issues or pull requests containing device credentials, cloud
accounts, extracted private keys, certificates, native libraries, logs with
tokens, or media from private cameras.

## Reporting Vulnerabilities

Until a dedicated disclosure channel exists, report security-sensitive issues
privately to the repository owner. Do not publish exploit details or real
credentials in public issues.

## Supported Versions

No stable public release exists yet. Treat the current codebase as pre-`0.1.0`
development software.
