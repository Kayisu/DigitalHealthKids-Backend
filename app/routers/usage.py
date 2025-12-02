# app/routers/usage.py
from collections import defaultdict
from datetime import datetime, timedelta, timezone 
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from psycopg import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError 

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


@router.post("/report", response_model=UsageReportResponse)
def report_usage(payload: UsageReportRequest, db: Session = Depends(get_db)):
    inserted = 0
    ignored = 0

    for ev in payload.events:
        
        start_dt = ev.start_time
        end_dt = ev.end_time
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc+timedelta(hours=3))
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc+timedelta(hours=3))

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
        try:
            db.add(session)
            db.commit() # Her satırı tek tek dene (Toplu insertte biri patlarsa hepsi patlar)
            inserted += 1
        except IntegrityError:
            db.rollback() # Bu kayıt zaten var, devam et
            ignored += 1
        except Exception as e:
            db.rollback()
            print(f"Error inserting: {e}")

    return UsageReportResponse(status="ok", inserted=inserted) # İstersen ignored sayısını da dön

@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(child_id: UUID, db: Session = Depends(get_db)) -> DashboardResponse:
    child = db.query(User).filter(User.id == child_id).first()
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")

    today = datetime.now(timezone.utc).date()
    # Son 7 gün (6 gün önce + bugün)
    start_date = today - timedelta(days=6)
    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)

    # Veritabanından bu aralıktaki tüm sessionları çek
    sessions = (
        db.query(AppSession)
        .filter(AppSession.child_id == child_id)
        .filter(AppSession.started_at >= start_dt)
        .all()
    )

    # Veriyi günlere göre grupla
    # daily_map: { date: { 'total': 0, 'apps': { 'pkg': minutes } } }
    daily_map = {}
    
    # Boş şablonu oluştur (Veri olmayan günler 0 görünsün)
    for i in range(7):
        d = start_date + timedelta(days=i)
        daily_map[d] = {'total': 0, 'apps': defaultdict(int), 'names': {}}

    for s in sessions:
        if not s.started_at: continue
        
        # Süre hesapla
        mins = 0
        if isinstance(s.payload, dict) and "total_seconds" in s.payload:
            mins = int(s.payload["total_seconds"]) // 60
        elif s.ended_at:
            mins = int((s.ended_at - s.started_at).total_seconds()) // 60
            
        if mins <= 0: continue

        d_key = s.started_at.date()
        if d_key in daily_map:
            daily_map[d_key]['total'] += mins
            pkg = s.package_name or "unknown"
            daily_map[d_key]['apps'][pkg] += mins
            
            # Uygulama adını kaydet
            potential_name = None
            if isinstance(s.payload, dict):
                potential_name = s.payload.get("app_name")
            
            # Eğer payload'dan gelen isim doluysa onu kullan, yoksa paket adını kullan
            final_app_name = potential_name if potential_name else pkg
            
            daily_map[d_key]['names'][pkg] = final_app_name

    # Response objesini oluştur
    weekly_breakdown = []
    # Tarih sırasına göre listeye çevir
    for i in range(7):
        d = start_date + timedelta(days=i)
        data = daily_map[d]
        
        # O günün en çok kullanılanlarını sırala
        sorted_apps = sorted(data['apps'].items(), key=lambda x: x[1], reverse=True)
        
        app_items = [
            AppUsageItem(
                package_name=pkg,
                # "or pkg" ekleyerek None gelirse paket ismini basmasını sağlıyoruz
                app_name=data['names'].get(pkg) or pkg, 
                minutes=m
            ) for pkg, m in sorted_apps
        ]

        weekly_breakdown.append(DailyStat(
            date=d,
            total_minutes=data['total'],
            apps=app_items
        ))

    today_stat = daily_map[today]
    
    return DashboardResponse(
        child_name=child.full_name or "Çocuk",
        today_total_minutes=today_stat['total'],
        weekly_breakdown=weekly_breakdown,
        bedtime_start="21:30",
        bedtime_end="07:00"
    )
