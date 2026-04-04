from models.task_config import TaskConfig

TASK2_CONFIG = TaskConfig(
    task_id=2,
    name="multi_service_queue",
    difficulty="medium",
    description=(
        "Multiple incidents of mixed severity are open across services. "
        "Resolve them efficiently, prioritising by severity."
    ),
    max_steps=12,
    n_incidents=4,
)

# Weights must sum to 1.0 — critical incidents count most
SEVERITY_WEIGHTS = {"critical": 0.4, "high": 0.3, "medium": 0.2, "low": 0.1}


def grade(state) -> float:
    """
    Score 0.0–1.0 for task 2.
    - Resolved incidents contribute their full severity weight.
    - Escalated incidents contribute 50% of their weight.
    - If all incidents are handled, a step-efficiency bonus of up to 0.15 is added.
    """
    total_weight = sum(SEVERITY_WEIGHTS[inc.severity] for inc in state.incidents)
    if total_weight == 0:
        return 0.0

    resolved_weight = sum(
        SEVERITY_WEIGHTS[inc.severity]
        for inc in state.incidents
        if inc.status == "resolved"
    )
    escalated_weight = sum(
        SEVERITY_WEIGHTS[inc.severity] * 0.5
        for inc in state.incidents
        if inc.status == "escalated"
    )

    base_score = (resolved_weight + escalated_weight) / total_weight

    all_handled = all(inc.status in ("resolved", "escalated") for inc in state.incidents)
    if all_handled:
        efficiency = max(0.0, (state.max_steps - state.step) / state.max_steps)
        base_score = min(1.0, base_score + 0.15 * efficiency)

    return round(base_score, 3)
