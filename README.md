# Incident Management — OpenEnv

A reinforcement learning environment simulating real-world IT incident management. An agent must triage, escalate, resolve, or mitigate service incidents across three tasks of increasing difficulty.

---

## Environment Description

Services go down. Alerts fire. Your agent decides what to do with each one.

At every step the agent receives the current state (list of incidents, each with a service, severity, and status) and takes one action on one incident. The episode ends when all incidents are handled or the step budget runs out.

**Task 1 — Single Alert Triage (Easy)**
One incident, 5 steps. Resolve, escalate, or mitigate it correctly.

**Task 2 — Multi-Service Queue (Medium)**
Four incidents — one of each severity (critical, high, medium, low) — across different services. 12 steps. Score is weighted by severity, so critical incidents matter most.

**Task 3 — Cascading Failure Response (Hard)**
Three initial incidents on interdependent services. 10 steps. Unhandled critical/high incidents age each step and trigger cascade incidents on downstream services after 2 steps. Use `mitigate` to buy time without resolving.

---

## Observation Space

```json
{
  "incidents": [
    {
      "id": "INC-001",
      "severity": "critical | high | medium | low",
      "service": "auth | payments | trading | ui | database | api-gateway",
      "status": "open | pending | resolved | escalated",
      "age": 0,
      "is_cascade": false,
      "parent_id": null
    }
  ],
  "task_id": 1,
  "step": 0,
  "max_steps": 5,
  "score": 0.0
}
```

## Action Space

```json
{ "type": "resolve | escalate | mitigate | ignore", "incident_id": "INC-001" }
```

| Action | Effect |
|--------|--------|
| `resolve` | Marks incident resolved. Full score credit. |
| `escalate` | Hands off to on-call. Partial score credit (50%). |
| `mitigate` | Resets incident age to 0, sets status to `pending`. Prevents cascade for 2 more steps (Task 3). |
| `ignore` | No change. Clock advances. |

---

## API

| Method | Path | Body | Description |
|--------|------|------|-------------|
| `POST` | `/reset` | `{ "task_id": 1 }` | Start a new episode |
| `POST` | `/step` | `{ "type": "resolve", "incident_id": "INC-001" }` | Take one action |
| `GET` | `/state` | — | Current environment state |
| `GET` | `/tasks` | — | List all tasks with metadata |

Returns from `/step`:
```json
{ "state": {...}, "reward": 0.1, "done": false, "info": {...} }
```

---

## Setup

**Requirements:** Python 3.11+, pip

```bash
pip install fastapi uvicorn pydantic
uvicorn api.main:app --reload
```

Open `http://127.0.0.1:8000` for the UI.

**Docker:**
```bash
docker build -t incident-env .
docker run -p 8000:8000 incident-env
```

---

## Running the Baseline Agent

```bash
python run_baseline.py
```

Runs a greedy agent (always resolves the highest-severity open incident) over 20 seeds per task and prints avg/min/max scores.

**Smoke-test the environment:**
```bash
python test_env.py
```

---

## Reward & Scoring

Each task has a grader (`env/tasks/task{1,2,3}.py`) that returns a score in `[0.0, 1.0]` after every step. The score is available as `state.score` and in `info["score"]`.

Severity weights used by Task 2 and Task 3 graders:

| Severity | Weight |
|----------|--------|
| critical | 0.4 |
| high | 0.3 |
| medium | 0.2 |
| low | 0.1 |

The per-step `reward` signal is separate from the grader score and is defined in `env/environment.py`.

---

## Project Structure

```
api/
  main.py               FastAPI app and route definitions
env/
  environment.py        IncidentEnv class (reset / step / get_state)
  generator.py          Task-specific incident generation
  tasks/
    task1.py            Easy task config + grader
    task2.py            Medium task config + grader
    task3.py            Hard task config + grader + cascade deps
models/
  incident.py           Incident model
  state.py              State model
  action.py             Action model
  task_config.py        TaskConfig model
ui/
  index.html            Dashboard UI
  script.js             Client-side logic
  styles.css            Styles
openenv.yaml            Full environment spec
run_baseline.py         Greedy baseline agent
test_env.py             Smoke tests for all 3 tasks
Dockerfile              Container config
```
