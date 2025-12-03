# app/routers/usage.py

from collections import defaultdict
from datetime import datetime, timedelta, timezone, date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
# 🔥 ÖNEMLİ: PostgreSQL'e özel 'INSERT ON CONFLICT' (Upsert) yapısı
from sqlalchemy.dialects.postgresql import insert 

from app.db import get_db
from app.models.core import AppSession, User, DailyAppUsageView
from app.schemas.usage import (
    DailyStat,
    UsageReportRequest,
    UsageReportResponse,
    DashboardResponse,
    AppUsageItem,
)

router = APIRouter()

# Sabit TR Timezone
TR_TZ = timezone(timedelta(hours=3))

@router.post("/report", response_model=UsageReportResponse)
def report_usage(payload: UsageReportRequest, db: Session = Depends(get_db)):
    processed_count = 0
    
    for ev in payload.events:
        raw_start = ev.start_time
        if raw_start.tzinfo is None:
            raw_start = raw_start.replace(tzinfo=TR_TZ)
            
        normalized_start = raw_start.replace(hour=0, minute=0, second=0, microsecond=0)
        
        normalized_end = normalized_start + timedelta(days=1) - timedelta(microseconds=1)

        stmt = insert(AppSession).values(
            user_id=payload.user_id,
            device_id=payload.device_id,
            package_name=ev.app_package,
            started_at=normalized_start, 
            ended_at=normalized_end,
            source="user_device_daily_aggregate", 
            payload={
                "app_name": ev.app_name,
                "total_seconds": ev.total_seconds,
            },
        )
        do_update_stmt = stmt.on_conflict_do_update(
            constraint='unique_session_entry', 
            set_={
                'ended_at': stmt.excluded.ended_at,
                'payload': stmt.excluded.payload,
                'occurred_at': datetime.utcnow()
            }
        )

        try:
            db.execute(do_update_stmt)
            processed_count += 1
        except Exception as e:
            print(f"Row error: {e}")
            continue

    try:
        db.commit()
        return UsageReportResponse(status="ok", inserted=processed_count)
    except Exception as e:
        db.rollback()
        print(f"Commit error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(user_id: UUID, db: Session = Depends(get_db)) -> DashboardResponse:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now_tr = datetime.now(TR_TZ)
    today = now_tr.date()
    start_date = today - timedelta(days=6)

    stats = (
        db.query(DailyAppUsageView)
        .filter(DailyAppUsageView.user_id == user_id)
        .filter(DailyAppUsageView.usage_date >= start_date)
        .all()
    )

    daily_map = {}
    for i in range(7):
        d = start_date + timedelta(days=i)
        daily_map[d] = {'total': 0, 'apps': []}

    for row in stats:
        d = row.usage_date
        if d in daily_map:
            daily_map[d]['total'] += row.total_minutes
            daily_map[d]['apps'].append(
                AppUsageItem(
                    package_name=row.package_name,
                    app_name=row.package_name, 
                    minutes=row.total_minutes
                )
            )

    weekly_breakdown = []
    sorted_dates = sorted(daily_map.keys())

    for d in sorted_dates:
        data = daily_map[d]
        sorted_apps = sorted(data['apps'], key=lambda x: x.minutes, reverse=True)
        
        weekly_breakdown.append(DailyStat(
            date=d,
            total_minutes=data['total'],
            apps=sorted_apps
        ))

    today_stat_total = daily_map.get(today, {}).get('total', 0)
    
    return DashboardResponse(
        user_name=user.full_name or "Kullanıcı",
        today_total_minutes=today_stat_total,
        weekly_breakdown=weekly_breakdown,
        bedtime_start="21:30",
        bedtime_end="07:00"
    )