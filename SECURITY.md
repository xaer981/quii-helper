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

Version `0.1.0` is the first final release being prepared; until it is
published, the latest public package remains `0.1.0rc6`. After publication,
security fixes will target the latest `0.1.x` release; older release candidates
will not receive separate backports. The API remains pre-`1.0`, and experimental
features and compatibility limits are documented explicitly.
