"""The default check suite, one behavior per test."""
from dialproof.checks import CHECKS, AuditConfig
from dialproof.models import Transcript, Turn


def run_check(name, turns, config=None):
    transcript = Transcript(turns=turns, call_id="test-call")
    return CHECKS[name].func(transcript, config or AuditConfig())


# --- greeting ---------------------------------------------------------------


def test_greeting_present_passes():
    findings = run_check(
        "greeting",
        [Turn("agent", "Hi, thanks for calling Acme Plumbing!"), Turn("customer", "Hello.")],
    )
    assert findings == []


def test_greeting_missing_flags_with_receipt():
    findings = run_check(
        "greeting",
        [Turn("agent", "State your account number."), Turn("customer", "Um, what?")],
    )
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert findings[0].receipt.turn_indices == [0]
    assert "State your account number." in findings[0].receipt.lines[0]


def test_silent_agent_is_high_severity():
    findings = run_check("greeting", [Turn("customer", "Hello? Anyone there?")])
    assert len(findings) == 1
    assert findings[0].severity == "high"


# --- disclosure --------------------------------------------------------------


def test_disclosure_detected():
    findings = run_check(
        "disclosure",
        [Turn("agent", "Hi! This is Ava, the automated assistant for Acme Plumbing.")],
    )
    assert findings == []


def test_disclosure_missing_flags():
    findings = run_check(
        "disclosure",
        [
            Turn("agent", "Hello, how are you today?"),
            Turn("customer", "Who is this?"),
            Turn("agent", "How can I help?"),
        ],
    )
    assert len(findings) == 1
    assert findings[0].check == "disclosure"


# --- opener_loop --------------------------------------------------------------


def test_opener_loop_detected():
    findings = run_check(
        "opener_loop",
        [
            Turn("agent", "Thanks for calling Acme Plumbing, how can I help you today?"),
            Turn("customer", "I'd like to schedule a repair."),
            Turn("agent", "Thanks for calling Acme Plumbing, how can I help you today?"),
        ],
    )
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert findings[0].receipt.turn_indices == [0, 2]


def test_single_opener_is_fine():
    findings = run_check(
        "opener_loop",
        [
            Turn("agent", "Thanks for calling Acme Plumbing, how can I help you today?"),
            Turn("customer", "I'd like to schedule a repair."),
            Turn("agent", "Sure, what day works for you?"),
        ],
    )
    assert findings == []


# --- interruption_recovery ----------------------------------------------------


def test_interruption_confusion_detected():
    findings = run_check(
        "interruption_recovery",
        [
            Turn("agent", "We offer three service tiers, starting with..."),
            Turn("customer", "Wait, stop."),
            Turn("agent", "Sorry, I didn't catch that. Could you repeat your request?"),
        ],
    )
    assert len(findings) == 1
    assert findings[0].receipt.turn_indices == [1, 2]


def test_interruption_handled_cleanly_passes():
    findings = run_check(
        "interruption_recovery",
        [
            Turn("agent", "We offer three service tiers, starting with..."),
            Turn("customer", "Wait, stop."),
            Turn("agent", "Of course — what would you like to know?"),
        ],
    )
    assert findings == []


# --- objection_handling --------------------------------------------------------


def test_unacknowledged_objection_flags():
    findings = run_check(
        "objection_handling",
        [
            Turn("agent", "It's forty-nine dollars a month."),
            Turn("customer", "That's too expensive for me."),
            Turn("agent", "Shall I sign you up for the annual plan?"),
        ],
    )
    assert len(findings) == 1
    assert findings[0].check == "objection_handling"


def test_acknowledged_objection_passes():
    findings = run_check(
        "objection_handling",
        [
            Turn("agent", "It's forty-nine dollars a month."),
            Turn("customer", "That's too expensive for me."),
            Turn("agent", "I totally understand — there is also a lighter plan at nineteen."),
        ],
    )
    assert findings == []


