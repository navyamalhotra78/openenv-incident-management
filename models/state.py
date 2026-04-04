from pydantic import BaseModel
from typing import List
from .incident import Incident

class State(BaseModel):
    incidents: List[Incident]