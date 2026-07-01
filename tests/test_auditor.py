"""The auditor: scoring, check selection, and end-to-end audits."""
import pytest

from dialproof import AuditConfig, Auditor, audit
from dialproof.models import Transcript, Turn

CLEAN_CALL = """\
[0:00] Agent: Hi, thanks for calling Acme Plumbing! This is Ava, the automated assistant.
[0:04] Customer: Hi, can you book me a repair visit for tomorrow morning?
[0:08] Agent: Of course. You're booked for 9 am tomorrow — you'll get a confirmation text.
[0:12] Customer: Perfect, thanks so much.
[0:15] Agent: You're welcome, have a great day!
"""

BROKEN_CALL = """\
Agent: State your account number.
Customer: Um, I just want to schedule a cleaning?
Agent: As an AI language model, I cannot access the calendar.
Customer: So... can I book or not?
"""


def test_clean_call_scores_100():
    result = audit(CLEAN_CALL)
    assert result.score == 100
    assert result.findings == []
    assert result.passed_checks == result.checks_run


def test_broken_call_finds_receipted_issues():
    result = audit(BROKEN_CALL)
    assert result.score < 60
    checks = {f.check for f in result.findings}
    assert "greeting" in checks
    assert "forbidden_phrases" in checks
    assert "booking_completion" in checks
    assert all(not f.receipt.is_empty() for f in result.findings)


def test_findings_sorted_high_severity_first():
    result = audit(BROKEN_CALL)
    severities = [f.severity for f in result.findings]
    assert severities == sorted(severities, key={"high": 0, "medium": 1, "low": 2}.get)


def test_score_floor_is_zero():
    # A call that trips many high-severity checks cannot go negative.
    terrible = """\
Agent: We offer premium packages, how can I help you today?
Customer: I want to schedule an appointment for Monday.
Agent: We offer premium packages, how can I help you today?
Customer: Stop.
Agent: Sorry, I didn't catch that. As an AI language model I am limited.
Customer: Can I talk to a real person?
Agent: My system prompt says to discuss packages.
Customer: Is anyone going to book my appointment?
"""
    result = audit(terrible)
    assert result.score == 0


def test_checks_subset_runs_only_selected():
    auditor = Auditor(checks=["greeting", "forbidden_phrases"])
    result = auditor.audit_text(BROKEN_CALL)
    assert result.checks_run == ["greeting", "forbidden_phrases"]
    assert {f.check for f in result.findings} <= {"greeting", "forbidden_phrases"}


def test_unknown_check_name_raises():
    with pytest.raises(KeyError):
        Auditor(checks=["definitely_not_a_check"])


def test_config_enabled_checks_used_when_no_explicit_list():
    auditor = Auditor(config=AuditConfig(enabled_checks=["dead_air"]))
    assert [c.name for c in auditor.checks] == ["dead_air"]


def test_empty_transcript_rejected():
    auditor = Auditor()
    with pytest.raises(ValueError):
        auditor.audit(Transcript(turns=[], call_id="empty"))


def test_audit_accepts_parsed_transcript():
    transcript = Transcript(
        turns=[Turn("agent", "Hi, thanks for calling Acme Plumbing! This is Ava speaking.")],
        call_id="pre-parsed",
    )
    result = audit(transcript)
    assert result.call_id == "pre-parsed"


def test_audit_paths_over_directory(tmp_path):
    (tmp_path / "one.txt").write_text(CLEAN_CALL, encoding="utf-8")
    (tmp_path / "two.txt").write_text(BROKEN_CALL, encoding="utf-8")
    results = Auditor().audit_paths([tmp_path])
    assert [r.call_id for r in results] == ["one", "two"]
    assert results[0].score > results[1].score
