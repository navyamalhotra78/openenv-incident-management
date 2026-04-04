from pydantic import BaseModel, Field
from typing import Any, Literal, Optional


class Incident(BaseModel):
    id: str
    severity: Literal["low", "medium", "high", "critical"]
    service: Literal["auth", "payments", "trading", "ui", "database", "api-gateway"]
    status: Literal["open", "pending", "in_progress", "resolved", "escalated", "dismissed"]
    age: int = 0

    # ── Rich context (visible to agent) ───────────────────────────────────────
    title: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)
    logs: list[str] = Field(default_factory=list)

    # ── Cascade (task 3) ───────────────────────────────────────────────────────
    is_cascade: bool = False
    parent_id: Optional[str] = None

    # ── SLA ────────────────────────────────────────────────────────────────────
    sla_deadline: int = 99
    sla_breached: bool = False

    # ── Root cause correlation ─────────────────────────────────────────────────
    root_cause_id: Optional[str] = None
    is_root_cause: bool = False

    # ── False alarms ───────────────────────────────────────────────────────────
    confirmed: bool = True
    is_false_alarm: bool = Field(default=False, exclude=True)

    # ── Multi-step resolution ──────────────────────────────────────────────────
    resolution_steps: int = 1
    resolution_progress: int = 0

    # ── Acknowledgment ─────────────────────────────────────────────────────────
    acknowledged: bool = False

    # ── Task 4 lifecycle flags (visible — agent tracks its own progress) ───────
    triage_done: bool = False
    root_cause_found: bool = False
    remediation_done: bool = False
    postmortem_done: bool = False
    assigned_team: Optional[str] = None

    # ── Task 4 per-stage scores (used by task 4 grader) ───────────────────────
    triage_score: float = 0.0
    root_cause_score: float = 0.0
    remediation_score: float = 0.0
    postmortem_score: float = 0.0

    # ── Hidden ground truth (excluded from API responses) ─────────────────────
    true_team: Optional[str] = Field(default=None, exclude=True)
    true_root_cause: Optional[str] = Field(default=None, exclude=True)
    valid_fixes: list[str] = Field(default_factory=list, exclude=True)
    required_fix_order: list[str] = Field(default_factory=list, exclude=True)
    prevention_steps: list[str] = Field(default_factory=list, exclude=True)
