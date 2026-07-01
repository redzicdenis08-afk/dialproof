"""Transcript parsing: JSON, plain text, and auto-detection.

Two source shapes are supported out of the box:

* **JSON** — an object with a ``turns`` list (``{"role", "text", "t"}``), a
  provider-style ``messages`` list (``{"role", "message"|"content",
  "secondsFromStart"}``), or a bare top-level list of either shape.
* **Plain text** — one utterance per line as ``Speaker: text``, with an
  optional leading ``[m:ss]`` timestamp. Unprefixed lines continue the
  previous utterance.

Roles normalize across providers: ``assistant`` / ``bot`` / ``ai`` map to
*agent*; ``user`` / ``caller`` / ``customer`` / ``human`` map to *customer*.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from dialproof.models import AGENT, CUSTOMER, Transcript, Turn

_ROLE_MAP = {
    "agent": AGENT,
    "assistant": AGENT,
    "bot": AGENT,
    "ai": AGENT,
    "receptionist": AGENT,
    "customer": CUSTOMER,
    "user": CUSTOMER,
    "caller": CUSTOMER,
    "human": CUSTOMER,
    "prospect": CUSTOMER,
    "lead": CUSTOMER,
}

_TEXT_LINE = re.compile(
    r"^\s*(?:\[(?P<min>\d+):(?P<sec>\d{2}(?:\.\d+)?)\]\s*)?"
    r"(?P<role>[A-Za-z][A-Za-z _-]{0,24}):\s*(?P<text>.*\S)\s*$"
)

TRANSCRIPT_SUFFIXES = (".json", ".txt")


class ParseError(ValueError):
    """Raised when content cannot be interpreted as a transcript."""


def normalize_role(raw: Optional[str]) -> str:
    return _ROLE_MAP.get((raw or "").strip().lower(), CUSTOMER)


def _coerce_time(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _turn_from_obj(obj: Dict[str, Any]) -> Optional[Turn]:
    text = obj.get("text") or obj.get("message") or obj.get("content") or ""
    if not str(text).strip():
        return None
    t = _coerce_time(obj.get("t"))
    if t is None:
        t = _coerce_time(obj.get("secondsFromStart"))
    return Turn(role=normalize_role(obj.get("role") or obj.get("speaker")), text=str(text).strip(), t=t)


def parse_json(content: str, call_id: Optional[str] = None) -> Transcript:
    """Parse a JSON transcript (object with ``turns``/``messages`` or a list)."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ParseError(f"invalid JSON: {exc}") from exc

    if isinstance(data, dict):
        raw_turns = data.get("turns") or data.get("messages") or []
        call_id = data.get("call_id") or data.get("id") or call_id
    elif isinstance(data, list):
        raw_turns = data
    else:
        raise ParseError("JSON transcript must be an object or a list of turns")

    if not isinstance(raw_turns, list):
        raise ParseError("'turns' / 'messages' must be a list")

    turns = [t for t in (_turn_from_obj(o) for o in raw_turns if isinstance(o, dict)) if t]
    return Transcript(turns=turns, call_id=call_id, source="json")


def parse_text(content: str, call_id: Optional[str] = None) -> Transcript:
    """Parse a plain-text ``Speaker: text`` transcript."""
    turns: List[Turn] = []
    for line in content.splitlines():
        if not line.strip():
            continue
        match = _TEXT_LINE.match(line)
        if match:
            t: Optional[float] = None
            if match.group("min") is not None:
                t = int(match.group("min")) * 60 + float(match.group("sec"))
            turns.append(Turn(role=normalize_role(match.group("role")), text=match.group("text"), t=t))
        elif turns:
            turns[-1].text = f"{turns[-1].text} {line.strip()}"
    return Transcript(turns=turns, call_id=call_id, source="text")


def parse_transcript(content: str, fmt: str = "auto", call_id: Optional[str] = None) -> Transcript:
    """Parse transcript ``content`` in the given format (``json``/``text``/``auto``)."""
    if fmt == "json":
        return parse_json(content, call_id=call_id)
    if fmt == "text":
        return parse_text(content, call_id=call_id)
    if fmt != "auto":
        raise ParseError(f"unknown format {fmt!r}; expected 'json', 'text', or 'auto'")
    stripped = content.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            return parse_json(content, call_id=call_id)
        except ParseError:
            # e.g. plain text opening with a "[0:05]" timestamp
            return parse_text(content, call_id=call_id)
    return parse_text(content, call_id=call_id)


def load_transcript(path: Union[str, Path]) -> Transcript:
    """Load one transcript file; the filename stem becomes the fallback call id."""
    p = Path(path)
    fmt = "json" if p.suffix.lower() == ".json" else "text" if p.suffix.lower() == ".txt" else "auto"
    transcript = parse_transcript(p.read_text(encoding="utf-8"), fmt=fmt, call_id=p.stem)
    if not transcript.call_id:
        transcript.call_id = p.stem
    return transcript


def collect_transcript_paths(paths: Iterable[Union[str, Path]]) -> List[Path]:
    """Expand files and directories into a sorted list of transcript files."""
    found: List[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            found.extend(
                child
                for child in sorted(p.iterdir())
                if child.is_file() and child.suffix.lower() in TRANSCRIPT_SUFFIXES
            )
        elif p.is_file():
            found.append(p)
        else:
            raise FileNotFoundError(f"no such file or directory: {p}")
    return found


def load_transcripts(paths: Iterable[Union[str, Path]]) -> List[Transcript]:
    """Load every transcript under the given files/directories."""
    return [load_transcript(p) for p in collect_transcript_paths(paths)]
