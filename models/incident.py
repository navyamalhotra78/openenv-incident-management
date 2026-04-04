from pydantic import BaseModel, Field
from typing import Literal, Optional


class Incident(BaseModel):
    id: str
    severity: Literal["low", "medium", "high", "critical"]
    service: Literal["auth", "payments", "trading", "ui", "database", "api-gateway"]
    status: Literal["open", "pending", "in_progress", "resolved", "escalated", "dismissed"]
    age: int = 0

    # ── Cascade (task 3) ───────────────────────────────────────
    is_cascade: bool = False
    parent_id: Optional[str] = None

    # ── SLA ───────────────────────────────────────────────────
    sla_deadline: int = 99          # absolute episode step when SLA expires
    sla_breached: bool = False

    # ── Root cause correlation ────────────────────────────────
    root_cause_id: Optional[str] = None   # ID of the root-cause incident this is a symptom of
    is_root_cause: bool = False            # resolving this auto-resolves linked symptoms

    # ── False alarms ──────────────────────────────────────────
    confirmed: bool = True          # False = unconfirmed; use 'investigate' to reveal truth
    is_false_alarm: bool = Field(default=False, exclude=True)  # hidden from agent / API

    # ── Multi-step resolution ─────────────────────────────────
    resolution_steps: int = 1       # number of 'resolve' actions required
    resolution_progress: int = 0    # how many resolves have been applied so far

    # ── Acknowledgment ────────────────────────────────────────
    acknowledged: bool = False      # True after any non-ignore action; unacked criticals auto-escalate
