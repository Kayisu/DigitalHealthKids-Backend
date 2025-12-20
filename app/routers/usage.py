from datetime import datetime, timedelta, timezone, time
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks 
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from app.db import get_db
from app.models.core import DailyUsageLog, AppSession, User
from app.schemas.usage import UsageReportRequest, UsageReportResponse, DashboardResponse, DailyStat, AppUsageItem
from app.services.analytics import calculate_daily_features 
from app.services.categorizer import get_or_create_app_entry
from app.models.core import AppCatalog, AppCategory 
import time as perf_time

router = APIRouter()

# Türkiye için UTC+3 saat dilimini tanımla
TR_TZ = timezone(timedelta(hours=3))

@router.post("/report", response_model=UsageReportResponse)
def report_usage(
    payload: UsageReportRequest, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)):

    t0 = perf_time.perf_counter()
    print("USAGE REPORT step=start_handler")

    if not payload.events:
        return UsageReportResponse(status="ok", inserted=0)

    try:
        min_ts = min(e.timestamp_start for e in payload.events)
        max_ts = max(e.timestamp_end for e in payload.events)
        span_hours = (max_ts - min_ts) / 1000 / 3600
        print(
            f"USAGE REPORT start count={len(payload.events)} user={payload.user_id} "
            f"device={payload.device_id} span_hours={span_hours:.2f} "
            f"min={datetime.fromtimestamp(min_ts/1000, TR_TZ)} "
            f"max={datetime.fromtimestamp(max_ts/1000, TR_TZ)}"
        )
    except Exception as e:
        print(f"USAGE REPORT log calculation failed: {e}")

    user_id = payload.user_id
    device_id = payload.device_id

    def _split_session(start_dt: datetime, end_dt: datetime):
        current_start = start_dt
        # Stop when we pass the real end time to avoid infinite loop on same-day sessions
        while current_start <= end_dt:
            day_end = datetime.combine(current_start.date(), time.max, tzinfo=TR_TZ)
            segment_end = min(day_end, end_dt)
            duration = (segment_end - current_start).total_seconds()
            if duration > 0:
                yield current_start.date(), duration
            current_start = segment_end + timedelta(seconds=1)

    aggregated = {}
    dates_in_payload = set()
    session_rows = []

    for ev in payload.events:
        start_dt = datetime.fromtimestamp(ev.timestamp_start / 1000.0, TR_TZ)
        end_dt = datetime.fromtimestamp(ev.timestamp_end / 1000.0, TR_TZ)

        if end_dt <= start_dt:
            continue

        # Insert raw session
        session_rows.append({
            "user_id": user_id,
            "device_id": device_id,
            "package_name": ev.package_name,
            "started_at": start_dt,
            "ended_at": end_dt,
            "source": "android_sync",
            "payload": None,
        })

        for usage_date, duration in _split_session(start_dt, end_dt):
            dates_in_payload.add(usage_date)
            key = (usage_date, ev.package_name)
            if key not in aggregated:
                aggregated[key] = {"duration": 0, "app_name": ev.app_name}
            aggregated[key]["duration"] += duration
            if ev.app_name:
                aggregated[key]["app_name"] = ev.app_name

    print(
        f"USAGE REPORT step=after_aggregate agg={len(aggregated)} dates={len(dates_in_payload)} "
        f"elapsed_ms={(perf_time.perf_counter()-t0)*1000:.1f}"
    )

    unique_packages = {pkg for (_, pkg) in aggregated.keys()}
    print(f"USAGE REPORT step=unique_packages count={len(unique_packages)}")
    for pkg in unique_packages:
        get_or_create_app_entry(db, pkg)
    print(
        f"USAGE REPORT step=after_catalog elapsed_ms={(perf_time.perf_counter()-t0)*1000:.1f}"
    )

    rows = []
    for (usage_date, pkg), data in aggregated.items():
        total_seconds = int(data["duration"])
        if total_seconds > 16 * 3600:
            msg = f"implausible daily total pkg={pkg} date={usage_date} total_seconds={total_seconds}"
            print(f"USAGE REPORT error={msg}")
            raise HTTPException(status_code=422, detail=msg)

        rows.append({
            "user_id": user_id,
            "device_id": device_id,
            "usage_date": usage_date,
            "package_name": pkg,
            "app_name": data["app_name"],
            "total_seconds": total_seconds,
            "updated_at": datetime.utcnow()
        })

    # Insert raw sessions (if any)
    if session_rows:
        db.execute(insert(AppSession), session_rows)
        print(f"USAGE REPORT step=insert_sessions rows={len(session_rows)} elapsed_ms={(perf_time.perf_counter()-t0)*1000:.1f}")

    if rows:
        stmt = insert(DailyUsageLog).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                DailyUsageLog.user_id,
                DailyUsageLog.device_id,
                DailyUsageLog.usage_date,
                DailyUsageLog.package_name
            ],
            set_={
                "app_name": stmt.excluded.app_name,
                "total_seconds": stmt.excluded.total_seconds,
                "updated_at": datetime.utcnow()
            }
        )
        db.execute(stmt)
    print(
        f"USAGE REPORT step=after_upsert rows={len(rows)} elapsed_ms={(perf_time.perf_counter()-t0)*1000:.1f}"
    )

    try:
        db.commit()
        print(
            f"USAGE REPORT step=after_commit elapsed_ms={(perf_time.perf_counter()-t0)*1000:.1f}"
        )
    except Exception as e:
        db.rollback()
        print(f"DATABASE COMMIT ERROR: {e}") 
        raise HTTPException(status_code=500, detail=f"Database commit failed: {e}")
    
    # Arka plan görevleri
    for d in dates_in_payload:
        background_tasks.add_task(calculate_daily_features, user_id, d, db)
    print("USAGE REPORT step=scheduled_background")

    return UsageReportResponse(status="ok", inserted=len(payload.events))



@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(user_id: UUID, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.now(TR_TZ)
    today = now.date()
    start_date = today - timedelta(days=6)

    # 1. Katalog Bilgilerini Çek (Paket -> Kategori İsmi eşleşmesi için)
    # Performans için hepsini memory'e alıyoruz (50k satırsa cache mekanizması gerekir ama şimdilik OK)
    catalog_query = (
        db.query(AppCatalog.package_name, AppCategory.display_name)
        .join(AppCategory, AppCatalog.category_id == AppCategory.id)
        .all()
    )
    # Sözlük yap: { "com.instagram": "Sosyal Medya", ... }
    category_map = {row.package_name: row.display_name for row in catalog_query}

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
        
        if d in daily_map:
            daily_map[d]['total'] += minutes
            
            existing_app = next((x for x in daily_map[d]['apps'] if x.package_name == row.package_name), None)
            
            # Kategoriyi haritadan bul, yoksa 'Diğer' de.
            cat_name = category_map.get(row.package_name, "Diğer")

            if existing_app:
                existing_app.minutes += minutes
            else:
                daily_map[d]['apps'].append(
                    AppUsageItem(
                        package_name=row.package_name,
                        app_name=row.app_name or row.package_name,
                        minutes=minutes,
                        category=cat_name # ARTIK KATEGORİ GİDİYOR
                    )
                )

    weekly_breakdown = []
    sorted_dates = sorted(daily_map.keys())

    for d in sorted_dates:
        data = daily_map[d]
        sorted_apps = sorted(data['apps'], key=lambda x: x.minutes, reverse=True)
        weekly_breakdown.append(DailyStat(
            date=d.isoformat(),
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