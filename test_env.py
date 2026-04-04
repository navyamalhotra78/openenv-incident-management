"""
Smoke-test for all three tasks covering all new mechanics.
Run from repo root: python test_env.py
"""

import random
from env.environment import IncidentEnv
from models.action import Action

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def greedy_action(state):
    actionable = [i for i in state.incidents if i.status not in ("resolved", "dismissed", "escalated")]
    if not actionable:
        return None
    unconfirmed = [i for i in actionable if not i.confirmed]
    if unconfirmed:
        return Action(type="investigate", incident_id=unconfirmed[0].id)
    confirmed = [i for i in actionable if i.confirmed]
    if not confirmed:
        return None
    target = min(confirmed, key=lambda i: SEVERITY_ORDER[i.severity])
    return Action(type="resolve", incident_id=target.id)


def run_task(task_id: int, seed: int = 42):
    random.seed(seed)
    env = IncidentEnv()
    state = env.reset(task_id=task_id)

    print(f"\n── Task {task_id} ──────────────────────────────────────")
    print(f"  max_steps={state.max_steps}  incidents={len(state.incidents)}")
    for inc in state.incidents:
        tags = []
        if inc.is_root_cause:    tags.append("root-cause")
        if inc.root_cause_id:    tags.append(f"symptom-of:{inc.root_cause_id}")
        if not inc.confirmed:    tags.append("unconfirmed")
        if inc.resolution_steps > 1: tags.append(f"steps:{inc.resolution_steps}")
        tag_str = f"  [{', '.join(tags)}]" if tags else ""
        print(f"  {inc.id}  {inc.severity:<8}  {inc.service:<12}  SLA@{inc.sla_deadline}{tag_str}")

    done = False
    while not done:
        action = greedy_action(state)
        if action is None:
            break
        state, reward, done, info = env.step(action)

        extras = []
        if info.get("cascades_triggered"):    extras.append(f"cascade={info['cascades_triggered']}")
        if info.get("auto_escalated"):        extras.append(f"escalated-sev={info['auto_escalated']}")
        if info.get("sla_breached_this_step"):extras.append(f"SLA-breach={info['sla_breached_this_step']}")
        if info.get("root_cause_resolved"):   extras.append(f"auto-resolved={info['root_cause_resolved']}")
        if info.get("new_arrivals"):          extras.append(f"new={info['new_arrivals']}")
        if info.get("false_alarm_revealed"):  extras.append("false-alarm-revealed")
        if info.get("ack_auto_escalated"):    extras.append(f"ack-escalated={info['ack_auto_escalated']}")

        print(
            f"  step {info['step']:>2}  {info['action_type']:<11}  {info['incident_id']:<14}"
            f"  sev={info['incident_severity']:<8}  score={info['score']:.3f}"
            + (f"  {' | '.join(extras)}" if extras else "")
        )

    print(f"  FINAL score={state.score:.3f}  sla_breaches={state.sla_breaches}  total_incidents={len(state.incidents)}")

    # Assertions
    assert 0.0 <= state.score <= 1.0, f"Score out of range: {state.score}"
    assert state.sla_breaches >= 0
    for inc in state.incidents:
        assert inc.status in ("open","pending","in_progress","resolved","escalated","dismissed"), \
            f"Unexpected status: {inc.status}"

    return state.score


if __name__ == "__main__":
    scores = {}
    for task_id in [1, 2, 3]:
        scores[task_id] = run_task(task_id)

    print("\n── Summary ──────────────────────────────────────────")
    for task_id, score in scores.items():
        print(f"  Task {task_id}: {score:.3f}")
    print("All assertions passed.")
