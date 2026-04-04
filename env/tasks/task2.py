from models.task_config import TaskConfig
from env.constants import incident_weight

TASK2_CONFIG = TaskConfig(
    task_id=2,
    name="multi_service_queue",
    difficulty="medium",
    description=(
        "Multiple incidents of mixed severity are open across services. "
        "Resolve them efficiently, prioritising by severity and service impact. "
        "Beware of false alarms — investigate before resolving unconfirmed incidents."
    ),
    max_steps=15,
    n_incidents=4,
)


def grade(state) -> float:
    """
    Score 0.0–1.0 for task 2.

    Base score = weighted resolution across real (non-false-alarm) incidents,
    where weight = severity_weight × service_impact.

    Modifiers:
    - Escalated incidents     → 50% of weight
    - In-progress incidents   → 25% of weight
    - SLA breach penalty      → −0.05 per breach (max −0.25)
    - False alarm bonus       → +0.1 if all false alarms correctly dismissed
    - Efficiency bonus        → +0.1 if all incidents handled with steps to spare
    """
    real = [i for i in state.incidents if not i.is_false_alarm]
    false_alarms = [i for i in state.incidents if i.is_false_alarm]

    total_weight = sum(incident_weight(i) for i in real)
    if total_weight == 0:
        base_score = 1.0  # no real incidents — all false alarms
    else:
        resolved_w    = sum(incident_weight(i)        for i in real if i.status == "resolved")
        escalated_w   = sum(incident_weight(i) * 0.50 for i in real if i.status == "escalated")
        in_progress_w = sum(incident_weight(i) * 0.25 for i in real if i.status == "in_progress")
        base_score = (resolved_w + escalated_w + in_progress_w) / total_weight

    # SLA penalty
    sla_penalty = min(0.25, state.sla_breaches * 0.05)

    # False alarm bonus
    dismissed = sum(1 for i in false_alarms if i.status == "dismissed")
    fa_bonus = 0.1 if false_alarms and dismissed == len(false_alarms) else 0.0

    # Efficiency bonus
    all_handled = all(i.status in ("resolved", "escalated", "dismissed") for i in state.incidents)
    eff_bonus = 0.0
    if all_handled and state.max_steps > 0:
        eff_bonus = 0.1 * max(0.0, (state.max_steps - state.step) / state.max_steps)

    return round(max(0.0, min(1.0, base_score - sla_penalty + fa_bonus + eff_bonus)), 3)
