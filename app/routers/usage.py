# app/routers/usage.py
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.core import AppSession, User
from app.schemas.usage import (
    UsageReportRequest,
    UsageReportResponse,
    DashboardResponse,
    AppUsageItem,
)

router = APIRouter()


@router.post("/report", response_model=UsageReportResponse)
def report_usage(payload: UsageReportRequest, db: Session = Depends(get_db)):
    inserted = 0

    for ev in payload.events:
        try:
            start_dt = datetime.fromisoformat(ev.start_time.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(ev.end_time.replace("Z", "+00:00"))
        except Exception:
            # Çöpe at, çok da kasmayalım şimdilik
            continue

        session = AppSession(
            child_id=payload.child_id,
            device_id=payload.device_id,
            package_name=ev.app_package,
            started_at=start_dt,
            ended_at=end_dt,
            source="child_device",
            payload={
                "app_name": ev.app_name,
                "total_seconds": ev.total_seconds,
            },
        )
        db.add(session)
        inserted += 1

    db.commit()

    return UsageReportResponse(status="ok", inserted=inserted)

@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(child_id: UUID, db: Session = Depends(get_db)) -> DashboardResponse:
    """
    Belirli bir child_id için SON 7 GÜNÜ gerçek app_session verisinden
    özetleyip dashboard döner.
    """
    # 1) Çocuğu doğrula
    child = db.query(User).filter(User.id == child_id).first()
    if child is None:
        raise HTTPException(status_code=404, detail="Child not found")

    # 2) Tarih aralığı: son 7 gün (bugün dahil)
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=6)
    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)

    sessions = (
        db.query(AppSession)
        .filter(AppSession.child_id == child_id)
        .filter(AppSession.started_at >= start_dt)
        .all()
    )

    # 3) Günlük dakika ve uygulama bazlı dakika bucket'ları
    day_minutes = defaultdict(int)   # date -> minutes
    app_minutes = defaultdict(int)   # package -> minutes
    app_names = {}                   # package -> app_name

    for s in sessions:
        # total_seconds öncelikli, yoksa ended_at - started_at
        if isinstance(s.payload, dict) and "total_seconds" in s.payload:
            total_sec = int(s.payload.get("total_seconds") or 0)
        elif s.ended_at:
            total_sec = int((s.ended_at - s.started_at).total_seconds())
        else:
            continue

        mins = total_sec // 60
        day = s.started_at.date()
        day_minutes[day] += mins

        pkg = s.package_name or "unknown"
        app_minutes[pkg] += mins
        name = None
        if isinstance(s.payload, dict):
            name = s.payload.get("app_name")
        app_names[pkg] = name or pkg

    # 4) Weekly trend: start_date..today arası 7 günlük liste
    weekly_trend: list[int] = []
    for i in range(7):
        d = start_date + timedelta(days=i)
        weekly_trend.append(day_minutes.get(d, 0))

    today_total = day_minutes.get(today, 0)

    # Şimdilik sabit limit: 240 dk (4 saat)
    allowed_daily_minutes = 240
    today_remaining = max(allowed_daily_minutes - today_total, 0)

    # 5) En çok kullanılan ilk 5 uygulama
    top = sorted(app_minutes.items(), key=lambda x: x[1], reverse=True)[:5]
    top_items = [
        AppUsageItem(
            app_name=app_names.get(pkg, pkg),
            package_name=pkg,
            category=None,
            minutes=mins,
        )
        for pkg, mins in top
    ]

    # 6) Bedtime şimdilik yok (child_settings'e sonra bağlarız)
    bedtime_start = None
    bedtime_end = None

    return DashboardResponse(
        child_name=child.full_name or "Çocuk",
        today_total_minutes=today_total,
        today_remaining_minutes=today_remaining,
        weekly_trend=weekly_trend,
        top_apps=top_items,
        bedtime_start=bedtime_start,
        bedtime_end=bedtime_end,
    )
