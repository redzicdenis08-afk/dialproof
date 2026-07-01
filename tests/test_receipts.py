"""Receipts: every finding must carry verbatim, in-range evidence."""
import pytest

from dialproof.models import Finding, Transcript, Turn
from dialproof.receipts import Receipt, format_timestamp, format_turn, receipt_for


def _transcript():
    return Transcript(
        turns=[
            Turn("agent", "Hi, thanks for calling Acme Plumbing!", t=0),
            Turn("customer", "Hi, I'd like to book a visit.", t=4),
            Turn("agent", "Of course, what day works?", t=7),
        ],
        call_id="call_x",
    )


def test_receipt_quotes_cited_turns_in_order():
    r = receipt_for(_transcript(), [2, 0])
    assert r.turn_indices == [0, 2]
    assert r.lines[0] == "#1 [0:00] agent: Hi, thanks for calling Acme Plumbing!"
    assert r.lines[1] == "#3 [0:07] agent: Of course, what day works?"


def test_receipt_out_of_range_raises():
    with pytest.raises(IndexError):
        receipt_for(_transcript(), [99])


def test_finding_requires_nonempty_receipt():
    with pytest.raises(ValueError):
        Finding("greeting", "high", "no receipt here", Receipt())


def test_finding_rejects_unknown_severity():
    r = receipt_for(_transcript(), [0])
    with pytest.raises(ValueError):
        Finding("greeting", "catastrophic", "bad severity", r)


def test_format_turn_truncates_long_text():
    turn = Turn("agent", "word " * 100)
    line = format_turn(0, turn)
    assert len(line) < 280
    assert line.endswith("...")


def test_format_timestamp():
    assert format_timestamp(0) == "0:00"
    assert format_timestamp(75.4) == "1:15"
    assert format_timestamp(None) == ""
    assert format_timestamp("nope") == ""


def test_receipt_round_trips_to_dict():
    r = receipt_for(_transcript(), [1], note="the booking ask")
    d = r.to_dict()
    assert d["turn_indices"] == [1]
    assert d["note"] == "the booking ask"
    assert "book a visit" in d["lines"][0]
