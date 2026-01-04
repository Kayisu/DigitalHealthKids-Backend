from datetime import datetime, timedelta, timezone, time, date
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks 
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from app.db import get_db, SessionLocal
from app.models.core import DailyUsageLog, AppSession, User, UserSettings
from app.schemas.usage import (
    UsageReportRequest,
    UsageReportResponse,
    DashboardResponse,
    DailyStat,
    AppUsageItem,
    AppDetailResponse,
    HourlyUsage,
    SessionUsage,
)
from app.services.analytics import calculate_daily_features 
from app.services.categorizer import get_or_create_app_entry
from app.services.category_constants import display_label_for, DEFAULT_CATEGORY_KEY
from app.models.core import AppCatalog, AppCategory 
import time as perf_time

router = APIRouter()

# Türkiye için UTC+3 saat dilimini tanımla
TR_TZ = timezone(timedelta(hours=3))
def _calculate_features_background(user_id: UUID, target_date: date):
    """Run feature calculation with a fresh DB session to avoid closed session errors."""
    db = SessionLocal()
    try:
        calculate_daily_features(user_id, target_date, db)
    finally:
        db.close()



def _interval_overlap_minutes(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> float:
    if a_end <= b_start or a_start >= b_end:
        return 0.0
    overlap_start = max(a_start, b_start)
    overlap_end = min(a_end, b_end)
    return max((overlap_end - overlap_start).total_seconds(), 0) / 60.0


def _night_overlap_minutes(start_dt: datetime, end_dt: datetime, win_start_t: time, win_end_t: time) -> float:
    minutes = 0.0
    cursor = start_dt
    while cursor < end_dt:
        day_end = datetime.combine(cursor.date(), time.max, tzinfo=cursor.tzinfo)
        seg_end = min(day_end, end_dt)

        if win_start_t > win_end_t:
            win1_start = datetime.combine(cursor.date(), win_start_t, tzinfo=cursor.tzinfo)
            win1_end = datetime.combine(cursor.date(), time.max, tzinfo=cursor.tzinfo)
            win2_start = datetime.combine(cursor.date(), time.min, tzinfo=cursor.tzinfo)
            win2_end = datetime.combine(cursor.date(), win_end_t, tzinfo=cursor.tzinfo)
            minutes += _interval_overlap_minutes(cursor, seg_end, win1_start, win1_end)
            minutes += _interval_overlap_minutes(cursor, seg_end, win2_start, win2_end)
        else:
            win_start = datetime.combine(cursor.date(), win_start_t, tzinfo=cursor.tzinfo)
            win_end = datetime.combine(cursor.date(), win_end_t, tzinfo=cursor.tzinfo)
            minutes += _interval_overlap_minutes(cursor, seg_end, win_start, win_end)

        cursor = seg_end + timedelta(seconds=1)
    return minutes

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
        stmt_sess = insert(AppSession).values(session_rows)
        stmt_sess = stmt_sess.on_conflict_do_nothing(
            index_elements=[
                AppSession.user_id,
                AppSession.device_id,
                AppSession.package_name,
                AppSession.started_at,
            ]
        )
        db.execute(stmt_sess)
        print(
            f"USAGE REPORT step=insert_sessions rows={len(session_rows)} elapsed_ms={(perf_time.perf_counter()-t0)*1000:.1f}"
        )

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
    
    # Arka plan görevleri (taze session ile çalıştır)
    for d in dates_in_payload:
        background_tasks.add_task(_calculate_features_background, user_id, d)
    print("USAGE REPORT step=scheduled_background")

    return UsageReportResponse(status="ok", inserted=len(payload.events))


@router.get("/app_detail", response_model=AppDetailResponse)
def get_app_detail(
    user_id: UUID,
    package_name: str,
    target_date: date,
    db: Session = Depends(get_db)
):
    day_start = datetime.combine(target_date, time.min, tzinfo=TR_TZ)
    day_end = datetime.combine(target_date, time.max, tzinfo=TR_TZ)

    sessions = (
        db.query(AppSession)
        .filter(AppSession.user_id == user_id)
        .filter(AppSession.package_name == package_name)
        .filter(AppSession.started_at <= day_end)
        .filter(AppSession.ended_at >= day_start)
        .order_by(AppSession.started_at)
        .all()
    )

    hourly = [0.0] * 24
    total_minutes = 0.0
    night_minutes = 0.0
    session_items = []

    bedtime_start = time(22, 0)
    bedtime_end = time(7, 0)
    custom = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if custom and custom.nightly_start:
        bedtime_start = custom.nightly_start
    if custom and custom.nightly_end:
        bedtime_end = custom.nightly_end

    for sess in sessions:
        s = max(sess.started_at, day_start)
        e = min(sess.ended_at, day_end)
        if e <= s:
            continue

        duration_min = (e - s).total_seconds() / 60.0
        total_minutes += duration_min
        night_minutes += _night_overlap_minutes(s, e, bedtime_start, bedtime_end)

        # Hourly bucket slicing
        cursor = s
        while cursor < e:
            hour_boundary = (cursor.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
            seg_end = min(hour_boundary, e)
            seg_min = max((seg_end - cursor).total_seconds(), 0) / 60.0
            hourly[cursor.hour] += seg_min
            cursor = seg_end

        session_items.append(
            SessionUsage(
                started_at=s,
                ended_at=e,
                minutes=int(round(duration_min))
            )
        )

    # App adı: katalogdan ya da session payload'dan
    catalog = db.query(AppCatalog).filter(AppCatalog.package_name == package_name).first()

    # Uygulama adı: katalog öncelikli, yoksa günlük log'a bak, son çare session payload
    app_name = None
    if catalog:
        app_name = catalog.app_name
    if not app_name:
        daily_log = (
            db.query(DailyUsageLog)
            .filter(DailyUsageLog.user_id == user_id)
            .filter(DailyUsageLog.package_name == package_name)
            .filter(DailyUsageLog.usage_date == target_date)
            .order_by(DailyUsageLog.updated_at.desc())
            .first()
        )
        if daily_log and daily_log.app_name:
            app_name = daily_log.app_name
    if not app_name and sessions:
        app_name = getattr(sessions[0], "app_name", None)

    # Kategori: ilişki varsa direkt, yoksa ID'den çek; katalog yoksa günlük log kategorisini kullanma
    category_name = None
    if catalog and catalog.category:
        category_name = catalog.category.display_name
    elif catalog and catalog.category_id:
        cat = db.query(AppCategory).filter(AppCategory.id == catalog.category_id).first()
        if cat:
            category_name = cat.display_name

    if not category_name:
        category_name = display_label_for(DEFAULT_CATEGORY_KEY)

    return AppDetailResponse(
        date=target_date.isoformat(),
        package_name=package_name,
        app_name=app_name,
        category=category_name,
        total_minutes=int(round(total_minutes)),
        night_minutes=int(round(night_minutes)),
        hourly=[HourlyUsage(hour=i, minutes=int(round(m))) for i, m in enumerate(hourly)],
        sessions=session_items,
    )



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
    # Sözlük yap: { "com.instagram": "Sosyal", ... }
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
            
            # Kategoriyi haritadan bul, yoksa varsayılan kategori (Araçlar) de.
            cat_name = category_map.get(row.package_name, display_label_for(DEFAULT_CATEGORY_KEY))

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