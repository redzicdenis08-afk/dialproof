"""Aggregate reporting and text rendering."""
from dialproof import Auditor
from dialproof.report import AggregateReport, render_call_text, render_report, render_summary_text

GOOD = """\
Agent: Hi, thanks for calling Acme Plumbing! This is Ava, the automated assistant.
Customer: Just checking your hours.
Agent: We're open eight to six, Monday through Saturday.
Customer: Great, thanks!
"""

BAD = """\
Agent: Hi, you've reached Acme Plumbing, this is Ava.
Customer: I want to schedule a visit for tomorrow.
Agent: As an AI language model, I cannot do that.
Customer: Seriously? Can I talk to a real person?
Agent: Our website has more information.
"""


def _audits():
    auditor = Auditor()
    return [
        auditor.audit_text(GOOD, call_id="call_good"),
        auditor.audit_text(BAD, call_id="call_bad"),
    ]


def test_aggregate_counts_and_average():
    report = AggregateReport(_audits())
    assert report.call_count == 2
    assert report.total_findings > 0
    assert 0 < report.average_score < 100
    assert report.worst_calls(1)[0].call_id == "call_bad"


def test_findings_by_check_and_severity():
    report = AggregateReport(_audits())
    by_check = report.findings_by_check()
    assert by_check.get("forbidden_phrases") == 1
    by_sev = report.findings_by_severity()
    assert by_sev["high"] >= 2
    assert sum(by_sev.values()) == report.total_findings


def test_render_call_text_includes_receipts():
    good, bad = _audits()
    text = render_call_text(bad)
    assert "call_bad" in text
    assert "FAIL" in text
    assert "receipt:" in text
    assert "As an AI language model" in text  # verbatim quote
    clean = render_call_text(good)
    assert "PASS" in clean
    assert "no findings" in clean


def test_render_summary_table():
    text = render_summary_text(AggregateReport(_audits()))
    assert "CALL" in text and "SCORE" in text
    assert "call_good" in text and "call_bad" in text
    assert "2 call(s)" in text
    assert "most common:" in text


def test_render_summary_empty():
    assert render_summary_text(AggregateReport([])) == "no calls audited"


def test_render_report_combines_detail_and_summary():
    text = render_report(_audits())
    assert text.count("receipt:") >= 1
    assert "avg score" in text


def test_report_to_dict_shape():
    d = AggregateReport(_audits()).to_dict()
    assert set(d) == {
        "call_count",
        "average_score",
        "total_findings",
        "findings_by_check",
        "findings_by_severity",
        "calls",
    }
    assert d["call_count"] == 2
    assert d["calls"][1]["call_id"] == "call_bad"
