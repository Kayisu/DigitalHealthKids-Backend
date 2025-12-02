# app/schemas/usage.py
from datetime import datetime, date
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class UsageEvent(BaseModel):
    app_package: str
    app_name: Optional[str] = None
    start_time: datetime
    end_time: datetime
    total_seconds: int = Field(ge=0)


class UsageReportRequest(BaseModel):
    child_id: UUID
    device_id: UUID
    events: List[UsageEvent]


class UsageReportResponse(BaseModel):
    status: str
    inserted: int


class AppUsageItem(BaseModel):
    app_name: str
    package_name: str
    minutes: int

# 🔥 YENİ: Her günün kendi detaylı raporu var
class DailyStat(BaseModel):
    date: date          # 2025-11-29
    total_minutes: int
    apps: List[AppUsageItem] # O gün kullanılanlar

class DashboardResponse(BaseModel):
    child_name: str
    today_total_minutes: int
    weekly_breakdown: List[DailyStat] # 🔥 Artık trend yerine bu var
    bedtime_start: Optional[str] = None
    bedtime_end: Optional[str] = None
