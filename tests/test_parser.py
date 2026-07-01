"""Parsing: JSON shapes, plain text, auto-detection, and file loading."""
import json

import pytest

from dialproof.parser import (
    ParseError,
    collect_transcript_paths,
    load_transcript,
    load_transcripts,
    parse_transcript,
)


def test_json_turns_shape():
    content = json.dumps(
        {
            "call_id": "call_001",
            "turns": [
                {"role": "agent", "text": "Hi, thanks for calling Acme Plumbing!", "t": 0},
                {"role": "customer", "text": "Hello, I need a quote.", "t": 3.5},
            ],
        }
    )
    t = parse_transcript(content, fmt="json")
    assert t.call_id == "call_001"
    assert [turn.role for turn in t.turns] == ["agent", "customer"]
    assert t.turns[1].t == 3.5


def test_json_provider_messages_shape():
    content = json.dumps(
        {
            "id": "call_002",
            "messages": [
                {"role": "assistant", "message": "Hello there!", "secondsFromStart": 0},
                {"role": "user", "content": "Hi.", "secondsFromStart": 2},
            ],
        }
    )
    t = parse_transcript(content, fmt="json")
    assert t.call_id == "call_002"
    assert t.turns[0].role == "agent"
    assert t.turns[1].role == "customer"
    assert t.turns[1].t == 2.0


def test_json_bare_list():
    content = json.dumps([{"role": "bot", "text": "Welcome to Acme."}])
    t = parse_transcript(content, fmt="json")
    assert len(t.turns) == 1
    assert t.turns[0].role == "agent"


def test_json_skips_empty_turns():
    content = json.dumps({"turns": [{"role": "agent", "text": "  "}, {"role": "user", "text": "Hi"}]})
    t = parse_transcript(content, fmt="json")
    assert len(t.turns) == 1


def test_invalid_json_raises_parse_error():
    with pytest.raises(ParseError):
        parse_transcript("{not json", fmt="json")


def test_json_scalar_raises_parse_error():
    with pytest.raises(ParseError):
        parse_transcript("42", fmt="json")


def test_text_with_timestamps_and_continuation():
    content = (
        "[0:05] Agent: Hi, thanks for calling Acme Plumbing.\n"
        "[0:09] Customer: My sink is clogged\n"
        "and it's getting worse.\n"
    )
    t = parse_transcript(content, fmt="text")
    assert len(t.turns) == 2
    assert t.turns[0].t == 5.0
    assert t.turns[1].text == "My sink is clogged and it's getting worse."


def test_text_role_normalization():
    t = parse_transcript("AI: Hello\nCaller: Hi\n", fmt="text")
    assert t.turns[0].role == "agent"
    assert t.turns[1].role == "customer"


def test_auto_detect_json_vs_text():
    as_json = parse_transcript('{"turns": [{"role": "agent", "text": "Hi"}]}')
    as_text = parse_transcript("Agent: Hi\n")
    assert as_json.source == "json"
    assert as_text.source == "text"


def test_auto_detect_timestamped_text_despite_leading_bracket():
    t = parse_transcript("[0:03] Agent: Hi, thanks for calling Acme Plumbing!\n")
    assert t.source == "text"
    assert t.turns[0].t == 3.0


def test_load_transcript_uses_filename_stem_as_call_id(tmp_path):
    path = tmp_path / "call_demo.txt"
    path.write_text("Agent: Hello!\n", encoding="utf-8")
    t = load_transcript(path)
    assert t.call_id == "call_demo"


def test_collect_paths_expands_directories_and_skips_other_suffixes(tmp_path):
    (tmp_path / "a.json").write_text('{"turns": [{"role": "agent", "text": "Hi"}]}', encoding="utf-8")
    (tmp_path / "b.txt").write_text("Agent: Hi\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("not a transcript", encoding="utf-8")
    paths = collect_transcript_paths([tmp_path])
    assert [p.name for p in paths] == ["a.json", "b.txt"]
    assert len(load_transcripts([tmp_path])) == 2


def test_missing_path_raises():
    with pytest.raises(FileNotFoundError):
        collect_transcript_paths(["does_not_exist_anywhere"])
