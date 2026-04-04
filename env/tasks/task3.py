from models.task_config import TaskConfig
from env.constants import incident_weight

TASK3_CONFIG = TaskConfig(
    task_id=3,
    name="cascading_failure_response",
    difficulty="hard",
    description=(
        "Critical incidents are triggering cascading failures across dependent services. "
        "Some incidents require multiple resolution steps. "
        "Contain the spread, acknowledge criticals fast, and resolve root causes first."
    ),
    max_steps=14,
    n_incidents=3,
)

# Downstream service dependencies for cascade propagation
CASCADE_DEPS: dict[str, list[str]] = {
    "database":    ["auth", "payments", "trading"],
    "api-gateway": ["ui", "trading"],
    "auth":        ["payments", "trading"],
    "payments":    ["trading"],
    "trading":     [],
    "ui":          [],
}


def grade(state) -> float:
    """
    Score 0.0–1.0 for task 3.

    Base score = weighted resolution of original (non-cascade) incidents,
    where weight = severity_weight × service_impact.

    Modifiers:
    - Escalated incidents    → 50% of weight
    - In-progress incidents  → 25% of weight
    - SLA breach penalty     → −0.05 per breach (max −0.25)
    - Cascade penalty        → −0.1 per spawned cascade (max −0.3)
    - No-cascade bonus       → +0.1 if zero cascades triggered
    """
    original = [i for i in state.incidents if not i.is_cascade]
    cascaded = [i for i in state.incidents if i.is_cascade]

    total_weight = sum(incident_weight(i) for i in original)
    if total_weight == 0:
        base_score = 0.0
    else:
        resolved_w    = sum(incident_weight(i)        for i in original if i.status == "resolved")
        escalated_w   = sum(incident_weight(i) * 0.50 for i in original if i.status == "escalated")
        in_progress_w = sum(incident_weight(i) * 0.25 for i in original if i.status == "in_progress")
        base_score = (resolved_w + escalated_w + in_progress_w) / total_weight

    sla_penalty     = min(0.25, state.sla_breaches * 0.05)
    cascade_penalty = min(0.30, len(cascaded) * 0.10)
    cascade_bonus   = 0.10 if len(cascaded) == 0 else 0.0

    return round(max(0.0, min(1.0, base_score - sla_penalty - cascade_penalty + cascade_bonus)), 3)
