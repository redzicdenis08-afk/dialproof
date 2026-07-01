# dialproof

**Receipt-backed QA audits for AI voice-agent calls.** Feed it call transcripts and get back what actually broke — opener loops, dropped bookings, dead transfers, dead air, raw-LLM leakage — with every finding pinned to the exact transcript lines that prove it.

[![CI](https://github.com/redzicdenis08-afk/dialproof/actions/workflows/ci.yml/badge.svg)](https://github.com/redzicdenis08-afk/dialproof/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

> This repository is the open reference implementation of the DialProof audit engine — the part that turns transcripts into receipt-backed findings. The production deployment (discovery, probing, outreach, and its data) stays private.

Built for AI voice agencies and the teams that QA them. A voice agent that *sounds* fine in a happy-path demo still loses real customers to the same handful of failure modes, and provider dashboards won't show you any of them.

---

## Why receipts

Anyone can tell an agency "your demo is broken." That claim is worth nothing — and costs real trust when it's wrong — unless it arrives with evidence.

So in dialproof, **a finding without a receipt cannot exist.** The `Finding` constructor rejects any finding that doesn't cite the verbatim transcript turns that triggered it, with turn numbers and timestamps. A skeptical reader goes straight from *"your booking flow drops appointments"* to the two lines where a caller asked to book and the agent talked about office hours instead.

The checks are conservative on purpose: each one is tuned to under-fire rather than over-fire, because a false accusation is worse than a miss. That philosophy comes directly from running these audits against real voice-agent deployments.

## Architecture

```
 transcripts (.json / .txt)
          |
          v
   +-------------+     +----------------------------------------+
   |   parser    |     |             check registry             |
   | JSON / text |     |  greeting   opener_loop   dead_air ... |
   | role + time |     |  (pluggable via @register_check)       |
   +------+------+     +-------------------+--------------------+
          |                                |
          v                                v
   +----------------------------------------------------+
   |                      Auditor                       |
   |   runs each check  ->  Finding(check, severity,    |
   |                                message, RECEIPT)   |
   |   score = 100 - severity weights (floor 0)         |
   +------------------------+---------------------------+
                            |
            +---------------+----------------+
            v                                v
   +-----------------+             +------------------+
   |  CallAudit      |             | AggregateReport  |
   |  per-call       |             | roll-up across   |
   |  findings +     |             | calls: averages, |
   |  receipts       |             | worst calls,     |
   +-----------------+             | common failures  |
                                   +------------------+
                            |
                            v
              text report  /  --json
                            
   +----------------------------------------------------+
   |  ActionGate (side effects live here, and only here) |
   |  DRY_RUN by default -> arm("ARM-LIVE") to execute   |
   +----------------------------------------------------+
```

Everything above the gate is pure computation: no network, no database, no side effects.

## Install

```bash
pip install -e .            # from a clone
```

Zero runtime dependencies — pure Python standard library, runs fully offline. `pytest` and `ruff` are dev extras (`pip install -e ".[dev]"`).

## Quickstart

### CLI

```bash
dialproof audit examples/call_sunrise_dental.txt
```

```
call_sunrise_dental  score 50/100  FAIL
  checks: 10 run, 7 clean, 3 finding(s) (2 high / 1 medium / 0 low)
  [HIGH] booking_completion: the caller asked to book but never got a confirmation - the appointment silently dropped
    receipt:
      #3 agent: As an AI language model, I cannot access the patient database right now.
      #4 customer: Okay... so how do I book a cleaning?
      (cites the caller's booking ask and the agent's final turn (no confirmation))
  [HIGH] forbidden_phrases: agent said a forbidden phrase: 'as an ai language model'
    receipt:
      #3 agent: As an AI language model, I cannot access the patient database right now.
  [MEDIUM] abrupt_ending: call ended while the caller was still waiting on the agent
    receipt:
      #4 customer: Okay... so how do I book a cleaning?
```

Aggregate across a directory of calls:

```bash
dialproof report examples/
```

```
CALL                 SCORE  HIGH  MED  LOW  TOP ISSUE
-----------------------------------------------------
call_acme_clean        100     0    0    0  -
call_ridgeline_demo     10     3    3    0  booking_completion
call_sunrise_dental     50     2    1    0  booking_completion
-----------------------------------------------------
3 call(s) | avg score 53.3 | 9 finding(s): 5 high, 4 medium, 0 low
most common: booking_completion x2, abrupt_ending x2, interruption_recovery x1, opener_loop x1, dead_air x1, transfer_handling x1, forbidden_phrases x1
```

Machine-readable output and a CI gate:

```bash
dialproof audit calls/ --json > audit.json
dialproof audit calls/ --fail-under 80        # exit 1 if any call scores below 80
dialproof audit calls/ --checks greeting,booking_completion --forbidden "free of charge"
```

### Library

```python
from dialproof import audit

result = audit(open("examples/call_ridgeline_demo.json").read())

result.score                        # 10
result.findings[0].check            # "booking_completion"
result.findings[0].severity         # "high"
result.findings[0].receipt.lines    # the exact quoted transcript turns
```

## The default check suite

| Check | Severity | What it catches |
|---|---|---|
| `greeting` | medium* | Cold opens with no greeting (high if the agent never speaks) |
| `disclosure` | medium | Agent never identifies itself or the business |
| `opener_loop` | high | Agent repeats its opener after the caller spoke — state lost |
| `interruption_recovery` | high | A short caller barge-in sends the agent into confusion |
| `objection_handling` | medium | Caller objects ("too expensive", "not interested") and is steamrolled |
| `booking_completion` | high | Caller asks to book; no confirmation ever lands |
| `forbidden_phrases` | high | "As an AI language model..." and any phrase you configure |
| `dead_air` | medium | Silent gaps between timestamped turns (default > 6s) |
| `transfer_handling` | medium | "Can I talk to a human?" dead-ends |
| `abrupt_ending` | medium | Call ends while the caller is still waiting on an answer |

Scoring: every call starts at 100; each finding subtracts its severity weight (high 20, medium 10, low 4), floored at 0. The score is a triage signal — the receipts are the verdict.

### Add your own checks

```python
from dialproof import Finding, SEVERITY_LOW, audit, receipt_for, register_check

@register_check("mentions_competitor", "Agent name-drops a competitor.")
def mentions_competitor(transcript, config):
    for i, turn in enumerate(transcript.turns):
        if turn.role == "agent" and "megacorp" in turn.text.lower():
            return [Finding("mentions_competitor", SEVERITY_LOW,
                            "agent mentioned a competitor by name",
                            receipt_for(transcript, [i]))]
    return []

result = audit(open("call.json").read())   # new check runs automatically
```

Thresholds, forbidden phrases, vertical-specific objection patterns, and check subsets are all knobs on `AuditConfig`.

## The action gate

Auditing is read-only, but the production system this engine powers drives real side effects — probe calls, report emails. Every one of those goes through an `ActionGate`, and the gate's contract is the point:

```python
from dialproof import ARM_CONFIRMATION, ActionGate

gate = ActionGate("send-audit-report")
record = gate.submit("email_report", {"to": "qa-team@example.com"}, executor=send_it)
record.mode     # "DRY_RUN" — send_it was never called

gate.arm(confirm=ARM_CONFIRMATION)   # the literal string "ARM-LIVE", nothing else
record = gate.submit("email_report", {"to": "qa-team@example.com"}, executor=send_it)
record.mode     # "EXECUTED"
```

- **Dry-run is the default.** A fresh gate never executes anything.
- **Arming is explicit.** No environment variable or config file can arm a gate silently.
- **Everything is recorded.** Dry-runs, blocks, executions, and failures all land in `gate.history`.

## Transcript formats

- **JSON** — `{"call_id": ..., "turns": [{"role", "text", "t"}]}`, provider-style `messages` lists, or a bare list of turns.
- **Plain text** — `Speaker: text` lines with optional `[m:ss]` timestamps; unprefixed lines continue the previous utterance.
- **Auto-detect** is the default; roles normalize across providers (`assistant`/`bot`/`ai` → agent, `user`/`caller` → customer).

All example data in this repo is synthetic — fictional businesses, `555` numbers, `example.com` addresses.

## Design principles

- **Zero runtime dependencies.** Standard library only. `pip install` cannot break you.
- **Fully offline.** No network calls anywhere in the audit path; transcripts never leave your machine.
- **Receipts or it didn't happen.** Enforced by the type system, not by convention.
- **Conservative detection.** Under-fire rather than over-fire; every check ships with a negative test proving it stays quiet on clean calls.
- **Dry-run by default.** Anything that could touch the outside world is gated behind an explicit, unmistakable arming step.

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests/ -q     # 79 tests
ruff check .
python examples/audit_example.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add checks and formats, [CHANGELOG.md](CHANGELOG.md) for history, and [SECURITY.md](SECURITY.md) for the security policy.

## Roadmap

- [ ] Native VAPI / Retell / Bland transcript adapters
- [ ] Latency scoring from per-word timestamps
- [ ] CSV export for the aggregate report
- [ ] Configurable severity weights

## License

[MIT](LICENSE) © Denis Redzic

---

Part of the work of [Denis Redzic](https://denis.denisai.online).
