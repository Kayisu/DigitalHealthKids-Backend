# app/routers/usage.py
from collections import defaultdict
from datetime import datetime, timedelta, timezone, date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.core import AppSession, User
from app.schemas.usage import (
    DailyStat,
    UsageReportRequest,
    UsageReportResponse,
    DashboardResponse,
    AppUsageItem,
)

router = APIRouter()

# Sabit TR Timezone (MVP için)
TR_TZ = timezone(timedelta(hours=3))

@router.post("/report", response_model=UsageReportResponse)
def report_usage(payload: UsageReportRequest, db: Session = Depends(get_db)):
    inserted = 0
    ignored = 0

    for ev in payload.events:
        # Gelen veriyi timezone aware yap
        start_dt = ev.start_time
        end_dt = ev.end_time
        
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=TR_TZ)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=TR_TZ)

        session = AppSession(
            user_id=payload.user_id,
            device_id=payload.device_id,
            package_name=ev.app_package,
            started_at=start_dt,
            ended_at=end_dt,
            source="user_device",
            payload={
                "app_name": ev.app_name,
                "total_seconds": ev.total_seconds,
            },
        )
        try:
            db.add(session)
            db.commit() 
            inserted += 1
        except IntegrityError:
            db.rollback() 
            ignored += 1
        except Exception as e:
            db.rollback()
            print(f"Error inserting: {e}")

    return UsageReportResponse(status="ok", inserted=inserted)


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(user_id: UUID, db: Session = Depends(get_db)) -> DashboardResponse:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Şu anki TR saati
    now_tr = datetime.now(TR_TZ)
    today = now_tr.date()

    # Son 7 günü kapsayacak şekilde (Bugün + 6 gün geri)
    # Eksik gün görünmemesi için 7 gün geriye gidiyoruz.
    start_date = today - timedelta(days=6)
    
    # DB sorgusu için başlangıç zamanı (Günün 00:00:00'ı)
    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=TR_TZ)

    sessions = (
        db.query(AppSession)
        .filter(AppSession.user_id == user_id)
        .filter(AppSession.started_at >= start_dt)
        .all()
    )

    # daily_map: { date: { 'total': 0, 'apps': { 'pkg': minutes }, 'names': {} } }
    daily_map = {}
    
    # 7 Günlük şablonu oluştur (Eskiden yeniye)
    for i in range(7):
        d = start_date + timedelta(days=i)
        daily_map[d] = {'total': 0, 'apps': defaultdict(int), 'names': {}}

    for s in sessions:
        if not s.started_at: continue
        
        # Session tarihini TR saatine göre al
        s_date = s.started_at.astimezone(TR_TZ).date()

        # Eğer hesaplanan tarih aralığımızın dışındaysa (örn: çok eski veya gelecek) atla
        if s_date not in daily_map:
            continue

        # Süre hesapla
        mins = 0
        if isinstance(s.payload, dict) and "total_seconds" in s.payload:
            mins = int(s.payload["total_seconds"]) // 60
        elif s.ended_at:
            mins = int((s.ended_at - s.started_at).total_seconds()) // 60
            
        if mins <= 0: continue

        daily_map[s_date]['total'] += mins
        pkg = s.package_name or "unknown"
        daily_map[s_date]['apps'][pkg] += mins
        
        # İsim belirle
        potential_name = None
        if isinstance(s.payload, dict):
            potential_name = s.payload.get("app_name")
        
        final_app_name = potential_name if potential_name else pkg
        daily_map[s_date]['names'][pkg] = final_app_name

    # Response oluştur
    weekly_breakdown = []
    
    # daily_map anahtarlarını sıralı dönüyoruz
    sorted_dates = sorted(daily_map.keys())
    
    for d in sorted_dates:
        data = daily_map[d]
        
        sorted_apps = sorted(data['apps'].items(), key=lambda x: x[1], reverse=True)
        
        app_items = [
            AppUsageItem(
                package_name=pkg,
                app_name=data['names'].get(pkg) or pkg, 
                minutes=m
            ) for pkg, m in sorted_apps
        ]

        weekly_breakdown.append(DailyStat(
            date=d,
            total_minutes=data['total'],
            apps=app_items
        ))

    # Bugünün verisi (Listenin sonuncusu bugündür)
    today_stat_total = daily_map.get(today, {}).get('total', 0)
    
    return DashboardResponse(
        user_name=user.full_name or "Kullanıcı",
        today_total_minutes=today_stat_total,
        weekly_breakdown=weekly_breakdown,
        bedtime_start="21:30",
        bedtime_end="07:00"
    )