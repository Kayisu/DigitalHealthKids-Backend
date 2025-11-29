# app/schemas/usage.py
from datetime import datetime
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
    category: Optional[str] = None
    minutes: int


class DashboardResponse(BaseModel):
    child_name: str
    today_total_minutes: int
    today_remaining_minutes: int
    weekly_trend: List[int]
    top_apps: List[AppUsageItem]
    bedtime_start: Optional[str] = None
    bedtime_end: Optional[str] = None
