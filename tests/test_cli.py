"""The command-line interface, end to end via main()."""
import json

import pytest

from dialproof.cli import EXIT_ERROR, EXIT_FAIL_UNDER, EXIT_OK, main

CLEAN = """\
Agent: Hi, thanks for calling Acme Plumbing! This is Ava, the automated assistant.
Customer: Just confirming you're open Saturday?
Agent: We are — eight to six on Saturdays. Anything else?
Customer: Nope, all good, thanks.
Agent: Have a great day!
"""

BROKEN = """\
Agent: State your account number.
Customer: I want to book a cleaning?
Agent: As an AI language model, I cannot access the calendar.
Customer: So can I book or not?
"""


@pytest.fixture()
def calls_dir(tmp_path):
    (tmp_path / "clean.txt").write_text(CLEAN, encoding="utf-8")
    (tmp_path / "broken.txt").write_text(BROKEN, encoding="utf-8")
    return tmp_path


def test_audit_text_output(calls_dir, capsys):
    code = main(["audit", str(calls_dir)])
    out = capsys.readouterr().out
    assert code == EXIT_OK
    assert "clean" in out and "broken" in out
    assert "receipt:" in out
    assert "avg score" in out


def test_audit_json_output(calls_dir, capsys):
    code = main(["audit", str(calls_dir), "--json"])
    assert code == EXIT_OK
    data = json.loads(capsys.readouterr().out)
    assert isinstance(data, list) and len(data) == 2
    broken = next(a for a in data if a["call_id"] == "broken")
    assert any(f["check"] == "forbidden_phrases" for f in broken["findings"])
    assert all(f["receipt"]["lines"] for a in data for f in a["findings"])


def test_report_json_output(calls_dir, capsys):
    code = main(["report", str(calls_dir), "--json"])
    assert code == EXIT_OK
    data = json.loads(capsys.readouterr().out)
    assert data["call_count"] == 2
    assert data["findings_by_check"]


def test_report_text_summary(calls_dir, capsys):
    code = main(["report", str(calls_dir)])
    out = capsys.readouterr().out
    assert code == EXIT_OK
    assert "CALL" in out and "2 call(s)" in out


def test_fail_under_gates_exit_code(calls_dir, capsys):
    assert main(["audit", str(calls_dir), "--fail-under", "90"]) == EXIT_FAIL_UNDER
    capsys.readouterr()
    assert main(["audit", str(calls_dir), "--fail-under", "10"]) == EXIT_OK


def test_checks_flag_limits_suite(calls_dir, capsys):
    code = main(["audit", str(calls_dir), "--checks", "greeting,dead_air", "--json"])
    assert code == EXIT_OK
    data = json.loads(capsys.readouterr().out)
    assert data[0]["checks_run"] == ["greeting", "dead_air"]


def test_unknown_check_is_an_error(calls_dir, capsys):
    assert main(["audit", str(calls_dir), "--checks", "nope"]) == EXIT_ERROR
    assert "unknown check" in capsys.readouterr().err


def test_missing_path_is_an_error(capsys):
    assert main(["audit", "no_such_dir_here"]) == EXIT_ERROR
    assert "error" in capsys.readouterr().err


def test_custom_forbidden_phrase_flag(calls_dir, capsys):
    code = main(["audit", str(calls_dir), "--forbidden", "eight to six", "--json"])
    assert code == EXIT_OK
    data = json.loads(capsys.readouterr().out)
    clean = next(a for a in data if a["call_id"] == "clean")
    assert any(
        f["check"] == "forbidden_phrases" and "eight to six" in f["message"]
        for f in clean["findings"]
    )
