"""dialproof — receipt-backed QA audits for AI voice-agent call transcripts.

Public API::

    from dialproof import audit, Auditor, AuditConfig

    result = audit(open("call.json").read())
    result.score                     # 0-100
    result.findings[0].message      # what went wrong
    result.findings[0].receipt      # the exact lines that prove it
"""
from dialproof.auditor import Auditor, audit, score_findings
from dialproof.checks import (
    CHECKS,
    DEFAULT_FORBIDDEN_PHRASES,
    AuditConfig,
    register_check,
    resolve_checks,
)
from dialproof.gate import (
    ARM_CONFIRMATION,
    ActionGate,
    ActionRecord,
    GateError,
)
from dialproof.models import (
    AGENT,
    CUSTOMER,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    SEVERITY_WEIGHTS,
    CallAudit,
    Finding,
    Transcript,
    Turn,
)
from dialproof.parser import (
    ParseError,
    load_transcript,
    load_transcripts,
    parse_transcript,
)
from dialproof.receipts import Receipt, receipt_for
from dialproof.report import (
    AggregateReport,
    render_call_text,
    render_report,
    render_summary_text,
)

__version__ = "0.1.0"

__all__ = [
    "AGENT",
    "ARM_CONFIRMATION",
    "CHECKS",
    "CUSTOMER",
    "DEFAULT_FORBIDDEN_PHRASES",
    "SEVERITY_HIGH",
    "SEVERITY_LOW",
    "SEVERITY_MEDIUM",
    "SEVERITY_WEIGHTS",
    "ActionGate",
    "ActionRecord",
    "AggregateReport",
    "AuditConfig",
    "Auditor",
    "CallAudit",
    "Finding",
    "GateError",
    "ParseError",
    "Receipt",
    "Transcript",
    "Turn",
    "__version__",
    "audit",
    "load_transcript",
    "load_transcripts",
    "parse_transcript",
    "receipt_for",
    "register_check",
    "render_call_text",
    "render_report",
    "render_summary_text",
    "resolve_checks",
    "score_findings",
]
