# app/schemas/policy.py
from pydantic import BaseModel
from uuid import UUID
from typing import List, Optional

# Ebeveyn ayarları değiştirdiğinde gelen paket
class PolicySettingsRequest(BaseModel):
    daily_limit_minutes: int
    bedtime_start: str      # "21:30" formatında gelir
    bedtime_end: str        # "07:00" formatında gelir
    weekend_relax_pct: int  

# Backend'den dönen cevap (Mobil bunu bekliyor)
class Bedtime(BaseModel):
    start: str
    end: str

class PolicyResponse(BaseModel):
    user_id: UUID
    daily_limit_minutes: int
    blocked_apps: List[str] = []
    bedtime: Optional[Bedtime] = None
    weekend_extra_minutes: int = 0  

class BlockAppRequest(BaseModel):
    package_name: str