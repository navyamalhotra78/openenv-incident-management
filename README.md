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
Multiple incidents requiring the full SRE workflow per incident. 20 steps. Each incident must go through: `triage` → `investigate` → `execute_fix` → `write_postmortem` → `resolve`. Skipping steps is penalised.

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

```json
{ "type": "<action_type>", "incident_id": "INC-001", ...payload }
```

| Action | Payload fields | Effect |
|--------|---------------|--------|
| `resolve` | — | Marks incident resolved. Full score credit. |
| `escalate` | — | Hands off to on-call. Partial score credit. |
| `mitigate` | — | Resets age to 0, status → pending. Prevents cascade for 2 more steps (Task 3). |
| `investigate` | `root_cause` (str) | Identifies root cause OR confirms/dismisses false alarm. |
| `triage` | `severity`, `team` | Classifies severity and assigns owning team (Task 4). |
| `execute_fix` | `fixes` (list) | Applies ordered remediation steps after root cause found (Task 4). |
| `write_postmortem` | `postmortem` (str) | Submits post-mortem document after fixing (Task 4). |
| `ignore` | — | No change. Clock advances. Penalised. |

---

## Reward Function

The reward function (`env/rewards.py`) provides dense, shaped signals across the full trajectory.

| Signal | Reward | Notes |
|--------|--------|-------|
| Resolve critical incident | up to +1.00 | Severity-weighted |
| Resolve low incident | up to +0.10 | Weighted down intentionally |
| Speed bonus | up to +0.30 | Finish early = bigger bonus |
| Triage accuracy | up to +0.40 | Grader-scored: severity + team |
| Root cause accuracy | up to +0.40 | Exact match or partial credit |
| Fix correctness + ordering | up to +0.60 | Order matters |
| Post-mortem quality | up to +0.50 | Root cause, timeline, prevention, action items |
| SLA breach | −0.40 × severity | Took too long |
| Cascade triggered | −0.25 per cascade | Inaction caused downstream failures |
| Auto-escalation (severity upgrade) | −0.15 | Incident worsened due to neglect |
| Resolving low before critical open | −0.10 | Prioritisation penalty (Task 2) |
| Task 4: skip postmortem | −0.25 | Can't shortcut the lifecycle |
| Ignore a critical | −0.30 | Extra penalty |
| Per step | −0.01 | Time pressure |

---

## Grader Scores

Each task has a grader in `env/tasks/task{1,2,3,4}.py` that returns a score in `[0.0, 1.0]` after every step, available as `state.score` and `info["score"]`.

Severity weights used by Task 2, 3, and 4 graders:

| Severity | Weight |
|----------|--------|
| critical | 0.4 |
| high | 0.3 |
| medium | 0.2 |
| low | 0.1 |

---

## API

| Method | Path | Body / Header | Description |
|--------|------|---------------|-------------|
| `POST` | `/reset` | `{ "task_id": 1 }` | Start a new episode. Returns `session_id` + initial state. |
| `POST` | `/step` | action body + `X-Session-Id` header | Take one action. Returns state, reward, done, info. |
| `GET` | `/state` | `X-Session-Id` header | Current environment state. |
| `GET` | `/tasks` | — | List all 4 tasks with metadata. |
| `DELETE` | `/session/{id}` | — | Release a session when done. |

`/reset` response:
```json
{ "session_id": "abc-123", "state": { ... } }
```

`/step` response:
```json
{ "state": {...}, "reward": 0.45, "done": false, "info": { "grader_feedback": "...", ... } }
```

Sessions are tracked server-side via `X-Session-Id` header, supporting up to 100 concurrent sessions.

---

## Setup

**Requirements:** Python 3.11+

```bash
pip install -r requirements.txt
uvicorn api.main:app --reload
```

Open `http://127.0.0.1:8000` for the dashboard UI.

**Docker:**
```bash
docker build -t incident-env .
docker run -p 8000:8000 incident-env
```

---

## Running the Inference Script

```bash
export HF_TOKEN=your_token
export ENV_BASE_URL=http://localhost:8000   # or your HF Space URL
export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct
python inference.py
```

Runs an LLM agent across all 4 tasks and emits structured `[START]` / `[STEP]` / `[END]` logs.

**Run the greedy baseline agent:**
```bash
python run_baseline.py
```

**Smoke-test the environment:**
```bash
python test_env.py
```

---

## Project Structure

```
api/
  main.py                   FastAPI app, route definitions, session management
env/
  environment.py            IncidentEnv class (reset / step / get_state)
  generator.py              Task-specific incident generation
  graders.py                Shared grader logic (triage, RCA, remediation, postmortem)
  rewards.py                Shaped reward function
  constants.py              SLA deadlines, escalation thresholds, severity configs
  incident_templates.py     Real-world incident scenarios with logs and metrics
  tasks/
    task1.py                Easy task config + grader
    task2.py                Medium task config + grader
    task3.py                Hard task config + grader + cascade dependencies
    task4.py                Very hard task config + grader (full lifecycle)
models/
  incident.py               Incident model
  state.py                  State model
  action.py                 Action model
  task_config.py            TaskConfig model
ui/
  index.html                Dashboard UI
  script.js                 Client-side logic
  styles.css                Styles
client.py                   HTTP client for agents (session-aware)
inference.py                LLM inference script (OpenAI API client)
run_baseline.py             Greedy baseline agent
test_env.py                 Smoke tests for all 4 tasks
openenv.yaml                OpenEnv environment manifest
requirements.txt            Python dependencies
Dockerfile                  Container configuration
README.md                   This file
```

---

## Baseline Scores

| Task | Difficulty | Greedy Baseline |
|------|-----------|----------------|
| 1 | Easy | 1.000 |
| 2 | Medium | 1.000 |
| 3 | Hard | 1.000 |
| 4 | Very Hard | 1.000 |