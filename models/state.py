from pydantic import BaseModel
from typing import List
from .incident import Incident


class State(BaseModel):
    incidents: List[Incident]
    task_id: int = 1
    step: int = 0
    max_steps: int = 15
    score: float = 0.0
