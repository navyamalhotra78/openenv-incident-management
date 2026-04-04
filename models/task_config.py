from pydantic import BaseModel


class TaskConfig(BaseModel):
    task_id: int
    name: str
    difficulty: str
    description: str
    max_steps: int
    n_incidents: int
