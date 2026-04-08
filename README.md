---
title: Incident Management Env
emoji: 🚨
colorFrom: red
colorTo: blue
sdk: docker
pinned: false
---

# Incident Management — OpenEnv

A reinforcement learning environment simulating real-world IT incident management. An AI agent acts as an on-call Site Reliability Engineer (SRE), triaging alerts, diagnosing root causes, applying fixes, and writing post-mortems across four tasks of increasing difficulty.

---

## Environment Description

Production systems fail. Alerts fire. Your agent decides what to do.

At every step the agent receives the current state — a list of active incidents, each with a service, severity, status, age, and logs — and takes one action on one incident. The episode ends when all incidents are handled or the step budget runs out.

**Task 1 — Single Alert Triage (Easy)**
One incident, 5 steps. Investigate to confirm it is real, then resolve or escalate.

**Task 2 — Multi-Service Queue (Medium)**
Four incidents of mixed severity across different services. 15 steps. Score is weighted by severity — critical incidents matter most. One incident may be a false alarm.

**Task 3 — Cascading Failure Response (Hard)**
Three initial incidents on interdependent services. 14 steps. Unhandled critical/high incidents age each step and trigger cascade incidents on downstream services after 2 steps. Use `mitigate` to buy time without fully resolving.

**Task 4 — Full Incident Lifecycle (Very Hard)**
One incident requiring the full SRE workflow. 10 steps. Each incident must go through: `triage` → `investigate` → `execute_fix` → `write_postmortem` → `resolve`. Skipping steps is penalised.

---

## Observation Space

```json
{
  "incidents": [
    {
      "id": "INC-001",
      "severity": "critical | high | medium | low",
      "service": "auth | payments | trading | ui | database | api-gateway",
      "status": "open | pending | in_progress | resolved | escalated | dismissed",
      "age": 0,
      "is_cascade": false,
      "is_false_alarm": false,
      "parent_id": null,
      "root_cause_id": null,
      "sla_deadline": 4,
      "sla_breached": false,
      "acknowledged": false,
      "triage_done": false,
      "root_cause_found": false,
      "remediation_done": false,
      "postmortem_done": false
    }
  ],
  "task_id": 1,
  "step": 0,
  "max_steps": 5,
  "score": 0.0,
  "sla_breaches": 0,
  "available_actions": ["resolve", "escalate", "investigate", "ignore"]
}
```

---

## Action Space

| Action | Payload | Effect |
|--------|---------|--------|
| `resolve` | — | Marks incident resolved. Full score credit. |
| `escalate` | — | Hands off to on-call. Partial credit. |
| `mitigate` | — | Resets age to 0, prevents cascade for 2 steps (Task 3). |
| `investigate` | `root_cause` (str) | Identifies root cause OR confirms/dismisses false alarm. |
| `triage` | `severity`, `team` | Classifies severity and assigns owning team (Task 4). |
| `execute_fix` | `fixes` (list) | Applies ordered remediation steps (Task 4). |
| `write_postmortem` | `postmortem` (str) | Submits post-mortem document (Task 4). |
| `ignore` | — | No change. Clock advances. Penalised. |

---

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/reset` | Start a new episode. Returns `session_id` + initial state. |
| `POST` | `/step` | Take one action. Pass `X-Session-Id` header. |
| `GET` | `/state` | Current environment state. |
| `GET` | `/tasks` | List all 4 tasks. |
| `DELETE` | `/session/{id}` | Release session when done. |

---

## Setup

```bash
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 7860
```

**Docker:**
```bash
docker build -t incident-env .
docker run -p 7860:7860 incident-env
```

---

## Baseline Scores

| Task | Difficulty | Greedy Baseline |
|------|-----------|----------------|
| 1 | Easy | 1.000 |
| 2 | Medium | 1.000 |
| 3 | Hard | 1.000 |
| 4 | Very Hard | 1.000 |