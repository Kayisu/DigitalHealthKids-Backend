# app/routers/usage.py
from datetime import datetime, timedelta, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.db import get_db
from app.models.core import DailyUsageLog, User
from app.schemas.usage import UsageReportRequest, UsageReportResponse, DashboardResponse, DailyStat, AppUsageItem

router = APIRouter()
TR_TZ = timezone(timedelta(hours=3))

@router.post("/report", response_model=UsageReportResponse)
def report_usage(payload: UsageReportRequest, db: Session = Depends(get_db)):
    processed_count = 0
    
    for ev in payload.events:
        # 🔥 ARTIK HESAP YOK. Android ne derse o.
        # ev.date_str -> "2025-12-03" geliyor.
        try:
            # String'i date objesine çeviriyoruz sadece DB için
            usage_date = datetime.strptime(ev.date_str, "%Y-%m-%d").date()
        except ValueError:
            continue # Format bozuksa atla

        stmt = insert(DailyUsageLog).values(
            user_id=payload.user_id,
            device_id=payload.device_id,
            usage_date=usage_date,
            package_name=ev.app_package,
            app_name=ev.app_name,
            total_seconds=ev.total_seconds,
            updated_at=datetime.utcnow()
        )
        
        do_update_stmt = stmt.on_conflict_do_update(
            constraint='pk_daily_usage',
            set_={
                'total_seconds': stmt.excluded.total_seconds,
                'app_name': stmt.excluded.app_name,
                'updated_at': datetime.utcnow()
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
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(user_id: UUID, db: Session = Depends(get_db)):
    # ... Dashboard mantığı aynı kalabilir, sadece veri çekme ...
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.now(TR_TZ)
    today = now.date()
    start_date = today - timedelta(days=6)

    logs = (
        db.query(DailyUsageLog)
        .filter(DailyUsageLog.user_id == user_id)
        .filter(DailyUsageLog.usage_date >= start_date)
        .all()
    )

    daily_map = {}
    for i in range(7):
        d = start_date + timedelta(days=i)
        daily_map[d] = {'total': 0, 'apps': []}

    for row in logs:
        d = row.usage_date
        minutes = row.total_seconds // 60
        
        # Eğer map'te varsa (tarih aralığındaysa) ekle
        if d in daily_map:
            daily_map[d]['total'] += minutes
            # 🔥 AYNI PAKET VAR MI KONTROLÜ (UI Duplicates Çözümü)
            # Backend tarafında da birleştirme yapalım ne olur ne olmaz.
            existing_app = next((x for x in daily_map[d]['apps'] if x.package_name == row.package_name), None)
            if existing_app:
                existing_app.minutes += minutes
            else:
                daily_map[d]['apps'].append(
                    AppUsageItem(
                        package_name=row.package_name,
                        app_name=row.app_name or row.package_name,
                        minutes=minutes
                    )
                )

    weekly_breakdown = []
    sorted_dates = sorted(daily_map.keys())

    for d in sorted_dates:
        data = daily_map[d]
        sorted_apps = sorted(data['apps'], key=lambda x: x.minutes, reverse=True)
        weekly_breakdown.append(DailyStat(
            date=d.isoformat(), # String olarak dön
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