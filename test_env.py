"""
Quick smoke-test for all three tasks.
Run from repo root: python test_env.py
"""

from env.environment import IncidentEnv
from models.action import Action

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def greedy_action(state):
    actionable = [i for i in state.incidents if i.status in ("open", "pending")]
    if not actionable:
        return None
    target = min(actionable, key=lambda i: SEVERITY_ORDER[i.severity])
    return Action(type="resolve", incident_id=target.id)


def run_task(task_id: int):
    env = IncidentEnv()
    state = env.reset(task_id=task_id)

    print(f"\n── Task {task_id} ──────────────────────────────")
    print(f"  max_steps={state.max_steps}  incidents={len(state.incidents)}")
    for inc in state.incidents:
        print(f"  {inc.id}  {inc.severity:<8}  {inc.service}")

    done = False
    while not done:
        action = greedy_action(state)
        if action is None:
            break
        state, reward, done, info = env.step(action)
        cascade_note = f"  cascades={info['cascades_triggered']}" if info.get("cascades_triggered") else ""
        print(
            f"  step {info['step']:>2}  {info['action_type']:<8} {info['incident_id']:<12}"
            f"  sev={info['incident_severity']:<8}  score={info['score']:.3f}"
            f"  reward={reward:.3f}{cascade_note}"
        )

    print(f"  FINAL score={state.score:.3f}  total_incidents={len(state.incidents)}")
    assert 0.0 <= state.score <= 1.0, "Score out of range!"
    return state.score


if __name__ == "__main__":
    scores = {}
    for task_id in [1, 2, 3]:
        scores[task_id] = run_task(task_id)

    print("\n── Summary ─────────────────────────────────")
    for task_id, score in scores.items():
        print(f"  Task {task_id}: {score:.3f}")
    print("All assertions passed.")
