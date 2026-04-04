from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from env.environment import IncidentEnv
from env.tasks.task1 import TASK1_CONFIG
from env.tasks.task2 import TASK2_CONFIG
from env.tasks.task3 import TASK3_CONFIG
from models.action import Action

app = FastAPI(title="Incident Management OpenEnv", version="1.0.0")
env = IncidentEnv()


class ResetRequest(BaseModel):
    task_id: int = 1


@app.get("/")
def root():
    return FileResponse("ui/index.html")


@app.post("/reset")
def reset(req: ResetRequest = None):
    if req is None:
        req = ResetRequest()
    state = env.reset(task_id=req.task_id)
    return state


@app.post("/step")
def step(action: Action):
    state, reward, done, info = env.step(action)
    return {"state": state, "reward": reward, "done": done, "info": info}


@app.get("/state")
def get_state():
    return env.get_state()


@app.get("/tasks")
def list_tasks():
    return [TASK1_CONFIG, TASK2_CONFIG, TASK3_CONFIG]


# Serve static assets (CSS, JS) — must come after route definitions
app.mount("/static", StaticFiles(directory="ui"), name="static")
