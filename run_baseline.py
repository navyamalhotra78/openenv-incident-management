"""
Baseline agent: greedy severity-priority resolution.

Strategy: each step, find the open incident with the highest severity and resolve it.
If no open incidents remain, resolve any pending/escalated ones.

Run:
    python run_baseline.py
"""

import random
from env.environment import IncidentEnv
from models.action import Action

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def greedy_action(state) -> Action | None:
    actionable = [i for i in state.incidents if i.status in ("open", "pending")]
    if not actionable:
        return None
    target = min(actionable, key=lambda i: SEVERITY_ORDER[i.severity])
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
    print("=" * 52)
    print("  Baseline Agent — Greedy Severity-Priority")
    print("=" * 52)

    overall = []
    for task_id in [1, 2, 3]:
        scores = [run_episode(task_id, seed)[0] for seed in range(n_seeds)]
        avg = sum(scores) / len(scores)
        mn, mx = min(scores), max(scores)
        overall.append(avg)
        print(f"\nTask {task_id}  avg={avg:.3f}  min={mn:.3f}  max={mx:.3f}  (n={n_seeds})")

    print(f"\nOverall avg: {sum(overall) / len(overall):.3f}")
    print("=" * 52)


if __name__ == "__main__":
    main()
