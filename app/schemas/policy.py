from pydantic import BaseModel
from uuid import UUID
from typing import List, Optional
from datetime import time

class PolicySettingsRequest(BaseModel):
    daily_limit_minutes: int
    bedtime_start: str      
    bedtime_end: str        
    weekend_relax_pct: int  
    
class Bedtime(BaseModel):
    start: str
    end: str

class PolicyResponse(BaseModel):
    user_id: UUID
    daily_limit_minutes: int
    blocked_apps: List[str] = []
    bedtime: Optional[Bedtime] = None
    weekend_extra_minutes: int = 0  