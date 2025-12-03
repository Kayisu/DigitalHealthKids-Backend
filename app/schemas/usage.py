# app/schemas/usage.py
from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field

class UsageEvent(BaseModel):
    app_package: str
    app_name: Optional[str] = None
    date_str: str # 🔥 DEĞİŞTİ: Artık "YYYY-MM-DD" formatında string bekliyoruz.
    total_seconds: int = Field(ge=0)
    # start_time ve end_time'ı sildik, kafa karıştırıyorlardı.

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

class DailyStat(BaseModel):
    date: str # date objesi yerine str dönebiliriz, frontend parsing yapıyor zaten
    total_minutes: int
    apps: List[AppUsageItem]

class DashboardResponse(BaseModel):
    user_name: str
    today_total_minutes: int
    weekly_breakdown: List[DailyStat]
    bedtime_start: Optional[str] = None
    bedtime_end: Optional[str] = None