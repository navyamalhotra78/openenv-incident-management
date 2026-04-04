import uuid
from fastapi import FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from env.environment import IncidentEnv
from env.tasks.task1 import TASK1_CONFIG
from env.tasks.task2 import TASK2_CONFIG
from env.tasks.task3 import TASK3_CONFIG
from env.tasks.task4 import TASK4_CONFIG
from models.action import Action

app = FastAPI(title="Incident Management OpenEnv", version="1.0.0")

# Per-session environment registry — keyed by session_id
_sessions: dict[str, IncidentEnv] = {}
MAX_SESSIONS = 100  # prevent unbounded memory growth


def _get_env(session_id: str) -> IncidentEnv:
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found — call /reset first")
    return _sessions[session_id]


class ResetRequest(BaseModel):
    task_id: int = 1
    session_id: Optional[str] = None   # client may pin a session; omit to get a fresh one


@app.get("/")
def root():
    return FileResponse("ui/index.html")


@app.post("/reset")
def reset(req: ResetRequest = None):
    if req is None:
        req = ResetRequest()

    # Reuse an existing session or create a new one
    session_id = req.session_id or str(uuid.uuid4())

    # Evict oldest session if at capacity
    if session_id not in _sessions and len(_sessions) >= MAX_SESSIONS:
        oldest = next(iter(_sessions))
        del _sessions[oldest]

    env = _sessions.setdefault(session_id, IncidentEnv())
    state = env.reset(task_id=req.task_id)
    return {"session_id": session_id, "state": state}


@app.post("/step")
def step(
    action: Action,
    x_session_id: Optional[str] = Header(default=None),
):
    """
    Pass session_id via the X-Session-Id header, or fall back to a
    single shared session for backwards compatibility with the UI.
    """
    if x_session_id:
        env = _get_env(x_session_id)
    elif _sessions:
        # UI / single-player fallback: use the most recently created session
        env = next(reversed(_sessions.values()))
    else:
        raise HTTPException(status_code=400, detail="No active session — call /reset first")

    state, reward, done, info = env.step(action)
    return {"state": state, "reward": reward, "done": done, "info": info}


@app.get("/state")
def get_state(x_session_id: Optional[str] = Header(default=None)):
    if x_session_id:
        env = _get_env(x_session_id)
    elif _sessions:
        env = next(reversed(_sessions.values()))
    else:
        return {"error": "No active session — call /reset first"}

    state = env.get_state()
    if state is None:
        return {"error": "Environment not initialised — call /reset first"}
    return state


@app.get("/tasks")
def list_tasks():
    return [TASK1_CONFIG, TASK2_CONFIG, TASK3_CONFIG, TASK4_CONFIG]


@app.delete("/session/{session_id}")
def close_session(session_id: str):
    """Explicitly release a session when the agent is done."""
    _sessions.pop(session_id, None)
    return {"deleted": session_id}


@app.get("/sessions")
def list_sessions():
    """Debug endpoint — shows active session count."""
    return {"active_sessions": len(_sessions)}


# Serve static assets — must come after route definitions
app.mount("/static", StaticFiles(directory="ui"), name="static")
