"""
env/rewards.py — Reward function for IncidentManagementEnv
===========================================================

Replace the `reward = 0.1` placeholder in environment.py with:

    from env.rewards import compute_reward
    reward = compute_reward(action, incident, info, state, task_id, steps, max_steps)

Design principles:
  - Severity-weighted: critical incidents matter more than low ones
  - Progress-shaped: partial credit at each lifecycle stage (triage → investigate → fix → postmortem)
  - Time-sensitive: earlier resolutions earn bonuses; SLA breaches penalise
  - Cascade-aware: preventing cascades is rewarded; causing them (via inaction) is penalised
  - Anti-gaming: ignoring incidents and premature resolves are penalised
  - Bounded: reward is clipped to [-1.0, 2.0] per step
"""

from __future__ import annotations
from typing import Any, Dict


# ─── Severity weights ─────────────────────────────────────────────────────────
# Used to scale all rewards by how critical the affected incident is.

SEVERITY_WEIGHT = {
    "critical": 1.0,
    "high":     0.6,
    "medium":   0.3,
    "low":      0.1,
}

# ─── Per-action base rewards ──────────────────────────────────────────────────

# These are BEFORE severity scaling. Final reward = base * severity_weight + bonuses - penalties.

ACTION_BASE = {
    # Full resolution — best outcome
    "resolve":          1.0,

    # Escalation — valid but suboptimal (hands off to someone else)
    "escalate":         0.3,

    # Mitigation — buys time, prevents cascade; good in Task 3
    "mitigate":         0.25,

    # Investigation — necessary lifecycle step
    "investigate":      0.2,

    # Triage — first step, scored by grader accuracy
    "triage":           0.2,

    # Fix execution — scored by grader (validity + ordering)
    "execute_fix":      0.4,

    # Post-mortem — required for Task 4, scored by grader quality
    "write_postmortem": 0.35,

    # Ignore — actively unhelpful
    "ignore":          -0.15,
}


