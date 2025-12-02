# app/schemas/policy.py
from pydantic import BaseModel
from uuid import UUID
from typing import List, Optional


class Bedtime(BaseModel):
    start: str  # "21:30"
    end: str    # "07:00"


class PolicyResponse(BaseModel):
    user_id: UUID
    daily_limit_minutes: int
    blocked_apps: List[str] = []
    bedtime: Optional[Bedtime] = None