def test_extra_objection_patterns_from_config():
    config = AuditConfig(extra_objection_patterns=(r"\bwe already have a guy\b",))
    findings = run_check(
        "objection_handling",
        [
            Turn("customer", "Honestly, we already have a guy for that."),
            Turn("agent", "Our plans start at forty-nine dollars."),
        ],
        config,
    )
    assert len(findings) == 1


# --- booking_completion ---------------------------------------------------------


def test_booking_without_confirmation_flags():
    findings = run_check(
        "booking_completion",
        [
            Turn("customer", "Can you book me for Thursday?"),
            Turn("agent", "We have lots of availability this week."),
        ],
    )
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert 0 in findings[0].receipt.turn_indices


def test_booking_confirmed_passes():
    findings = run_check(
        "booking_completion",
        [
            Turn("customer", "Can you book me for Thursday?"),
            Turn("agent", "You're booked for Thursday at 10 am — you'll get a confirmation text."),
        ],
    )
    assert findings == []


def test_no_booking_talk_no_finding():
    findings = run_check(
        "booking_completion",
        [Turn("customer", "What are your hours?"), Turn("agent", "We're open nine to five.")],
    )
    assert findings == []


# --- forbidden_phrases -----------------------------------------------------------


def test_default_forbidden_phrase_detected():
    findings = run_check(
        "forbidden_phrases",
        [Turn("agent", "As an AI language model, I cannot look that up.")],
    )
    assert len(findings) == 1
    assert "as an ai language model" in findings[0].message


def test_custom_forbidden_phrase():
    config = AuditConfig(forbidden_phrases=("free of charge",))
    findings = run_check(
        "forbidden_phrases",
        [Turn("agent", "The first visit is free of charge!")],
        config,
    )
    assert len(findings) == 1


def test_forbidden_phrase_in_customer_turn_ignored():
    findings = run_check(
        "forbidden_phrases",
        [Turn("customer", "Are you an AI language model or what?")],
    )
    assert findings == []


# --- dead_air ---------------------------------------------------------------------


def test_dead_air_gap_detected():
    findings = run_check(
        "dead_air",
        [
            Turn("agent", "One moment please.", t=10.0),
            Turn("customer", "...hello?", t=22.0),
        ],
    )
    assert len(findings) == 1
    assert "12.0s" in findings[0].message
    assert findings[0].receipt.turn_indices == [0, 1]


def test_dead_air_threshold_configurable():
    turns = [Turn("agent", "Hold on.", t=0.0), Turn("customer", "Okay.", t=5.0)]
    assert run_check("dead_air", turns) == []
    assert len(run_check("dead_air", turns, AuditConfig(dead_air_seconds=3.0))) == 1


def test_dead_air_skips_missing_timestamps():
    findings = run_check(
        "dead_air",
        [Turn("agent", "Hold on."), Turn("customer", "Still here...")],
    )
    assert findings == []


# --- transfer_handling ---------------------------------------------------------------


def test_transfer_request_dead_ends_flags():
    findings = run_check(
        "transfer_handling",
        [
            Turn("customer", "Can I speak to a human please?"),
            Turn("agent", "Our office hours are nine to five."),
        ],
    )
    assert len(findings) == 1
    assert findings[0].check == "transfer_handling"


def test_transfer_request_honored_passes():
    findings = run_check(
        "transfer_handling",
        [
            Turn("customer", "Can I speak to a human please?"),
            Turn("agent", "Absolutely — connecting you now, one moment."),
        ],
    )
    assert findings == []


# --- abrupt_ending ---------------------------------------------------------------------


def test_call_ending_on_open_question_flags():
    findings = run_check(
        "abrupt_ending",
        [
            Turn("agent", "Anything else?"),
            Turn("customer", "Yes — how much does the service cost?"),
        ],
    )
    assert len(findings) == 1
    assert findings[0].receipt.turn_indices == [1]


def test_clean_goodbye_passes():
    findings = run_check(
        "abrupt_ending",
        [
            Turn("customer", "That's all, thanks."),
            Turn("agent", "Great, have a wonderful day!"),
        ],
    )
    assert findings == []