def compute_reward(
    action_type: str,
    incident: Any,           # The Incident model object acted upon
    info: Dict[str, Any],    # The full info dict from env.step()
    state: Any,              # The current State object
    task_id: int,
    steps: int,
    max_steps: int,
) -> float:
    """
    Compute a meaningful, shaped reward for one environment step.

    Args:
        action_type:  The action that was just taken (e.g. "resolve", "triage")
        incident:     The Incident object that was acted upon
        info:         The info dict returned by IncidentEnv.step()
        state:        The current State after the action
        task_id:      Current task (1–4)
        steps:        Current step number (1-indexed)
        max_steps:    Maximum steps for this episode

    Returns:
        reward: float, clipped to [-1.0, 2.0]
    """

    reward = 0.0
    sev    = info.get("severity_before", "low")   # severity at time of action
    weight = SEVERITY_WEIGHT.get(sev, 0.1)

    status_before = info.get("status_before", "open")
    status_after  = info.get("status_after",  "open")
    terminal      = {"resolved", "escalated", "dismissed"}

    # ── 1. Base action reward (severity-scaled) ───────────────────────────────

    base = ACTION_BASE.get(action_type, 0.0)

    # For graded actions, replace the flat base with the actual grader score
    if action_type == "triage":
        grader_score = info.get("triage_score", 0.0) or 0.0
        base = grader_score * 0.4           # max 0.4 for perfect triage

    elif action_type == "investigate":
        grader_score = info.get("root_cause_score", 0.0) or 0.0
        base = grader_score * 0.4           # max 0.4 for exact root cause

    elif action_type == "execute_fix":
        grader_score = info.get("remediation_score", 0.0) or 0.0
        base = grader_score * 0.6           # max 0.6 — fixing is the core task

    elif action_type == "write_postmortem":
        grader_score = info.get("postmortem_score", 0.0) or 0.0
        base = grader_score * 0.5           # max 0.5 for excellent post-mortem

    elif action_type == "resolve":
        # Only give full credit if we actually just resolved it this step
        if status_after == "resolved" and status_before != "resolved":
            base = ACTION_BASE["resolve"]
        elif status_after != "resolved":
            # Tried to resolve but couldn't (prerequisites not met)
            base = -0.3
        else:
            base = 0.0   # already resolved, double action

    reward += base * weight

    # ── 2. Resolution speed bonus ─────────────────────────────────────────────
    # Reward finishing the incident well before the step budget runs out.

    if status_after == "resolved" and status_before != "resolved":
        steps_remaining = max_steps - steps
        speed_bonus = 0.3 * (steps_remaining / max_steps)   # up to +0.3
        reward += speed_bonus * weight

    # ── 3. SLA breach penalty ─────────────────────────────────────────────────
    # Each incident that breaches its SLA this step costs proportional to severity.

    newly_breached = info.get("sla_breached_this_step", [])
    if newly_breached:
        # Penalise for the incident we acted on if it breached
        if incident.id in newly_breached:
            reward -= 0.4 * weight
        # Additional flat penalty per extra breach (other incidents also breaching)
        other_breaches = [b for b in newly_breached if b != incident.id]
        reward -= 0.1 * len(other_breaches)

    # ── 4. Cascade penalty ────────────────────────────────────────────────────
    # If our inaction on this incident caused a cascade, penalise.

    cascades = info.get("cascades_triggered", [])
    if cascades:
        reward -= 0.25 * len(cascades)

    # ── 5. Auto-escalation penalty ────────────────────────────────────────────
    # Severity upgraded automatically because we didn't handle it fast enough.

    auto_escalated = info.get("auto_escalated", [])
    if incident.id in auto_escalated:
        reward -= 0.15 * weight

    # ── 6. Unacknowledged critical penalty ────────────────────────────────────
    # Leaving critical/high incidents unacknowledged is bad practice.

    unacked = info.get("unacknowledged_criticals", 0)
    if unacked > 0:
        reward -= 0.05 * unacked

    # ── 7. False alarm bonus ──────────────────────────────────────────────────
    # Correctly dismissing a false alarm saves resources.

    if info.get("false_alarm_revealed") and status_after == "dismissed":
        reward += 0.2

    # ── 8. Ignore penalty ─────────────────────────────────────────────────────
    # Stronger penalty for ignoring critical incidents.

    if action_type == "ignore":
        reward += ACTION_BASE["ignore"] * weight  # already in base, but boost for critical
        if sev == "critical":
            reward -= 0.15   # extra penalty

    # ── 9. Task-specific shaping ──────────────────────────────────────────────

    if task_id == 1:
        # Task 1 is simple — bonus for resolving the single incident cleanly
        if status_after == "resolved":
            reward += 0.2

    elif task_id == 2:
        # Task 2: severity-weighted queue — bonus for clearing criticals first
        if status_after == "resolved" and sev == "critical":
            reward += 0.15
        # Small penalty for resolving low before critical still open
        open_severities = [
            i.severity for i in state.incidents
            if i.status not in terminal and i.id != incident.id
        ]
        if status_after == "resolved" and sev == "low" and "critical" in open_severities:
            reward -= 0.1   # prioritisation penalty

    elif task_id == 3:
        # Task 3: cascade prevention — mitigate buys 2 steps and is rewarded above
        # Extra bonus if mitigate prevented a cascade (would have triggered without it)
        if action_type == "mitigate" and not cascades:
            reward += 0.15 * weight
        # Bonus for resolving root cause (which auto-resolves symptoms)
        root_resolved = info.get("root_cause_resolved", [])
        if root_resolved:
            reward += 0.2 * len(root_resolved)

    elif task_id == 4:
        # Task 4: full lifecycle — reward each milestone
        if action_type == "triage" and getattr(incident, "triage_done", False):
            reward += 0.1
        if action_type == "investigate" and getattr(incident, "root_cause_found", False):
            reward += 0.15
        if action_type == "execute_fix" and getattr(incident, "remediation_done", False):
            reward += 0.2
        if action_type == "write_postmortem" and getattr(incident, "postmortem_done", False):
            reward += 0.2
        # Penalty for skipping steps (e.g. trying to resolve without postmortem)
        if action_type == "resolve" and not getattr(incident, "postmortem_done", False):
            reward -= 0.25

    # ── 10. Step budget pressure ──────────────────────────────────────────────
    # Small per-step cost to encourage efficiency.

    reward -= 0.01

    # ── Clip and round ────────────────────────────────────────────────────────
    return round(max(-1.0, min(2.0, reward)), 4)