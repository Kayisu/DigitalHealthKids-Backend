# app/services/analytics.py
from datetime import date, datetime, time, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.core import AppSession, FeatureDaily, UserSettings, AppCatalog, AppCategory
from app.services.categorizer import get_or_create_app_entry

def calculate_daily_features(user_id: str, target_date: date, db: Session):
    """
    Belirtilen gün için kullanıcının oturumlarını analiz eder ve
    FeatureDaily tablosuna 'AI Özelliklerini' yazar.
    """
    
    # 1. O günün oturumlarını çek
    # (Not: Timezone dönüşümü router'da yapılmıştı, burada DB'deki UTC/Local duruma göre filtreliyoruz)
    # Basitlik için tüm günün kayıtlarını alıyoruz.
    start_of_day = datetime.combine(target_date, time.min)
    end_of_day = datetime.combine(target_date, time.max)
    
    sessions = db.query(AppSession).filter(
        AppSession.user_id == user_id,
        AppSession.started_at >= start_of_day,
        AppSession.started_at <= end_of_day
    ).all()
    
    if not sessions:
        return # Veri yoksa işlem yapma (veya 0 olarak kaydet)

    # 2. Kullanıcı Ayarlarını (Uyku Saati) Çek
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    
    # Varsayılan Uyku Aralığı: 22:00 - 07:00
    bedtime_start = settings.nightly_start if settings and settings.nightly_start else time(22, 0)
    bedtime_end = settings.nightly_end if settings and settings.nightly_end else time(7, 0)

    # 3. Metrikleri Hesapla
    total_minutes = 0
    night_minutes = 0
    cat_durations = {"game": 0, "social": 0, "video": 0, "education": 0, "other": 0}

    def overlap_minutes(start_dt: datetime, end_dt: datetime, win_start_t: time, win_end_t: time) -> float:
        """Gece aralığı gün aşsa bile oturumun kesişen dakikasını hesapla."""
        minutes = 0.0
        cursor = start_dt
        while cursor < end_dt:
            day_end = datetime.combine(cursor.date(), time.max, tzinfo=cursor.tzinfo)
            seg_end = min(day_end, end_dt)

            if win_start_t > win_end_t:
                # Gece yarısını geçen aralık: [win_start, 24:00) ve [00:00, win_end)
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

    def _interval_overlap_minutes(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> float:
        if a_end <= b_start or a_start >= b_end:
            return 0.0
        overlap_start = max(a_start, b_start)
        overlap_end = min(a_end, b_end)
        return max((overlap_end - overlap_start).total_seconds(), 0) / 60.0

    for sess in sessions:
        duration_sec = (sess.ended_at - sess.started_at).total_seconds()
        duration_min = duration_sec / 60.0
        if duration_min <= 0:
            continue

        total_minutes += duration_min

        # Kategori
        app_entry = get_or_create_app_entry(db, sess.package_name)
        cat_key = "other"
        if app_entry.category:
            cat_key = app_entry.category.key
        cat_durations[cat_key] = cat_durations.get(cat_key, 0) + duration_min

        # Gece kesişimi (gerçek overlap)
        night_minutes += overlap_minutes(sess.started_at, sess.ended_at, bedtime_start, bedtime_end)

    # 4. Oranları Hesapla
    total_m = max(total_minutes, 1) # Sıfıra bölünme hatası önlemi
    gaming_ratio = (cat_durations.get("game", 0) / total_m)
    social_ratio = (cat_durations.get("social", 0) / total_m)

    # 5. FeatureDaily Tablosuna Yaz (Upsert)
    feature_entry = db.query(FeatureDaily).filter_by(user_id=user_id, date=target_date).first()
    
    if not feature_entry:
        feature_entry = FeatureDaily(user_id=user_id, date=target_date)
        db.add(feature_entry)
    
    feature_entry.total_minutes = int(total_minutes)
    feature_entry.night_minutes = int(night_minutes)
    feature_entry.gaming_ratio = round(gaming_ratio, 2)
    feature_entry.social_ratio = round(social_ratio, 2)
    feature_entry.session_count = len(sessions)
    
    # Tarihsel Özellikler
    feature_entry.weekday = target_date.weekday() # 0-6
    feature_entry.weekend = (target_date.weekday() >= 5) # Cmt-Paz
    # is_holiday ileride ebeveyn girişine bağlanabilir, şimdilik hafta sonu ile aynı varsayalım
    feature_entry.is_holiday = feature_entry.weekend 

    db.commit()
    return feature_entry