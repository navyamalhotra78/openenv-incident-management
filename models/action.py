from pydantic import BaseModel
from typing import Literal


class Action(BaseModel):
    type: Literal["resolve", "escalate", "ignore", "mitigate"]
    incident_id: str
