"""
Baseline agent: greedy priority-aware resolver.

Strategy (in order of priority):
  1. Investigate any unconfirmed incidents (reveal false alarms first)
  2. In Task 3: mitigate critical/high incidents at cascade-risk (age >= 1) if multiples exist
  3. Resolve the highest-severity confirmed open/in-progress incident
     (weighted by severity × service impact for tie-breaking)

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
            # Mitigate the one with highest age (most urgent cascade risk)
            target = max(at_risk, key=lambda i: i.age)
            return Action(type="mitigate", incident_id=target.id)

    # 3. Resolve highest-weight incident (root causes first)
    root_causes = [i for i in open_real if i.is_root_cause]
    pool = root_causes if root_causes else open_real
    target = max(pool, key=_weight)
    return Action(type="resolve", incident_id=target.id)


def run_episode(task_id: int, seed: int) -> tuple[float, int]:
    random.seed(seed)
    env = IncidentEnv()
    state = env.reset(task_id=task_id)
    done = False
    steps = 0

    while not done:
        action = greedy_action(state)
        if action is None:
            break
        state, _reward, done, _info = env.step(action)
        steps += 1

    return state.score, steps


def main():
    n_seeds = 20
    print("=" * 56)
    print("  Baseline Agent — Greedy Priority-Aware Resolver")
    print("=" * 56)

    overall = []
    for task_id in [1, 2, 3]:
        scores = [run_episode(task_id, seed)[0] for seed in range(n_seeds)]
        avg = sum(scores) / len(scores)
        mn, mx = min(scores), max(scores)
        overall.append(avg)
        print(f"\nTask {task_id}  avg={avg:.3f}  min={mn:.3f}  max={mx:.3f}  (n={n_seeds})")

    print(f"\nOverall avg: {sum(overall) / len(overall):.3f}")
    print("=" * 56)


if __name__ == "__main__":
    main()
