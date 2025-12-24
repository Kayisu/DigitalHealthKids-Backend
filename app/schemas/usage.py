# app/schemas/usage.py
from datetime import datetime
from typing import List, Optional
from datetime import date
from uuid import UUID
from pydantic import BaseModel, Field

class UsageEvent(BaseModel):
    package_name: str
    app_name: Optional[str] = None
    timestamp_start: int
    timestamp_end: int
    duration_seconds: int = Field(ge=0)


class UsageReportRequest(BaseModel):
    user_id: UUID
    device_id: UUID
    events: List[UsageEvent]

class UsageReportResponse(BaseModel):
    status: str
    inserted: int

# Diğer sınıflar aynı kalabilir...
class AppUsageItem(BaseModel):
    app_name: str
    package_name: str
    minutes: int
    category: Optional[str] = None

class DailyStat(BaseModel):
    date: str # date objesi yerine str dönebiliriz, frontend parsing yapıyor zaten
    total_minutes: int
    category: Optional[str] = None
    apps: List[AppUsageItem] = []
    
    class Config:
        orm_mode = True 

class DashboardResponse(BaseModel):
    user_name: str
    today_total_minutes: int
    weekly_breakdown: List[DailyStat]
    bedtime_start: Optional[str] = None
    bedtime_end: Optional[str] = None


# App detail / hourly usage
class HourlyUsage(BaseModel):
    hour: int
    minutes: int


class SessionUsage(BaseModel):
    started_at: datetime
    ended_at: datetime
    minutes: int


class AppDetailResponse(BaseModel):
    date: str
    package_name: str
    app_name: Optional[str] = None
    category: Optional[str] = None
    total_minutes: int
    night_minutes: int
    hourly: List[HourlyUsage]
    sessions: List[SessionUsage] = []