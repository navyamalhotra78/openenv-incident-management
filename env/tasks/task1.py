from models.task_config import TaskConfig
from env.constants import incident_weight

TASK1_CONFIG = TaskConfig(
    task_id=1,
    name="single_alert_triage",
    difficulty="easy",
    description=(
        "A single alert has triggered. Correctly triage it within the step budget. "
        "Watch for SLA deadlines and severity escalation."
    ),
    max_steps=5,
    n_incidents=1,
)


def grade(state) -> float:
    """
    Score 0.0–1.0 for task 1.

    - resolved   → 0.7 base + up to 0.3 step-efficiency bonus
    - in_progress → 0.35 (partially resolved)
    - escalated  → 0.4
    - pending    → 0.2
    - open       → 0.0
    SLA breach   → −0.15 penalty
    """
    inc = state.incidents[0]

    if inc.status == "resolved":
        efficiency = max(0.0, (state.max_steps - state.step) / state.max_steps)
        base = 0.7 + 0.3 * efficiency
    elif inc.status == "escalated":
        base = 0.4
    elif inc.status == "in_progress":
        base = 0.35
    elif inc.status == "pending":
        base = 0.2
    else:
        base = 0.0

    sla_penalty = 0.15 if inc.sla_breached else 0.0
    return round(max(0.0, base - sla_penalty), 3)
