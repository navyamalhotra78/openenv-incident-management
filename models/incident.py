from pydantic import BaseModel
from typing import Literal

class Incident(BaseModel):
    id: str
    severity: Literal["low", "medium", "high", "critical"]
    service: Literal["auth", "payments", "trading", "ui"]
    status: Literal["open", "pending", "resolved"]