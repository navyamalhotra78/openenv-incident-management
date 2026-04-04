from pydantic import BaseModel
from typing import Literal


class Action(BaseModel):
    type: Literal["resolve", "escalate", "ignore", "mitigate", "investigate"]
    incident_id: str
