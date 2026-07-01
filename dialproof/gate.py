"""The action gate: dry-run by default, live only when explicitly armed.

In production, DialProof drives real-world side effects — placing a probe
call, sending an audit email. Every one of those goes through a gate like
this one. The contract:

* **Dry-run is the default.** A freshly constructed gate never executes
  anything; it records what *would* happen and returns the plan.
* **Arming is explicit and unmistakable.** ``gate.arm(confirm=ARM_CONFIRMATION)``
  with the exact confirmation phrase, or nothing goes live. There is no
  environment variable or config file that can silently arm a gate.
* **Every attempt is recorded.** Dry-runs, blocks, executions, and failures
  all land in ``gate.history`` so an operator can always answer "what did
  this thing try to do?".
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

ARM_CONFIRMATION = "ARM-LIVE"

MODE_DRY_RUN = "DRY_RUN"
MODE_BLOCKED = "BLOCKED"
MODE_EXECUTED = "EXECUTED"
MODE_FAILED = "FAILED"


class GateError(RuntimeError):
    """Raised when a gate is armed incorrectly."""


@dataclass
class ActionRecord:
    """One attempt (real or planned) at an outbound action."""

    action: str
    mode: str
    detail: str
    payload: Dict[str, Any] = field(default_factory=dict)
    result: Any = None
    at: float = field(default_factory=time.time)

    @property
    def executed(self) -> bool:
        return self.mode == MODE_EXECUTED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "mode": self.mode,
            "detail": self.detail,
            "payload": dict(self.payload),
            "result": self.result,
            "at": self.at,
        }


class ActionGate:
    """Dry-run-by-default gate for any outbound side effect."""

    def __init__(self, name: str = "default") -> None:
        self.name = name
        self._armed = False
        self.history: List[ActionRecord] = []

    @property
    def armed(self) -> bool:
        return self._armed

    def arm(self, confirm: str) -> None:
        """Arm the gate. Requires the exact confirmation phrase ``ARM-LIVE``."""
        if confirm != ARM_CONFIRMATION:
            raise GateError(
                f"refusing to arm gate {self.name!r}: confirmation phrase must be "
                f"{ARM_CONFIRMATION!r} (got {confirm!r})"
            )
        self._armed = True

    def disarm(self) -> None:
        """Return the gate to its safe default."""
        self._armed = False

    def submit(
        self,
        action: str,
        payload: Optional[Dict[str, Any]] = None,
        executor: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> ActionRecord:
        """Submit an outbound action through the gate.

        * Gate disarmed -> ``DRY_RUN`` record; ``executor`` is never called.
        * Gate armed, no executor -> ``BLOCKED`` record (refuse, don't guess).
        * Gate armed with executor -> run it; ``EXECUTED`` on success,
          ``FAILED`` (with the error message) if it raises.
        """
        payload = dict(payload or {})

        if not self._armed:
            record = ActionRecord(
                action=action,
                mode=MODE_DRY_RUN,
                detail="dry-run: no live action taken; call arm(confirm='ARM-LIVE') to execute",
                payload=payload,
            )
        elif executor is None:
            record = ActionRecord(
                action=action,
                mode=MODE_BLOCKED,
                detail="gate is armed but no executor was supplied; refusing to guess",
                payload=payload,
            )
        else:
            try:
                result = executor(payload)
            except Exception as exc:  # noqa: BLE001 - the record *is* the error report
                record = ActionRecord(
                    action=action,
                    mode=MODE_FAILED,
                    detail=f"executor raised {type(exc).__name__}: {exc}",
                    payload=payload,
                )
            else:
                record = ActionRecord(
                    action=action,
                    mode=MODE_EXECUTED,
                    detail="executed live",
                    payload=payload,
                    result=result,
                )

        self.history.append(record)
        return record

    def executed_actions(self) -> List[ActionRecord]:
        return [r for r in self.history if r.executed]
