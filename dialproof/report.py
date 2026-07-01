"""Reporting: per-call detail and the aggregate roll-up.

Two renderers, both pure functions over audit results:

* :func:`render_call_text` — one call, every finding, every receipt.
* :func:`render_summary_text` — the table you scan first across many calls.

Both have JSON twins via ``CallAudit.to_dict`` / ``AggregateReport.to_dict``.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from dialproof.models import (
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    CallAudit,
)

PASS_SCORE = 80  # a call at or above this is "pass" in the summary column


@dataclass
class AggregateReport:
    """A roll-up of many call audits."""

    audits: List[CallAudit]

    @property
    def call_count(self) -> int:
        return len(self.audits)

    @property
    def average_score(self) -> float:
        if not self.audits:
            return 0.0
        return sum(a.score for a in self.audits) / len(self.audits)

    @property
    def total_findings(self) -> int:
        return sum(len(a.findings) for a in self.audits)

    def findings_by_check(self) -> Dict[str, int]:
        counter: Counter = Counter()
        for audit in self.audits:
            counter.update(f.check for f in audit.findings)
        return dict(counter.most_common())

    def findings_by_severity(self) -> Dict[str, int]:
        counts = {SEVERITY_HIGH: 0, SEVERITY_MEDIUM: 0, SEVERITY_LOW: 0}
        for audit in self.audits:
            for f in audit.findings:
                counts[f.severity] += 1
        return counts

    def worst_calls(self, limit: int = 5) -> List[CallAudit]:
        return sorted(self.audits, key=lambda a: (a.score, a.call_id or ""))[:limit]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_count": self.call_count,
            "average_score": round(self.average_score, 1),
            "total_findings": self.total_findings,
            "findings_by_check": self.findings_by_check(),
            "findings_by_severity": self.findings_by_severity(),
            "calls": [a.to_dict() for a in self.audits],
        }


def render_call_text(audit: CallAudit) -> str:
    """Render one call audit with every finding and its receipt."""
    sev = audit.findings_by_severity()
    verdict = "PASS" if audit.score >= PASS_SCORE else "FAIL"
    lines = [
        f"{audit.call_id or 'unnamed-call'}  score {audit.score}/100  {verdict}",
        f"  checks: {len(audit.checks_run)} run, {len(audit.passed_checks)} clean, "
        f"{len(audit.findings)} finding(s) "
        f"({sev[SEVERITY_HIGH]} high / {sev[SEVERITY_MEDIUM]} medium / {sev[SEVERITY_LOW]} low)",
    ]
    for finding in audit.findings:
        lines.append(f"  [{finding.severity.upper()}] {finding.check}: {finding.message}")
        lines.append("    receipt:")
        for quoted in finding.receipt.lines:
            lines.append(f"      {quoted}")
        if finding.receipt.note:
            lines.append(f"      ({finding.receipt.note})")
    if not audit.findings:
        lines.append("  no findings - clean call")
    return "\n".join(lines)


def render_summary_text(report: AggregateReport) -> str:
    """Render the aggregate table across calls."""
    if not report.audits:
        return "no calls audited"

    name_width = max(len(a.call_id or "unnamed-call") for a in report.audits)
    name_width = max(name_width, len("CALL"))
    header = f"{'CALL':<{name_width}}  SCORE  HIGH  MED  LOW  TOP ISSUE"
    rule = "-" * len(header)
    lines = [header, rule]
    for audit in report.audits:
        sev = audit.findings_by_severity()
        top = audit.findings[0].check if audit.findings else "-"
        lines.append(
            f"{(audit.call_id or 'unnamed-call'):<{name_width}}  "
            f"{audit.score:>5}  {sev[SEVERITY_HIGH]:>4}  {sev[SEVERITY_MEDIUM]:>3}  "
            f"{sev[SEVERITY_LOW]:>3}  {top}"
        )
    lines.append(rule)
    sev = report.findings_by_severity()
    lines.append(
        f"{report.call_count} call(s) | avg score {report.average_score:.1f} | "
        f"{report.total_findings} finding(s): {sev[SEVERITY_HIGH]} high, "
        f"{sev[SEVERITY_MEDIUM]} medium, {sev[SEVERITY_LOW]} low"
    )
    by_check = report.findings_by_check()
    if by_check:
        ranked = ", ".join(f"{name} x{count}" for name, count in by_check.items())
        lines.append(f"most common: {ranked}")
    return "\n".join(lines)


def render_report(audits: Sequence[CallAudit]) -> str:
    """Full text report: per-call detail followed by the aggregate summary."""
    report = AggregateReport(list(audits))
    blocks = [render_call_text(a) for a in report.audits]
    blocks.append(render_summary_text(report))
    return "\n\n".join(blocks)
