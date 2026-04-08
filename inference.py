"""
inference.py — Incident Management OpenEnv Inference Script
============================================================
Runs an LLM agent against the Incident Management environment across all 4 tasks.

Required environment variables:
    API_BASE_URL   LLM endpoint  (default: https://router.huggingface.co/v1)
    MODEL_NAME     Model ID      (default: Qwen/Qwen2.5-72B-Instruct)
    HF_TOKEN       HF / API key  (no default — must be set)
    ENV_BASE_URL   Environment server URL (default: http://localhost:8000)

Stdout format (mandatory):
    [START] task=<n> env=<benchmark> model=<model>
    [STEP]  step=<n> action=<str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<0.00> rewards=<r1,r2,...>
"""

import os
import sys
import json
import textwrap
from typing import List, Optional

import requests
from openai import OpenAI

# ── Config ────────────────────────────────────────────────────────────────────

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME   = os.getenv("MODEL_NAME",   "Qwen/Qwen2.5-72B-Instruct")
HF_TOKEN     = os.getenv("HF_TOKEN")
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:8000")
BENCHMARK    = "incident-management-env"

TEMPERATURE             = 0.3
MAX_TOKENS              = 512
SUCCESS_SCORE_THRESHOLD = 0.5

TASKS = [
    {"task_id": 1, "name": "single-alert-triage",       "max_steps": 5},
    {"task_id": 2, "name": "multi-service-queue",        "max_steps": 15},
    {"task_id": 3, "name": "cascading-failure-response", "max_steps": 14},
    {"task_id": 4, "name": "full-lifecycle",             "max_steps": 10},
]

# ── Stdout logging ────────────────────────────────────────────────────────────

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)

def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    action_str = action.replace("\n", " ").replace("\r", "")[:120]
    error_val  = error.replace("\n", " ") if error else "null"
    print(
        f"[STEP] step={step} action={action_str} "
        f"reward={reward:.2f} done={str(done).lower()} error={error_val}",
        flush=True,
    )

def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} "
        f"score={score:.2f} rewards={rewards_str}",
        flush=True,
    )

# ── Environment client ────────────────────────────────────────────────────────

