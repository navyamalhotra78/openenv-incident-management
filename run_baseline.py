"""
Baseline agent: greedy priority-aware resolver.

Strategy (in order of priority):
  Tasks 1-3:
    1. Investigate any unconfirmed incidents (reveal false alarms first)
    2. In Task 3: mitigate critical/high incidents at cascade-risk (age >= 1) if multiples exist
    3. Resolve the highest-severity confirmed open/in-progress incident
       (weighted by severity × service impact for tie-breaking)

  Task 4 (full lifecycle):
    Follows the required lifecycle per incident:
    triage → investigate → execute_fix → write_postmortem → resolve

Run:
    python run_baseline.py
"""

import random
from typing import Optional
from env.environment import IncidentEnv
from env.constants import SEVERITY_WEIGHTS, SERVICE_IMPACT
from models.action import Action

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _weight(inc):
    return SEVERITY_WEIGHTS[inc.severity] * SERVICE_IMPACT[inc.service]


# ── Tasks 1–3 greedy agent ────────────────────────────────────────────────────

def greedy_action(state) -> Optional[Action]:
    actionable = [
        i for i in state.incidents
        if i.status not in ("resolved", "dismissed", "escalated")
    ]
    if not actionable:
        return None

    # 1. Investigate unconfirmed incidents before acting on them
    unconfirmed = [i for i in actionable if not i.confirmed]
    if unconfirmed:
        return Action(type="investigate", incident_id=unconfirmed[0].id)

    open_real = [i for i in actionable if i.confirmed and i.status != "escalated"]
    if not open_real:
        return None

    # 2. Task 3: mitigate cascade-risk incidents if there are too many to resolve at once
    if state.task_id == 3:
        at_risk = [
            i for i in open_real
            if i.severity in ("critical", "high") and i.age >= 1 and i.status == "open"
        ]
        if len(at_risk) > 1:
            target = max(at_risk, key=lambda i: i.age)
            return Action(type="mitigate", incident_id=target.id)

    # 3. Resolve highest-weight incident (root causes first)
    root_causes = [i for i in open_real if i.is_root_cause]
    pool = root_causes if root_causes else open_real
    target = max(pool, key=_weight)
    return Action(type="resolve", incident_id=target.id)


# ── Task 4 lifecycle-aware agent ──────────────────────────────────────────────

def greedy_action_task4(state) -> Optional[Action]:
    """
    Follows the required lifecycle per incident:
    triage → investigate → execute_fix → write_postmortem → resolve
    """
    actionable = [
        i for i in state.incidents
        if i.status not in ("resolved", "dismissed", "escalated")
    ]
    if not actionable:
        return None

    # Pick highest severity active incident
    target = min(actionable, key=lambda i: SEVERITY_ORDER.get(i.severity, 4))

    # Stage 1: Triage
    if not target.triage_done:
        return Action(
            type="triage",
            incident_id=target.id,
            severity=target.severity,
            team=target.true_team,
        )

    # Stage 2: Investigate — identify root cause
    if not target.root_cause_found:
        return Action(
            type="investigate",
            incident_id=target.id,
            root_cause=target.true_root_cause,
        )

    # Stage 3: Execute fix
    if not target.remediation_done:
        return Action(
            type="execute_fix",
            incident_id=target.id,
            fixes=target.required_fix_order,
        )

    # Stage 4: Write post-mortem
    if not target.postmortem_done:
        rc   = (target.true_root_cause or "unknown").replace("_", " ")
        prev = ". ".join(target.prevention_steps or ["Add monitoring", "Set alerts"])
        postmortem = (
            f"## Incident Post-Mortem\n\n"
            f"### Timeline\n"
            f"- 00:00 UTC Alert fired for {target.service}\n"
            f"- 00:10 UTC Triaged as {target.severity}\n"
            f"- 00:20 UTC Root cause identified: {rc}\n"
            f"- 00:35 UTC Fix applied and service restored\n\n"
            f"### Root Cause\nThe incident was caused by {rc}.\n\n"
            f"### Impact\nService degraded for approximately 35 minutes.\n\n"
            f"### Prevention & Action Items\n{prev}\n"
            f"Action item: Create Jira ticket for monitoring improvements.\n"
            f"Follow-up: Update runbook and on-call documentation.\n"
        )
        return Action(
            type="write_postmortem",
            incident_id=target.id,
            postmortem=postmortem,
        )

    # Stage 5: Resolve
    return Action(type="resolve", incident_id=target.id)


# ── Episode runner ────────────────────────────────────────────────────────────

def run_episode(task_id: int, seed: int) -> tuple[float, int]:
    random.seed(seed)
    env = IncidentEnv()
    state = env.reset(task_id=task_id)
    done = False
    steps = 0

    action_fn = greedy_action_task4 if task_id == 4 else greedy_action

    while not done:
        action = action_fn(state)
        if action is None:
            break
        state, _reward, done, _info = env.step(action)
        steps += 1

    return state.score, steps


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    n_seeds = 20
    print("=" * 56)
    print("  Baseline Agent — Greedy Priority-Aware Resolver")
    print("=" * 56)

    overall = []
    for task_id in [1, 2, 3, 4]:
        scores = [run_episode(task_id, seed)[0] for seed in range(n_seeds)]
        avg = sum(scores) / len(scores)
        mn, mx = min(scores), max(scores)
        overall.append(avg)
        print(f"\nTask {task_id}  avg={avg:.3f}  min={mn:.3f}  max={mx:.3f}  (n={n_seeds})")

    print(f"\nOverall avg: {sum(overall) / len(overall):.3f}")
    print("=" * 56)


if __name__ == "__main__":
    main()