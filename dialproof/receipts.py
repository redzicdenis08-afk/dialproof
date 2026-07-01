"""Receipts: the evidence behind every finding.

DialProof's signature rule is that no finding ships without a receipt — the
exact transcript lines that triggered it, quoted verbatim with turn numbers
and (when available) timestamps. A receipt lets a skeptical reader jump
straight from "your booking flow drops" to the two lines that prove it.

This module deliberately has no imports from the rest of the package so that
``models`` can depend on it without cycles.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence

EXCERPT_MAX_CHARS = 240


def format_timestamp(seconds: Any) -> str:
    """Render seconds-from-start as ``m:ss`` (or '' when unknown)."""
    if seconds is None:
        return ""
    try:
        total = int(float(seconds))
    except (TypeError, ValueError):
        return ""
    return f"{total // 60}:{total % 60:02d}"


@dataclass
class Receipt:
    """Verbatim transcript evidence for a finding.

    ``turn_indices`` are zero-based indices into ``Transcript.turns`` and
    ``lines`` are the human-readable rendered quotes, one per cited turn.
    """

    turn_indices: List[int] = field(default_factory=list)
    lines: List[str] = field(default_factory=list)
    note: str = ""

    def is_empty(self) -> bool:
        return not self.lines

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_indices": list(self.turn_indices),
            "lines": list(self.lines),
            "note": self.note,
        }


def format_turn(index: int, turn: Any) -> str:
    """Render one cited turn as ``#<n> [m:ss] role: text``."""
    stamp = format_timestamp(getattr(turn, "t", None))
    stamp_part = f" [{stamp}]" if stamp else ""
    text = " ".join((getattr(turn, "text", "") or "").split())
    if len(text) > EXCERPT_MAX_CHARS:
        text = text[: EXCERPT_MAX_CHARS - 3].rstrip() + "..."
    return f"#{index + 1}{stamp_part} {getattr(turn, 'role', '?')}: {text}"


def receipt_for(transcript: Any, indices: Sequence[int], note: str = "") -> Receipt:
    """Build a receipt citing ``indices`` (zero-based) of ``transcript.turns``.

    Raises ``IndexError`` for out-of-range indices — a check citing lines that
    do not exist is a bug worth failing loudly on.
    """
    turns = transcript.turns
    cited = sorted(set(int(i) for i in indices))
    for i in cited:
        if i < 0 or i >= len(turns):
            raise IndexError(f"receipt cites turn {i}, but transcript has {len(turns)} turns")
    return Receipt(
        turn_indices=cited,
        lines=[format_turn(i, turns[i]) for i in cited],
        note=note,
    )
