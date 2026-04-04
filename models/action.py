from pydantic import BaseModel
from typing import Literal, Optional


class Action(BaseModel):
    type: Literal[
        "resolve", "escalate", "ignore", "mitigate", "investigate",
        "triage", "execute_fix", "write_postmortem",
    ]
    incident_id: str

    # ── Triage payload ─────────────────────────────────────────────────────────
    severity: Optional[str] = None          # agent's severity classification
    team: Optional[str] = None              # agent's team assignment

    # ── Root cause investigation payload ──────────────────────────────────────
    root_cause: Optional[str] = None        # agent's root cause hypothesis

    # ── Remediation payload ────────────────────────────────────────────────────
    fixes: Optional[list[str]] = None       # ordered list of fix action names

    # ── Post-mortem payload ────────────────────────────────────────────────────
    postmortem: Optional[str] = None        # free-text post-mortem write-up
