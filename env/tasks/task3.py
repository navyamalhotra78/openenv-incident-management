from models.task_config import TaskConfig

TASK3_CONFIG = TaskConfig(
    task_id=3,
    name="cascading_failure_response",
    difficulty="hard",
    description=(
        "Critical incidents are triggering cascading failures. "
        "Contain the spread and resolve root causes before the system degrades further."
    ),
    max_steps=10,
    n_incidents=3,
)

# If a service has an unhandled critical/high incident for >= 2 steps,
# it can spawn a new incident on one of its downstream services.
CASCADE_DEPS: dict[str, list[str]] = {
    "database":    ["auth", "payments", "trading"],
    "api-gateway": ["ui", "trading"],
    "auth":        ["payments", "trading"],
    "payments":    ["trading"],
    "trading":     [],
    "ui":          [],
}

SEVERITY_WEIGHTS = {"critical": 0.4, "high": 0.3, "medium": 0.2, "low": 0.1}


def grade(state) -> float:
    """
    Score 0.0–1.0 for task 3.
    - Base score = weighted resolution of the *original* (non-cascade) incidents.
    - Cascade penalty: -0.1 per spawned cascade incident (capped at -0.3).
    - No-cascade bonus: +0.1 if zero cascades were triggered.
    """
    original = [inc for inc in state.incidents if not inc.is_cascade]
    cascaded = [inc for inc in state.incidents if inc.is_cascade]

    total_weight = sum(SEVERITY_WEIGHTS[inc.severity] for inc in original)
    if total_weight == 0:
        return 0.0

    resolved_weight = sum(
        SEVERITY_WEIGHTS[inc.severity]
        for inc in original
        if inc.status == "resolved"
    )
    escalated_weight = sum(
        SEVERITY_WEIGHTS[inc.severity] * 0.5
        for inc in original
        if inc.status == "escalated"
    )

    base_score = (resolved_weight + escalated_weight) / total_weight
    cascade_penalty = min(0.3, len(cascaded) * 0.1)
    cascade_bonus = 0.1 if len(cascaded) == 0 else 0.0

    return round(max(0.0, min(1.0, base_score - cascade_penalty + cascade_bonus)), 3)
