"""
Smoke-test for all four tasks covering all mechanics.
Run from repo root: python test_env.py
"""

import random
from env.environment import IncidentEnv
from models.action import Action

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


# ── Task 1-3 greedy agent ─────────────────────────────────────────────────────

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


# ── Task 4 lifecycle-aware greedy agent ───────────────────────────────────────

def greedy_action_task4(state):
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

    # Stage 1: Triage — classify severity and assign team
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

    # Stage 3: Execute fix — apply fixes in correct order
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


# ── Task runner ───────────────────────────────────────────────────────────────

def run_task(task_id: int, seed: int = 42):
    random.seed(seed)
    env = IncidentEnv()
    state = env.reset(task_id=task_id)

    print(f"\n── Task {task_id} ──────────────────────────────────────")
    print(f"  max_steps={state.max_steps}  incidents={len(state.incidents)}")
    for inc in state.incidents:
        tags = []
        if inc.is_root_cause:        tags.append("root-cause")
        if inc.root_cause_id:        tags.append(f"symptom-of:{inc.root_cause_id}")
        if not inc.confirmed:        tags.append("unconfirmed")
        if inc.resolution_steps > 1: tags.append(f"steps:{inc.resolution_steps}")
        tag_str = f"  [{', '.join(tags)}]" if tags else ""
        print(f"  {inc.id}  {inc.severity:<8}  {inc.service:<12}  SLA@{inc.sla_deadline}{tag_str}")

    action_fn = greedy_action_task4 if task_id == 4 else greedy_action

    done = False
    while not done:
        action = action_fn(state)
        if action is None:
            break
        state, reward, done, info = env.step(action)

        extras = []
        if info.get("cascades_triggered"):     extras.append(f"cascade={info['cascades_triggered']}")
        if info.get("auto_escalated"):         extras.append(f"escalated-sev={info['auto_escalated']}")
        if info.get("sla_breached_this_step"): extras.append(f"SLA-breach={info['sla_breached_this_step']}")
        if info.get("root_cause_resolved"):    extras.append(f"auto-resolved={info['root_cause_resolved']}")
        if info.get("new_arrivals"):           extras.append(f"new={info['new_arrivals']}")
        if info.get("false_alarm_revealed"):   extras.append("false-alarm-revealed")
        if info.get("ack_auto_escalated"):     extras.append(f"ack-escalated={info['ack_auto_escalated']}")
        if info.get("grader_feedback"):        extras.append(f"feedback={info['grader_feedback'][:60]}")

        print(
            f"  step {info['step']:>2}  {info['action_type']:<16}  {info['incident_id']:<14}"
            f"  sev={info['incident_severity']:<8}  score={info['score']:.3f}  reward={reward:+.3f}"
            + (f"\n           {' | '.join(extras)}" if extras else "")
        )

    print(f"  FINAL score={state.score:.3f}  sla_breaches={state.sla_breaches}  total_incidents={len(state.incidents)}")

    # Assertions
    assert 0.0 <= state.score <= 1.0, f"Score out of range: {state.score}"
    assert state.sla_breaches >= 0
    for inc in state.incidents:
        assert inc.status in (
            "open", "pending", "in_progress", "resolved", "escalated", "dismissed"
        ), f"Unexpected status: {inc.status}"

    return state.score


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    scores = {}
    for task_id in [1, 2, 3, 4]:
        scores[task_id] = run_task(task_id)

    print("\n── Summary ──────────────────────────────────────────")
    for task_id, score in scores.items():
        print(f"  Task {task_id}: {score:.3f}")
    print("All assertions passed.")