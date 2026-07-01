"""Library usage example: audit the bundled synthetic calls.

Run from the repository root::

    python examples/audit_example.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, if not installed

from dialproof import (  # noqa: E402
    ActionGate,
    AuditConfig,
    Auditor,
    render_call_text,
    render_summary_text,
)
from dialproof.report import AggregateReport  # noqa: E402

EXAMPLES_DIR = Path(__file__).parent


def main() -> None:
    # 1. Audit every transcript in this directory (JSON and plain text).
    auditor = Auditor(
        config=AuditConfig(
            dead_air_seconds=6.0,
            forbidden_phrases=AuditConfig().forbidden_phrases + ("we guarantee results",),
        )
    )
    audits = auditor.audit_paths([EXAMPLES_DIR])

    # 2. Per-call detail: every finding carries a receipt (the exact lines).
    for audit in audits:
        print(render_call_text(audit))
        print()

    # 3. Aggregate roll-up across the batch.
    print(render_summary_text(AggregateReport(audits)))
    print()

    # 4. Anything outbound goes through a gate: dry-run unless explicitly armed.
    gate = ActionGate("send-audit-report")
    record = gate.submit(
        "email_report",
        payload={"to": "qa-team@example.com", "calls": len(audits)},
    )
    print(f"gate[{gate.name}] {record.mode}: {record.detail}")


if __name__ == "__main__":
    main()
