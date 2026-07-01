"""The action gate: dry-run by default, explicit arming, full history."""
import pytest

from dialproof.gate import (
    ARM_CONFIRMATION,
    MODE_BLOCKED,
    MODE_DRY_RUN,
    MODE_EXECUTED,
    MODE_FAILED,
    ActionGate,
    GateError,
)


def test_gate_is_disarmed_by_default():
    gate = ActionGate("outreach")
    assert gate.armed is False


def test_dry_run_never_calls_executor():
    gate = ActionGate()
    calls = []
    record = gate.submit("send_email", {"to": "qa@example.com"}, executor=calls.append)
    assert record.mode == MODE_DRY_RUN
    assert calls == []
    assert record.executed is False


def test_arming_requires_exact_confirmation_phrase():
    gate = ActionGate()
    with pytest.raises(GateError):
        gate.arm(confirm="yes please")
    with pytest.raises(GateError):
        gate.arm(confirm="arm-live")  # case matters
    assert gate.armed is False


def test_armed_gate_executes_and_records_result():
    gate = ActionGate()
    gate.arm(confirm=ARM_CONFIRMATION)
    record = gate.submit("place_call", {"number": "+1-555-0100"}, executor=lambda p: "dialed")
    assert record.mode == MODE_EXECUTED
    assert record.result == "dialed"
    assert gate.executed_actions() == [record]


def test_armed_without_executor_blocks():
    gate = ActionGate()
    gate.arm(confirm=ARM_CONFIRMATION)
    record = gate.submit("place_call", {"number": "+1-555-0100"})
    assert record.mode == MODE_BLOCKED


def test_executor_exception_recorded_not_raised():
    gate = ActionGate()
    gate.arm(confirm=ARM_CONFIRMATION)

    def boom(payload):
        raise ConnectionError("SMTP unreachable")

    record = gate.submit("send_email", {}, executor=boom)
    assert record.mode == MODE_FAILED
    assert "SMTP unreachable" in record.detail


def test_disarm_returns_to_safe_default():
    gate = ActionGate()
    gate.arm(confirm=ARM_CONFIRMATION)
    gate.disarm()
    record = gate.submit("send_email", {}, executor=lambda p: "sent")
    assert record.mode == MODE_DRY_RUN


def test_history_records_every_attempt():
    gate = ActionGate()
    gate.submit("a")
    gate.arm(confirm=ARM_CONFIRMATION)
    gate.submit("b", executor=lambda p: 1)
    gate.submit("c")
    modes = [r.mode for r in gate.history]
    assert modes == [MODE_DRY_RUN, MODE_EXECUTED, MODE_BLOCKED]
    assert [r.to_dict()["action"] for r in gate.history] == ["a", "b", "c"]
