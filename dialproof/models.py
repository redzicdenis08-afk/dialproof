"""Core data structures for dialproof.

Everything downstream (checks, auditor, report, CLI) speaks in terms of these
types. A ``Transcript`` is a normalized list of ``Turn`` objects; an audit
produces ``Finding`` objects, and every finding is required — at the type
level — to carry a :class:`~dialproof.receipts.Receipt`.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from dialproof.receipts import Receipt

# Normalized speaker roles.
AGENT = "agent"
CUSTOMER = "customer"

# Severity levels and how much each finding subtracts from a call's score.
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"

SEVERITY_WEIGHTS: Dict[str, int] = {
    SEVERITY_HIGH: 20,
    SEVERITY_MEDIUM: 10,
    SEVERITY_LOW: 4,
}

# For stable sorting: high first.
SEVERITY_ORDER: Dict[str, int] = {SEVERITY_HIGH: 0, SEVERITY_MEDIUM: 1, SEVERITY_LOW: 2}

MAX_SCORE = 100


@dataclass
class Turn:
    """A single utterance in a call.

    ``t`` is the utterance start time in seconds from the beginning of the
    call, when the source format provides it. Timing-based checks (dead air,
    latency) quietly skip turns without timestamps.
    """

    role: str
    text: str
    t: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Transcript:
    """A parsed, provider-agnostic call transcript."""

    turns: List[Turn] = field(default_factory=list)
    call_id: Optional[str] = None
    source: str = "unknown"

    @property
    def agent_turns(self) -> List[Turn]:
        return [t for t in self.turns if t.role == AGENT]

    @property
    def customer_turns(self) -> List[Turn]:
        return [t for t in self.turns if t.role == CUSTOMER]

    def duration(self) -> Optional[float]:
        """Best-effort call duration from turn timestamps, or None."""
        stamps = [t.t for t in self.turns if t.t is not None]
        if len(stamps) < 2:
            return None
        return max(stamps) - min(stamps)


@dataclass
class Finding:
    """One QA issue detected in one call.

    A finding without evidence is an accusation, not a finding — so a
    ``Receipt`` is mandatory and must be non-empty. This is enforced here
    rather than by convention.
    """

    check: str
    severity: str
    message: str
    receipt: Receipt

    def __post_init__(self) -> None:
        if self.severity not in SEVERITY_WEIGHTS:
            raise ValueError(
                f"unknown severity {self.severity!r}; expected one of {sorted(SEVERITY_WEIGHTS)}"
            )
        if not isinstance(self.receipt, Receipt) or self.receipt.is_empty():
            raise ValueError(
                f"finding {self.check!r} has no receipt; every finding must cite "
                "the transcript lines that triggered it"
            )

    @property
    def weight(self) -> int:
        return SEVERITY_WEIGHTS[self.severity]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check": self.check,
            "severity": self.severity,
            "message": self.message,
            "receipt": self.receipt.to_dict(),
        }


@dataclass
class CallAudit:
    """The full audit result for a single call."""

    call_id: Optional[str]
    source: str
    score: int
    findings: List[Finding]
    checks_run: List[str]

    @property
    def passed_checks(self) -> List[str]:
        failed = {f.check for f in self.findings}
        return [name for name in self.checks_run if name not in failed]

    @property
    def failed_checks(self) -> List[str]:
        failed = {f.check for f in self.findings}
        return [name for name in self.checks_run if name in failed]

    def findings_by_severity(self) -> Dict[str, int]:
        counts = {SEVERITY_HIGH: 0, SEVERITY_MEDIUM: 0, SEVERITY_LOW: 0}
        for f in self.findings:
            counts[f.severity] += 1
        return counts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_id": self.call_id,
            "source": self.source,
            "score": self.score,
            "findings": [f.to_dict() for f in self.findings],
            "checks_run": list(self.checks_run),
            "passed_checks": self.passed_checks,
        }
