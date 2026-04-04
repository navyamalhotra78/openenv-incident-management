from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from env.environment import IncidentEnv
from models.action import Action

app = FastAPI()
env = IncidentEnv()

app.mount("/", StaticFiles(directory="ui", html=True), name="ui")

@app.post("/reset")
def reset():
    state = env.reset()
    return state

@app.post("/step")
def step(action: Action):
    state, reward, done, info = env.step(action)
    return {
        "state": state,
        "reward": reward,
        "done": done,
        "info": info
    }

@app.get("/state")
def get_state():
    return env.get_state()