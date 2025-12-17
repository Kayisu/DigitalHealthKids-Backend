from datetime import datetime, timedelta, timezone
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

router = APIRouter()
TR_TZ = timezone(timedelta(hours=3))

@router.post("/report", response_model=UsageReportResponse)
def report_usage(
    payload: UsageReportRequest, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)):
    
    
    
    # Veritabanında olmayan uygulama paketlerini bir kerede topluca ekle
    unique_packages = {ev.package_name for ev in payload.events}
    for pkg in unique_packages:
        get_or_create_app_entry(db, pkg)

    # Her bir günlük kullanım özetini veritabanına işle
    for ev in payload.events:
        # Gelen timestamp'e göre doğru tarihi hesapla
        # Not: Backend'in zaman dilimi ayarına göre start_dt kullanmak daha güvenilir.
        start_dt = datetime.fromtimestamp(ev.timestamp_start / 1000.0)
        usage_date = start_dt.date()

        # DailyUsageLog için UPSERT (insert or update) ifadesini hazırla
        stmt = insert(DailyUsageLog).values(
            user_id=payload.user_id,
            device_id=payload.device_id,
            usage_date=usage_date,
            package_name=ev.package_name,
            app_name=ev.app_name, 
            total_seconds=ev.duration_seconds, 
            updated_at=datetime.utcnow()
        )
        
        # Eğer aynı gün, aynı kullanıcı, aynı cihaz ve aynı paket için kayıt varsa,
        # total_seconds'ı üzerine ekle.
            # Lütfen bu kodun sunucunuzda aktif olduğundan emin olun.
        do_update_stmt = stmt.on_conflict_do_update(
            constraint='pk_daily_usage',
            set_={
                # EN KRİTİK SATIR: Toplama yok, direkt üzerine yazma var.
                'total_seconds': stmt.excluded.total_seconds,
                'app_name': stmt.excluded.app_name, 
                'updated_at': datetime.utcnow()
            }
        )
    
        
        # Hazırlanan SQL ifadesini çalıştır
        db.execute(do_update_stmt)

    try:
        # Tüm işlemleri veritabanına işle
        db.commit()
    except Exception as e:
        db.rollback()
        # Hatanın detayını loglamak development için daha iyi olabilir
        print(f"DATABASE COMMIT ERROR: {e}") 
        raise HTTPException(status_code=500, detail=f"Database commit failed: {e}")
    
    # Analizleri arka plan görevi olarak tetikle
    try:
        unique_dates = {datetime.fromtimestamp(ev.timestamp_start / 1000.0).date() for ev in payload.events}
        for d in unique_dates:
            # ÖNEMLİ: Arka plan görevine 'db' session'ı direkt geçmek hatalara yol açar.
            # Bu yüzden bu şekilde bırakıyoruz, ancak production'da bu kısmın
            # yeni bir session açacak şekilde refactor edilmesi gerekir.
            background_tasks.add_task(calculate_daily_features, payload.user_id, d, db)
    except Exception as e:
        print(f"Analytics Error: {e}")

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