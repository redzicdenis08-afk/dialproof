"""The QA check registry.

Each check is a plain function ``(transcript, config) -> list[Finding]``
registered under a stable name. The default suite encodes the failure modes
that actually kill real voice-agent deployments: opener loops, dropped
bookings, dead transfers, un-acknowledged objections, dead air, raw-LLM
leakage, and calls that end mid-conversation.

Checks are conservative by design. A false "your agent is broken" costs far
more trust than a miss, so every pattern here should only fire on strong
signal — and every finding must cite the exact turns that triggered it.

Add your own::

    from dialproof.checks import register_check
    from dialproof.receipts import receipt_for
    from dialproof.models import Finding, SEVERITY_LOW

    @register_check("mentions_weather", "Agent small-talks about the weather.")
    def mentions_weather(transcript, config):
        for i, turn in enumerate(transcript.turns):
            if turn.role == "agent" and "weather" in turn.text.lower():
                return [Finding("mentions_weather", SEVERITY_LOW,
                                "agent drifted into weather small talk",
                                receipt_for(transcript, [i]))]
        return []
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from dialproof.models import (
    AGENT,
    CUSTOMER,
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    Finding,
    Transcript,
)
from dialproof.receipts import receipt_for

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_FORBIDDEN_PHRASES: Tuple[str, ...] = (
    "as an ai language model",
    "as a language model",
    "large language model",
    "my system prompt",
    "my instructions say",
    "i am not able to browse",
)


@dataclass
class AuditConfig:
    """Tunable knobs for the default check suite."""

    # Phrases an agent must never say on a live call (case-insensitive substrings).
    forbidden_phrases: Tuple[str, ...] = DEFAULT_FORBIDDEN_PHRASES
    # A silence between consecutive timestamped turns longer than this is dead air.
    dead_air_seconds: float = 6.0
    # The agent must greet within its first turn...
    greeting_turns: int = 1
    # ...and identify itself / the business within its first N turns.
    disclosure_turns: int = 3
    # A customer turn shorter than this counts as an interruption/barge-in.
    interruption_max_chars: int = 25
    # Run only these checks (None = all registered checks).
    enabled_checks: Optional[Sequence[str]] = None
    # Extra objection patterns for your vertical, merged with the defaults.
    extra_objection_patterns: Tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

CheckFunc = Callable[[Transcript, AuditConfig], List[Finding]]


@dataclass(frozen=True)
class Check:
    name: str
    description: str
    func: CheckFunc


CHECKS: Dict[str, Check] = {}


def register_check(name: str, description: str) -> Callable[[CheckFunc], CheckFunc]:
    """Register a check function under ``name`` (overwrites any existing one)."""

    def decorator(func: CheckFunc) -> CheckFunc:
        CHECKS[name] = Check(name=name, description=description, func=func)
        return func

    return decorator


def resolve_checks(names: Optional[Sequence[str]] = None) -> List[Check]:
    """Return the checks to run, validating unknown names loudly."""
    if names is None:
        return list(CHECKS.values())
    resolved = []
    for name in names:
        if name not in CHECKS:
            known = ", ".join(sorted(CHECKS))
            raise KeyError(f"unknown check {name!r}; registered checks: {known}")
        resolved.append(CHECKS[name])
    return resolved


# ---------------------------------------------------------------------------
# Shared language patterns (compiled once, deliberately conservative)
# ---------------------------------------------------------------------------

GREETING = re.compile(
    r"\b(hi|hello|hey|good\s+(morning|afternoon|evening)|thanks?\s+for\s+calling"
    r"|welcome\s+to|you'?ve\s+reached)\b",
    re.I,
)
OPENER = re.compile(
    r"\b(how\s+(can|may)\s+i\s+help|what\s+can\s+i\s+(do|help)"
    r"|thanks?\s+for\s+calling|welcome\s+to)\b",
    re.I,
)
DISCLOSURE = re.compile(
    r"\b(this\s+is\s+\w+|my\s+name\s+is|i'?m\s+\w+\s+(from|with|at)\b|you'?ve\s+reached"
    r"|(ai|virtual|automated|digital)\s+(assistant|receptionist|agent))\b",
    re.I,
)
OBJECTION = re.compile(
    r"\b(not\s+interested|no\s+thanks?\b|too\s+(expensive|pricey|much)"
    r"|sounds?\s+(expensive|pricey)|can'?t\s+afford|already\s+(have|using|work\s+with)"
    r"|don'?t\s+(need|want)|stop\s+calling|take\s+me\s+off)\b",
    re.I,
)
ACKNOWLEDGEMENT = re.compile(
    r"\b(understand(able)?|fair\s+enough|no\s+problem|makes\s+sense|i\s+hear\s+you"
    r"|appreciate|good\s+question|totally\s+get|happy\s+to\s+explain)\b",
    re.I,
)
BOOKING_INTENT = re.compile(
    r"\b(book(ing)?|schedule|scheduling|appointment|reserve"
    r"|set\s+up\s+a\s+(time|visit|call))\b",
    re.I,
)
BOOKING_CONFIRMATION = re.compile(
    r"\b(you'?re\s+(all\s+set|booked)|booked\s+you|confirmed|scheduled\s+(you|for)"
    r"|confirmation\s+(text|email|number)|calendar\s+invite|see\s+you\s+(at|on|then))\b",
    re.I,
)
TRANSFER_REQUEST = re.compile(
    r"\b((speak|talk)\s+(to|with)\s+(a\s+|an\s+)?(human|person|someone|rep(resentative)?"
    r"|manager|real\s+person)|real\s+person|human\s+being|transfer\s+me"
    r"|get\s+me\s+(a|an|someone))\b",
    re.I,
)
TRANSFER_ACTION = re.compile(
    r"\b(transferr?ing|connect(ing)?\s+you|let\s+me\s+(get|grab|find)\s+(a|an|someone|the)"
    r"|one\s+moment\s+while|patch(ing)?\s+you|put(ting)?\s+you\s+through)\b",
    re.I,
)
CONFUSION = re.compile(
    r"\b(sorry,?\s+(what|i\s+didn'?t)|didn'?t\s+(catch|understand|get)\s+that"
    r"|could\s+you\s+repeat|say\s+that\s+again|i'?m\s+not\s+sure\s+(what|i)|come\s+again)\b",
    re.I,
)


def _expects_reply(text: str) -> bool:
    stripped = text.rstrip()
    return (
        stripped.endswith("?")
        or bool(BOOKING_INTENT.search(text))
        or bool(TRANSFER_REQUEST.search(text))
    )


# ---------------------------------------------------------------------------
# The default check suite
# ---------------------------------------------------------------------------


@register_check("greeting", "Agent opens the call with a recognizable greeting.")
def check_greeting(transcript: Transcript, config: AuditConfig) -> List[Finding]:
    agent_turns = [(i, t) for i, t in enumerate(transcript.turns) if t.role == AGENT]
    if not agent_turns:
        return [
            Finding(
                "greeting",
                SEVERITY_HIGH,
                "the agent never spoke on this call",
                receipt_for(transcript, [0], note="first turn of a call with no agent speech"),
            )
        ]
    window = agent_turns[: max(1, config.greeting_turns)]
    if any(GREETING.search(t.text) for _, t in window):
        return []
    return [
        Finding(
            "greeting",
            SEVERITY_MEDIUM,
            "agent's opener contains no greeting - callers hear a cold start",
            receipt_for(transcript, [i for i, _ in window]),
        )
    ]


@register_check("disclosure", "Agent identifies itself or the business early in the call.")
def check_disclosure(transcript: Transcript, config: AuditConfig) -> List[Finding]:
    agent_turns = [(i, t) for i, t in enumerate(transcript.turns) if t.role == AGENT]
    if not agent_turns:
        return []  # the greeting check already covers a silent agent
    window = agent_turns[: max(1, config.disclosure_turns)]
    if any(DISCLOSURE.search(t.text) for _, t in window):
        return []
    return [
        Finding(
            "disclosure",
            SEVERITY_MEDIUM,
            "agent never identified itself or the business in its opening turns",
            receipt_for(transcript, [i for i, _ in window]),
        )
    ]


@register_check("opener_loop", "Agent does not repeat its opener after the caller has spoken.")
def check_opener_loop(transcript: Transcript, config: AuditConfig) -> List[Finding]:
    first_opener: Optional[int] = None
    customer_spoke = False
    for i, turn in enumerate(transcript.turns):
        if turn.role == CUSTOMER and turn.text.strip():
            customer_spoke = True
        elif turn.role == AGENT and OPENER.search(turn.text):
            if first_opener is None:
                first_opener = i
            elif customer_spoke:
                return [
                    Finding(
                        "opener_loop",
                        SEVERITY_HIGH,
                        "agent repeated its opener after the caller had already spoken - "
                        "the conversation state was lost",
                        receipt_for(transcript, [first_opener, i]),
                    )
                ]
    return []


@register_check("interruption_recovery", "Agent recovers when the caller barges in.")
def check_interruption_recovery(transcript: Transcript, config: AuditConfig) -> List[Finding]:
    for i, turn in enumerate(transcript.turns[:-1]):
        nxt = transcript.turns[i + 1]
        if (
            turn.role == CUSTOMER
            and 0 < len(turn.text.strip()) < config.interruption_max_chars
            and nxt.role == AGENT
            and CONFUSION.search(nxt.text)
        ):
            return [
                Finding(
                    "interruption_recovery",
                    SEVERITY_HIGH,
                    "agent lost the thread after a short caller interjection",
                    receipt_for(transcript, [i, i + 1]),
                )
            ]
    return []


@register_check("objection_handling", "Agent acknowledges a caller objection instead of steamrolling.")
def check_objection_handling(transcript: Transcript, config: AuditConfig) -> List[Finding]:
    patterns = [OBJECTION] + [re.compile(p, re.I) for p in config.extra_objection_patterns]
    findings: List[Finding] = []
    for i, turn in enumerate(transcript.turns):
        if turn.role != CUSTOMER or not any(p.search(turn.text) for p in patterns):
            continue
        replies = [
            (j, t)
            for j, t in enumerate(transcript.turns[i + 1 : i + 3], start=i + 1)
            if t.role == AGENT
        ]
        if not replies:
            continue  # no agent response at all -> abrupt_ending's territory
        if any(ACKNOWLEDGEMENT.search(t.text) for _, t in replies):
            continue
        findings.append(
            Finding(
                "objection_handling",
                SEVERITY_MEDIUM,
                "caller raised an objection and the agent never acknowledged it",
                receipt_for(transcript, [i, replies[0][0]]),
            )
        )
    return findings


@register_check("booking_completion", "A booking the caller asked for actually reaches a confirmation.")
def check_booking_completion(transcript: Transcript, config: AuditConfig) -> List[Finding]:
    # Intent must come from the caller; an agent describing itself as a
    # "scheduling assistant" is not a booking request.
    intent_turns = [
        i
        for i, t in enumerate(transcript.turns)
        if t.role == CUSTOMER and BOOKING_INTENT.search(t.text)
    ]
    if not intent_turns:
        return []
    if any(BOOKING_CONFIRMATION.search(t.text) for t in transcript.agent_turns):
        return []
    last_agent = max(
        (i for i, t in enumerate(transcript.turns) if t.role == AGENT),
        default=None,
    )
    cited = [intent_turns[0]] + ([last_agent] if last_agent is not None else [])
    return [
        Finding(
            "booking_completion",
            SEVERITY_HIGH,
            "the caller asked to book but never got a confirmation - the appointment silently dropped",
            receipt_for(
                transcript,
                cited,
                note="cites the caller's booking ask and the agent's final turn (no confirmation)",
            ),
        )
    ]


@register_check("forbidden_phrases", "Agent never says a configured forbidden phrase.")
def check_forbidden_phrases(transcript: Transcript, config: AuditConfig) -> List[Finding]:
    findings: List[Finding] = []
    for i, turn in enumerate(transcript.turns):
        if turn.role != AGENT:
            continue
        lowered = turn.text.lower()
        for phrase in config.forbidden_phrases:
            if phrase.lower() in lowered:
                findings.append(
                    Finding(
                        "forbidden_phrases",
                        SEVERITY_HIGH,
                        f"agent said a forbidden phrase: {phrase!r}",
                        receipt_for(transcript, [i]),
                    )
                )
                break  # one finding per turn, even if it hits several phrases
    return findings


@register_check("dead_air", "No long silent gaps between timestamped turns.")
def check_dead_air(transcript: Transcript, config: AuditConfig) -> List[Finding]:
    findings: List[Finding] = []
    for i in range(len(transcript.turns) - 1):
        a, b = transcript.turns[i], transcript.turns[i + 1]
        if a.t is None or b.t is None:
            continue
        gap = b.t - a.t
        if gap > config.dead_air_seconds:
            findings.append(
                Finding(
                    "dead_air",
                    SEVERITY_MEDIUM,
                    f"{gap:.1f}s gap between turns "
                    f"(threshold {config.dead_air_seconds:.1f}s) - feels broken to a caller",
                    receipt_for(transcript, [i, i + 1]),
                )
            )
    return findings


@register_check("transfer_handling", "A request for a human leads to transfer language.")
def check_transfer_handling(transcript: Transcript, config: AuditConfig) -> List[Finding]:
    for i, turn in enumerate(transcript.turns):
        if turn.role != CUSTOMER or not TRANSFER_REQUEST.search(turn.text):
            continue
        replies = [t for t in transcript.turns[i + 1 : i + 4] if t.role == AGENT]
        if not replies:
            continue  # nothing after the request -> abrupt_ending's territory
        if any(TRANSFER_ACTION.search(t.text) for t in replies):
            return []
        reply_index = next(
            j for j, t in enumerate(transcript.turns[i + 1 : i + 4], start=i + 1) if t.role == AGENT
        )
        return [
            Finding(
                "transfer_handling",
                SEVERITY_MEDIUM,
                "caller asked for a human and the agent never offered a transfer",
                receipt_for(transcript, [i, reply_index]),
            )
        ]
    return []


@register_check("abrupt_ending", "The call does not end while the caller is waiting on the agent.")
def check_abrupt_ending(transcript: Transcript, config: AuditConfig) -> List[Finding]:
    if not transcript.turns:
        return []
    last_index = len(transcript.turns) - 1
    last = transcript.turns[last_index]
    if last.role == CUSTOMER and _expects_reply(last.text):
        return [
            Finding(
                "abrupt_ending",
                SEVERITY_MEDIUM,
                "call ended while the caller was still waiting on the agent",
                receipt_for(transcript, [last_index]),
            )
        ]
    return []
