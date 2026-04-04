"""
IncidentManagementClient — OpenEnv-compatible environment client.

Usage:
    from client import IncidentManagementClient

    client = IncidentManagementClient()          # default: localhost:8000
    state  = client.reset(task_id=1)
    while True:
        obs, reward, done, info = client.step({
            "type": "resolve",
            "incident_id": "INC-001",
        })
        if done:
            break

The client wraps the HTTP API so agents interact with a clean Python interface
rather than constructing raw HTTP requests.
"""

import requests


class IncidentManagementClient:
    """
    HTTP client for the Incident Management OpenEnv environment.

    Implements the standard OpenEnv interface:
        reset(**kwargs)  -> observation (dict)
        step(action)     -> (observation, reward, done, info)
        state()          -> current observation (dict)
        tasks()          -> list of available task configs
    """

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self._session_id: str | None = None
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    # ── Core interface ────────────────────────────────────────────────────────

    def reset(self, task_id: int = 1) -> dict:
        """
        Start a new episode.

        Args:
            task_id: 1 (easy) | 2 (medium) | 3 (hard) | 4 (very hard)

        Returns:
            Initial observation (state dict with incidents, step, score, etc.)
        """
        body = {"task_id": task_id}
        if self._session_id:
            body["session_id"] = self._session_id
        resp = self._post("/reset", body)
        self._session_id = resp["session_id"]
        # Attach session ID to all subsequent requests via header
        self._session.headers["X-Session-Id"] = self._session_id
        return resp["state"]

    def step(self, action: dict) -> tuple[dict, float, bool, dict]:
        """
        Execute one action.

        Args:
            action: dict with keys:
                type        — "resolve" | "escalate" | "ignore" | "mitigate"
                              | "investigate" | "triage" | "execute_fix" | "write_postmortem"
                incident_id — ID of the target incident (e.g. "INC-001")

                Optional payload keys (depending on action type):
                  severity   — for triage
                  team       — for triage
                  root_cause — for investigate
                  fixes      — list[str] for execute_fix
                  postmortem — str for write_postmortem

        Returns:
            (observation, reward, done, info)
        """
        resp = self._post("/step", action)
        return resp["state"], resp["reward"], resp["done"], resp["info"]

    def state(self) -> dict:
        """Return the current environment state without advancing a step."""
        return self._get("/state")

    def tasks(self) -> list[dict]:
        """List all available tasks with metadata (id, name, difficulty, max_steps)."""
        return self._get("/tasks")

    # ── Convenience helpers ───────────────────────────────────────────────────

    def run_episode(self, task_id: int, agent_fn) -> tuple[float, list[dict]]:
        """
        Run a full episode with a given agent function.

        Args:
            task_id:  which task to run
            agent_fn: callable(state) -> action dict

        Returns:
            (final_score, history)
            history is a list of dicts: {action, reward, done, info}
        """
        state   = self.reset(task_id=task_id)
        history = []
        done    = False

        while not done:
            action = agent_fn(state)
            if action is None:
                break
            state, reward, done, info = self.step(action)
            history.append({"action": action, "reward": reward, "done": done, "info": info})

        return state.get("score", 0.0), history

    # ── Internal ──────────────────────────────────────────────────────────────

    def _post(self, path: str, body: dict) -> dict:
        resp = self._session.post(f"{self.base_url}{path}", json=body)
        resp.raise_for_status()
        return resp.json()

    def _get(self, path: str) -> dict | list:
        resp = self._session.get(f"{self.base_url}{path}")
        resp.raise_for_status()
        return resp.json()

    def close(self):
        """Release the server-side session when done."""
        if self._session_id:
            try:
                self._session.delete(f"{self.base_url}/session/{self._session_id}")
            except Exception:
                pass
            self._session_id = None

    def __repr__(self) -> str:
        return f"IncidentManagementClient(base_url={self.base_url!r}, session_id={self._session_id!r})"
