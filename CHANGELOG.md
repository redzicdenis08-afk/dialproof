# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Native VAPI / Retell / Bland transcript adapters
- Latency scoring from per-word timestamps
- CSV export for the aggregate report
- Configurable severity weights

## [0.1.0] - 2026-07-02

### Added
- Receipt-backed findings: `Receipt`, `receipt_for`, and a `Finding` type that
  refuses to exist without verbatim transcript evidence.
- Default QA check suite: `greeting`, `disclosure`, `opener_loop`,
  `interruption_recovery`, `objection_handling`, `booking_completion`,
  `forbidden_phrases`, `dead_air`, `transfer_handling`, `abrupt_ending`.
- Pluggable check registry (`register_check`) and tunable `AuditConfig`.
- `Auditor` with per-call 0–100 scoring and severity-weighted deductions.
- Aggregate reporting (`AggregateReport`) with text and JSON renderers.
- `ActionGate`: dry-run-by-default gate for outbound side effects with an
  explicit `ARM-LIVE` confirmation phrase and a full attempt history.
- Transcript parsing for JSON (object, provider-style messages, bare list) and
  plain text with optional `[m:ss]` timestamps; file/directory loading.
- `dialproof audit` / `dialproof report` CLI with `--json`, `--checks`,
  `--forbidden`, `--dead-air`, and CI-friendly `--fail-under`.
- Synthetic example calls, a runnable library example, and a test suite
  covering every check in both firing and quiet states.
