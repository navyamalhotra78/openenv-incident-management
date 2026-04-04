from models.task_config import TaskConfig

TASK4_CONFIG = TaskConfig(
    task_id=4,
    name="full_incident_lifecycle",
    difficulty="very_hard",
    description=(
        "Handle a production incident end-to-end: acknowledge → triage (classify severity & team) → "
        "investigate (identify root cause from logs/metrics) → execute_fix (apply fixes in correct order) → "
        "write_postmortem (root cause, timeline, prevention steps, action items) → resolve. "
        "Each stage is graded — partial credit for partial completion."
    ),
    max_steps=10,
    n_incidents=1,
)


def grade(state) -> float:
    """
    Score 0.0–1.0 for task 4.

    Weighted average across all lifecycle stage scores:
      triage        15%
      root_cause    20%
      remediation   35%   ← core engineering task
      postmortem    20%
      resolved      10%

    SLA breach penalty: −0.05 per breach (max −0.20)
    """
    incidents = [i for i in state.incidents if not i.is_cascade]
    if not incidents:
        return 0.0

    scores = []
    for inc in incidents:
        s = (
            inc.triage_score      * 0.15
            + inc.root_cause_score  * 0.20
            + inc.remediation_score * 0.35
            + inc.postmortem_score  * 0.20
            + (0.10 if inc.status == "resolved" else 0.0)
        )
        scores.append(s)

    sla_penalty = min(0.20, state.sla_breaches * 0.05)
    return round(max(0.0, min(1.0, sum(scores) / len(scores) - sla_penalty)), 3)