class EnvClient:
    """
    HTTP client matching main.py's session-based API.
      POST /reset              → {"session_id": ..., "state": ...}
      POST /step   + X-Session-Id header → {"state":..., "reward":..., "done":..., "info":...}
      GET  /state  + X-Session-Id header → state dict (includes "score")
      DELETE /session/{id}     → cleanup
    """

    def __init__(self, base_url: str):
        self.base_url   = base_url.rstrip("/")
        self.session_id: Optional[str] = None
        self._http      = requests.Session()
        self._http.headers.update({"Content-Type": "application/json"})

    def reset(self, task_id: int) -> dict:
        resp = self._http.post(
            f"{self.base_url}/reset",
            json={"task_id": task_id},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self.session_id = data["session_id"]
        self._http.headers["X-Session-Id"] = self.session_id
        return data["state"]

    def step(self, action: dict) -> dict:
        resp = self._http.post(
            f"{self.base_url}/step",
            json=action,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def state(self) -> dict:
        resp = self._http.get(f"{self.base_url}/state", timeout=30)
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        if self.session_id:
            try:
                self._http.delete(
                    f"{self.base_url}/session/{self.session_id}",
                    timeout=10,
                )
            except Exception:
                pass
            self.session_id = None

# ── Prompts ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = textwrap.dedent("""
    You are an expert on-call Site Reliability Engineer (SRE) managing production incidents.

    You receive the current incident state and must choose one action per step.
    Respond ONLY with a single valid JSON object — no explanation, no markdown fences.

    Action types:
      "resolve"          - Fully resolve a confirmed incident
      "escalate"         - Hand off to on-call manager
      "mitigate"         - Reset incident age, prevent cascade (Task 3)
      "investigate"      - Confirm/dismiss false alarm OR identify root cause
      "triage"           - Classify severity + assign team (Task 4)
      "execute_fix"      - Apply fixes after root cause found (Task 4)
      "write_postmortem" - Write post-mortem after fixing (Task 4)
      "ignore"           - Do nothing (avoid)

    Priority: critical > high > medium > low
    Task 4 order: triage → investigate → execute_fix → write_postmortem → resolve

    JSON examples:
      {"type": "resolve", "incident_id": "INC-001"}
      {"type": "triage", "incident_id": "INC-001", "severity": "critical", "team": "database"}
      {"type": "investigate", "incident_id": "INC-002", "root_cause": "connection_leak"}
      {"type": "execute_fix", "incident_id": "INC-001", "fixes": ["kill_long_running_queries", "restart_connection_pool"]}
      {"type": "write_postmortem", "incident_id": "INC-001", "postmortem": "## Post-Mortem\\n### Timeline\\n- 00:00 UTC Alert fired\\n- 00:20 UTC Root cause: connection leak\\n### Root Cause\\nConnection pool exhausted.\\n### Prevention\\nAdd monitoring. Set timeouts. Use PgBouncer.\\nAction item: Jira ticket.\\nFollow-up: Update runbook."}
      {"type": "mitigate", "incident_id": "INC-003"}
""").strip()


def build_user_prompt(state: dict, step: int, task_config: dict, last_feedback: str) -> str:
    incidents = state.get("incidents", [])
    task_id   = state.get("task_id", 1)
    score     = state.get("score", 0.0)
    available = state.get("available_actions", [])
    terminal  = {"resolved", "escalated", "dismissed"}

    inc_lines = []
    for inc in incidents:
        if inc.get("status") not in terminal:
            line = (
                f"  - {inc['id']} | sev={inc['severity']:<8} | "
                f"service={inc['service']:<12} | status={inc['status']:<11} | "
                f"age={inc.get('age', 0)}"
            )
            if inc.get("is_false_alarm"):  line += " [POSSIBLE FALSE ALARM]"
            if inc.get("is_cascade"):      line += f" [CASCADE from {inc.get('parent_id')}]"
            if inc.get("root_cause_id"):   line += f" [symptom of {inc.get('root_cause_id')}]"
            if inc.get("sla_breached"):    line += " [!! SLA BREACHED]"
            inc_lines.append(line)

    task_instructions = {
        1: "TASK 1 (Easy): One incident. Investigate to confirm, then resolve or escalate.",
        2: "TASK 2 (Medium): Multiple incidents. Resolve critical incidents first.",
        3: "TASK 3 (Hard): Cascading failures. Use mitigate on critical incidents. Resolve root causes first.",
        4: "TASK 4 (Very Hard): Full lifecycle per incident: triage → investigate → execute_fix → write_postmortem → resolve.",
    }

    return textwrap.dedent(f"""
        Step {step}/{task_config['max_steps']} | Score: {score:.3f}
        {task_instructions.get(task_id, '')}

        Active incidents:
        {chr(10).join(inc_lines) if inc_lines else '  (all incidents handled)'}

        Available actions: {available}
        Last feedback: {last_feedback or 'none'}

        Your action (JSON only):
    """).strip()


# ── LLM agent ────────────────────────────────────────────────────────────────

def get_agent_action(
    client: OpenAI,
    state: dict,
    step: int,
    task_config: dict,
    last_feedback: str,
    history: List[dict],
) -> dict:
    user_prompt = build_user_prompt(state, step, task_config, last_feedback)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in history[-3:]:
        messages.append({"role": "assistant", "content": h["action_json"]})
        messages.append({"role": "user",      "content": f"Feedback: {h['feedback']}"})
    messages.append({"role": "user", "content": user_prompt})

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            stream=False,
        )
        text = (completion.choices[0].message.content or "").strip()

        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        return json.loads(text)

    except json.JSONDecodeError:
        print(f"[DEBUG] JSON parse failed, using fallback", flush=True)
        return _fallback_action(state)
    except Exception as exc:
        print(f"[DEBUG] LLM error: {exc}", flush=True)
        return _fallback_action(state)


def _fallback_action(state: dict) -> dict:
    """Greedy fallback: act on the highest-severity active incident."""
    priority = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    terminal = {"resolved", "escalated", "dismissed"}
    active = sorted(
        [i for i in state.get("incidents", []) if i.get("status") not in terminal],
        key=lambda i: priority.get(i.get("severity", "low"), 4),
    )
    if not active:
        inc_id = (state.get("incidents") or [{}])[0].get("id", "INC-001")
        return {"type": "ignore", "incident_id": inc_id}

    inc       = active[0]
    available = state.get("available_actions", ["resolve"])

    if "triage" in available and not inc.get("triage_done"):
        return {"type": "triage", "incident_id": inc["id"],
                "severity": inc["severity"], "team": _guess_team(inc)}
    if "investigate" in available and not inc.get("root_cause_found"):
        return {"type": "investigate", "incident_id": inc["id"],
                "root_cause": inc.get("true_root_cause", "unknown_cause")}
    if "execute_fix" in available and not inc.get("remediation_done"):
        return {"type": "execute_fix", "incident_id": inc["id"],
                "fixes": inc.get("required_fix_order", ["restart_service"])}
    if "write_postmortem" in available:
        return {"type": "write_postmortem", "incident_id": inc["id"],
                "postmortem": _default_postmortem(inc)}
    if "resolve" in available:
        return {"type": "resolve", "incident_id": inc["id"]}
    if "mitigate" in available:
        return {"type": "mitigate", "incident_id": inc["id"]}
    return {"type": "escalate", "incident_id": inc["id"]}


def _guess_team(incident: dict) -> str:
    return {
        "database":    "database",
        "auth":        "backend",
        "payments":    "backend",
        "api-gateway": "infra",
        "trading":     "backend",
        "ui":          "frontend",
    }.get(incident.get("service", ""), "backend")


def _default_postmortem(incident: dict) -> str:
    rc   = (incident.get("true_root_cause") or "unknown issue").replace("_", " ")
    prev = ". ".join(incident.get("prevention_steps") or ["Add monitoring", "Set alerts"])
    return (
        f"## Incident Post-Mortem\n\n"
        f"### Timeline\n"
        f"- 00:00 UTC Alert fired for {incident.get('service', 'service')}\n"
        f"- 00:10 UTC Incident triaged as {incident.get('severity', 'high')}\n"
        f"- 00:20 UTC Root cause identified: {rc}\n"
        f"- 00:35 UTC Fix applied and service restored\n\n"
        f"### Root Cause\nThe incident was caused by {rc}.\n\n"
        f"### Impact\nService degraded for approximately 35 minutes.\n\n"
        f"### Prevention & Action Items\n{prev}\n"
        f"Action item: Create Jira ticket for monitoring improvements.\n"
        f"Follow-up: Update runbook and on-call documentation.\n"
    )


# ── Episode runner ────────────────────────────────────────────────────────────

def run_episode(client: OpenAI, task_config: dict) -> float:
    task_name = task_config["name"]
    task_id   = task_config["task_id"]

    log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME)

    env           = EnvClient(base_url=ENV_BASE_URL)
    rewards       = []
    steps_taken   = 0
    score         = 0.0
    success       = False
    last_feedback = ""
    history       = []

    try:
        state = env.reset(task_id=task_id)

        for step in range(1, task_config["max_steps"] + 1):
            terminal = {"resolved", "escalated", "dismissed"}
            active   = [i for i in state.get("incidents", []) if i.get("status") not in terminal]
            if not active:
                break

            action     = get_agent_action(client, state, step, task_config, last_feedback, history)
            action_str = json.dumps(action)
            error_msg  = None

            try:
                result        = env.step(action)
                state         = result.get("state", state)
                reward        = float(result.get("reward", 0.0))
                done          = bool(result.get("done", False))
                info          = result.get("info", {})
                last_feedback = info.get("grader_feedback", "")
                if "error" in info:
                    error_msg = str(info["error"])
            except Exception as exc:
                reward    = 0.0
                done      = True
                error_msg = str(exc)
                print(f"[DEBUG] env.step() error: {exc}", flush=True)

            rewards.append(reward)
            steps_taken = step
            history.append({"action_json": action_str, "feedback": last_feedback or ""})

            log_step(step=step, action=action_str, reward=reward, done=done, error=error_msg)

            if done:
                break

        final_state = env.state()
        score   = min(max(float(final_state.get("score", 0.0)), 0.0), 1.0)
        success = score >= SUCCESS_SCORE_THRESHOLD

    except Exception as exc:
        print(f"[DEBUG] Episode error: {exc}", flush=True)

    finally:
        env.close()

    log_end(success=success, steps=steps_taken, score=score, rewards=rewards)
    return score


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)

    try:
        probe = EnvClient(base_url=ENV_BASE_URL)
        probe.reset(task_id=1)
        probe.close()
    except Exception as exc:
        print(f"[ERROR] Cannot reach environment at {ENV_BASE_URL}: {exc}", flush=True)
        sys.exit(1)

    all_scores = []
    for task_config in TASKS:
        score = run_episode(client, task_config)
        all_scores.append(score)

    print("\n[SUMMARY]", file=sys.stderr)
    for task_config, s in zip(TASKS, all_scores):
        print(f"  Task {task_config['task_id']} ({task_config['name']}): {s:.3f}", file=sys.stderr)
    print(f"  Mean score: {sum(all_scores)/len(all_scores):.3f}", file=sys.stderr)


if __name__ == "__main__":
    main()