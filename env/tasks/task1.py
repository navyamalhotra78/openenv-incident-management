from models.task_config import TaskConfig

TASK1_CONFIG = TaskConfig(
    task_id=1,
    name="single_alert_triage",
    difficulty="easy",
    description="A single alert has triggered. Correctly triage it within the step budget.",
    max_steps=5,
    n_incidents=1,
)


def grade(state) -> float:
    """
    Score 0.0–1.0 for task 1.
    - resolve  → 0.7 base + up to 0.3 step-efficiency bonus
    - escalate → 0.4 (acknowledged but not fully handled)
    - pending  → 0.2 (mitigated / partially addressed)
    - open     → 0.0
    """
    inc = state.incidents[0]
    if inc.status == "resolved":
        efficiency = max(0.0, (state.max_steps - state.step) / state.max_steps)
        return round(0.7 + 0.3 * efficiency, 3)
    elif inc.status == "escalated":
        return 0.4
    elif inc.status == "pending":
        return 0.2
    return 0.0
