# Security Policy

dialproof analyzes call transcripts, which routinely contain personal data, so a few surfaces deserve explicit care.

## Reporting a vulnerability

Please do not open a public issue for security reports. Use GitHub's
[private vulnerability reporting](https://github.com/redzicdenis08-afk/dialproof/security/advisories/new)
on this repository with a description and a minimal reproduction.

## Security-sensitive surfaces

- **Transcript contents (PII).** Real transcripts carry names, phone numbers, addresses, and emails. dialproof runs fully offline and never transmits transcript data anywhere, but *receipts quote transcripts verbatim* — treat audit output with the same care as the transcripts themselves, and be deliberate about where `--json` output is stored or logged.
- **The action gate.** `ActionGate` is dry-run by default and can only go live via the exact `ARM-LIVE` confirmation phrase passed in code. There is intentionally no environment variable or config file that arms a gate. If you wire real executors (dialers, mailers), keep their credentials in your own secret store; this package never reads or stores credentials.
- **Parsing untrusted files.** Transcript parsing uses only `json` and bounded regular expressions from the standard library. Still, audit files from third parties are untrusted input — run with least privilege.
- **Example data.** Everything under `examples/` is synthetic (fictional businesses, `555` numbers). Contributions must keep it that way.

## Supported versions

This project is pre-1.0. Security fixes are applied to the latest `main`.
