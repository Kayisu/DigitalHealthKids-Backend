# app/schemas/policy.py
from pydantic import BaseModel
from uuid import UUID
from typing import List, Optional

class PolicySettingsRequest(BaseModel):
    # Ebeveyn ayarı silmek isterse null gönderebilsin diye buraları da opsiyonel yapabiliriz
    daily_limit_minutes: Optional[int] = None
    bedtime_start: Optional[str] = None
    bedtime_end: Optional[str] = None
    weekend_relax_pct: int = 0
    
class Bedtime(BaseModel):
    start: str
    end: str

class PolicyResponse(BaseModel):
    user_id: UUID
    daily_limit_minutes: Optional[int] = None 
    blocked_apps: List[str] = []
    bedtime: Optional[Bedtime] = None
    weekend_extra_minutes: int = 0
    
# ... (BlockAppRequest aynı kalabilir)
class BlockAppRequest(BaseModel):
    package_name: str
    
class ToggleBlockRequest(BaseModel):
    user_id: UUID
    package_name: str    