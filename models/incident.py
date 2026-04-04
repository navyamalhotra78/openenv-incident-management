from pydantic import BaseModel
from typing import Literal, Optional


class Incident(BaseModel):
    id: str
    severity: Literal["low", "medium", "high", "critical"]
    service: Literal["auth", "payments", "trading", "ui", "database", "api-gateway"]
    status: Literal["open", "pending", "resolved", "escalated"]
    age: int = 0
    is_cascade: bool = False
    parent_id: Optional[str] = None
