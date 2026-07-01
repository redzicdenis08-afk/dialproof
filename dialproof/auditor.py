"""The auditor: run a check suite over transcripts and score the result.

Scoring is deliberately simple and readable: every call starts at 100 and
each finding subtracts its severity weight (high 20, medium 10, low 4),
floored at 0. The number is a triage signal, not a verdict — the receipts
are the verdict.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Union

from dialproof.checks import AuditConfig, resolve_checks
from dialproof.models import MAX_SCORE, SEVERITY_ORDER, CallAudit, Finding, Transcript
from dialproof.parser import load_transcript, load_transcripts, parse_transcript


def score_findings(findings: Sequence[Finding]) -> int:
    """100 minus the summed severity weights, floored at 0."""
    return max(0, MAX_SCORE - sum(f.weight for f in findings))


class Auditor:
    """Runs a configurable check suite over transcripts.

    ``config.enabled_checks`` (or the ``checks`` argument) selects a subset of
    the registered checks; by default every registered check runs.
    """

    def __init__(
        self,
        config: Optional[AuditConfig] = None,
        checks: Optional[Sequence[str]] = None,
    ) -> None:
        self.config = config or AuditConfig()
        names = checks if checks is not None else self.config.enabled_checks
        self.checks = resolve_checks(names)

    def audit(self, transcript: Transcript) -> CallAudit:
        """Audit one parsed transcript."""
        if not transcript.turns:
            raise ValueError(
                f"transcript {transcript.call_id!r} has no turns; nothing to audit"
            )
        findings: List[Finding] = []
        for check in self.checks:
            findings.extend(check.func(transcript, self.config))
        findings.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.check))
        return CallAudit(
            call_id=transcript.call_id,
            source=transcript.source,
            score=score_findings(findings),
            findings=findings,
            checks_run=[c.name for c in self.checks],
        )

    def audit_text(self, content: str, fmt: str = "auto", call_id: Optional[str] = None) -> CallAudit:
        """Parse raw transcript content and audit it."""
        return self.audit(parse_transcript(content, fmt=fmt, call_id=call_id))

    def audit_file(self, path: Union[str, Path]) -> CallAudit:
        """Load and audit a single transcript file."""
        return self.audit(load_transcript(path))

    def audit_paths(self, paths: Iterable[Union[str, Path]]) -> List[CallAudit]:
        """Load and audit every transcript under the given files/directories."""
        return [self.audit(t) for t in load_transcripts(paths)]


def audit(
    content: Union[str, Transcript],
    fmt: str = "auto",
    config: Optional[AuditConfig] = None,
    checks: Optional[Sequence[str]] = None,
) -> CallAudit:
    """One-shot convenience: audit raw content or an already-parsed transcript."""
    auditor = Auditor(config=config, checks=checks)
    if isinstance(content, Transcript):
        return auditor.audit(content)
    return auditor.audit_text(content, fmt=fmt)
