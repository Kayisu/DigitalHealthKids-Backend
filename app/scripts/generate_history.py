import random
import sys
import os
import uuid
import hashlib
from datetime import datetime, timedelta, date

current_file_path = os.path.abspath(__file__)
scripts_dir = os.path.dirname(current_file_path)
app_dir = os.path.dirname(scripts_dir)
project_root = os.path.dirname(app_dir)

if project_root not in sys.path:
    sys.path.append(project_root)

from app.db import SessionLocal
from app.models.core import AppSession, AppCatalog, DailyUsageLog, User, Device
from app.services.categorizer import get_or_create_app_entry
from app.services.analytics import calculate_daily_features


# Default gün sayısı (bugün dahil)
DAYS_BACK = 21

# Persona listesi: (user_id, device_id, label, style)
PERSONAS = [
    ("30210d15-0821-41c5-bf59-510ac5b72f7b", "36d61160-7f5a-412a-b8c4-8138d25b49d7", "Cocuk Heavy", "heavy"),
    ("f6a7d251-1250-4df5-ab8b-04c684157292", "7c327f1e-4bf1-4166-862c-47d3afd27b78", "Cocuk Dengeli", "balanced"),
    ("0f8c537d-e2b1-4763-bac6-ccbf09dd87d9", "278d0184-db51-438b-b21f-42a4eb9f044d", "Cocuk Gece", "nightowl"),
    ("27ca606a-e236-48ff-addf-49943fe00eec", "98cc7ea5-f2f0-4d32-9ad4-a16d034bcf8b", "Cocuk Sosyal", "social"),
]

# Paket grupları (risk profillerine göre seçilecek)
GAMES = [
    "com.supercell.brawlstars",
    "com.supercell.clashofclans",
    "com.robtopx.geometryjump",
    "com.playstack.balatro.android",
    "jp.pokemon.pokemontcgp",
    "com.kiloo.subwaysurf",
    "com.shatteredpixel.shatteredpixeldungeon",
    "com.devolver.reigns",
    "com.chess",
    "com.colonist.colonist"
]

SOCIAL = [
    "com.instagram.android",
    "com.whatsapp",
    "com.twitter.android",
    "com.discord",
    "org.telegram.messenger",
    "com.reddit.frontpage",
    "com.snapchat.android"
]

VIDEO = [
    "com.google.android.youtube",
    "com.netflix.mediaclient",
    "com.twitch.android.app"
]

MUSIC = [
    "com.spotify.music",
    "com.shazam.android",
    "com.bandlab.bandlab"
]

SHOPPING = [
    "com.getir",
    "com.ataexpress.tiklagelsin",
    "tr.com.dominos",
    "com.sahibinden",
    "com.amazon.mShop.android.shopping",
    "com.lcwaikiki.android"
]

UTIL = [
    "com.openai.chatgpt"
]

ALL_PACKAGES = GAMES + SOCIAL + VIDEO + MUSIC + SHOPPING + UTIL

db = SessionLocal()

def get_app_name_guess(pkg):
    """Paket isminden güzel görünen bir uygulama adı uydurur."""
    if "com." in pkg:
        parts = pkg.split('.')
        # com.supercell.brawlstars -> Brawlstars
        if len(parts) > 2 and parts[1] in ["supercell", "google", "microsoft", "playstack"]:
                return parts[2].capitalize()
        return parts[-1].capitalize()
    return pkg

def get_or_create_user_device(user_uuid_str, device_uuid_str):
    try:
        u_uuid = uuid.UUID(user_uuid_str)
        d_uuid = uuid.UUID(device_uuid_str)
    except ValueError:
        print("❌ HATA: ID'ler UUID formatında değil!")
        sys.exit(1)

    user = db.query(User).filter(User.id == u_uuid).first()
    if not user:
        print(f"👤 Kullanıcı oluşturuluyor: {u_uuid}")
        user = User(
            id=u_uuid,
            full_name="Mock User",
            email=f"mock_{str(u_uuid)[:8]}@test.com",
            password_hash=hashlib.sha256("finalspace".encode("utf-8")).hexdigest(),
            birth_date=date(2010, 1, 1),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        db.refresh(user)

    device = db.query(Device).filter(Device.id == d_uuid).first()
    if not device:
        print(f"📱 Cihaz oluşturuluyor: {d_uuid}")
        device = Device(
            id=d_uuid,
            user_id=user.id,
            platform="Android",
            model="Mock Phone",
            os_version="14.0",
            enrolled_at=datetime.utcnow()
        )
        db.add(device)
        db.commit()
        db.refresh(device)
    else:
        db.refresh(device)

    return u_uuid, d_uuid

def pick_packages(style: str, is_weekend: bool) -> list[str]:
    if style == "heavy":
        base = GAMES + SOCIAL + VIDEO + MUSIC
        k = random.randint(9, 12) if is_weekend else random.randint(8, 11)
    elif style == "nightowl":
        base = SOCIAL + VIDEO + MUSIC + GAMES[:3]
        k = random.randint(6, 8)
    elif style == "social":
        base = SOCIAL + VIDEO + MUSIC + SHOPPING[:2]
        k = random.randint(7, 10)
        mandatory = [pkg for pkg in ["com.instagram.android", "com.twitter.android"] if pkg in base]
        pool = [pkg for pkg in base if pkg not in mandatory]
        remaining = max(k - len(mandatory), 0)
        selected_pool = random.sample(pool, min(remaining, len(pool)))
        picked = mandatory + selected_pool
        if len(picked) < k:
            extras = [pkg for pkg in pool if pkg not in selected_pool]
            picked += random.sample(extras, min(k - len(picked), len(extras)))
        return picked[:k]
    else:  # balanced
        base = SOCIAL[:3] + VIDEO[:1] + MUSIC[:2] + GAMES[:3] + SHOPPING[:2] + UTIL
        k = random.randint(5, 7)
    k = min(k, len(base))
    return random.sample(base, k)


def pick_duration_minutes(pkg: str, style: str, is_weekend: bool) -> int:
    is_game = pkg in GAMES
    is_social = pkg in SOCIAL
    is_video = pkg in VIDEO

    if style == "heavy":
        base = random.randint(35, 70) if is_weekend else random.randint(28, 55)
        if is_game or is_video:
            base += random.randint(15, 35)
        return base
    if style == "nightowl":
        base = random.randint(15, 35)
        if is_video or is_social:
            base += random.randint(8, 15)
        return base
    if style == "social":
        base = random.randint(18, 40)
        if is_social or is_video:
            base += random.randint(6, 12)
        return base
    # balanced
    base = random.randint(10, 25) if is_weekend else random.randint(8, 20)
    if is_game:
        base += 5
    return base


def pick_start_hour(style: str, is_weekend: bool) -> int:
    if style == "nightowl":
        # gece ağırlıklı: 21-01 arası baskın
        r = random.random()
        if r < 0.6:
            return random.choice([21, 22, 23, 0, 1])
        return random.randint(18, 23)
    if style == "heavy":
        return random.randint(9, 23)
    if style == "social":
        return random.randint(10, 23)
    # balanced
    return random.randint(9, 22 if not is_weekend else 23)


def create_mock_history(user_uuid_str: str, device_uuid_str: str, label: str, style: str):
    print(f"🚀 {label} ({style}) için veri üretimi başlıyor... ({DAYS_BACK} gün, bugün dahil)")
    
    try:
        user_uuid, device_uuid = get_or_create_user_device(user_uuid_str, device_uuid_str)
        
        # Önceki verileri temizle (Opsiyonel - Temiz kurulum için iyi olur)
        print("🧹 Günlük loglar temizleniyor (Mock verisi çakışmasın)...")
        db.query(DailyUsageLog).filter(DailyUsageLog.user_id == user_uuid).delete()
        db.commit()

        session_batch = []
        daily_log_batch = []
        
        end_date = datetime.combine(datetime.now().date(), datetime.min.time())
        start_date = end_date - timedelta(days=DAYS_BACK - 1)
        current_day = start_date

        while current_day <= end_date:
            day_str = current_day.strftime("%Y-%m-%d")
            day_date_obj = current_day.date()
            is_weekend = current_day.weekday() >= 5 
            
            # Günlük İstatistikleri Tutacak Sözlük
            # Format: { 'paket_adi': toplam_saniye }
            daily_stats = {} 

            daily_apps = pick_packages(style, is_weekend)
            
            print(f"📅 {day_str}: {len(daily_apps)} uygulama işleniyor...")

            for pkg in daily_apps:
                duration_min = pick_duration_minutes(pkg, style, is_weekend)
                duration_sec = duration_min * 60

                hour = pick_start_hour(style, is_weekend)
                minute = random.randint(0, 59)
                
                ts_start = datetime.strptime(f"{day_str} {hour}:{minute}", "%Y-%m-%d %H:%M")
                ts_end = ts_start + timedelta(seconds=duration_sec)

                # 1. SESSION Ekle
                session = AppSession(
                    user_id=user_uuid,
                    device_id=device_uuid,
                    package_name=pkg,
                    started_at=ts_start,
                    ended_at=ts_end,
                    source="mock_script",
                    payload={"mock": True}
                )
                session_batch.append(session)

                # 2. Günlük Toplamı Hesapla (DailyUsageLog için)
                if pkg in daily_stats:
                    daily_stats[pkg] += duration_sec
                else:
                    daily_stats[pkg] = duration_sec

            # Pazar günü ağır kullanıcıya ekstra 5 saatlik binge ekle
            if style == "heavy" and current_day.weekday() == 6:
                binge_pkg = random.choice(GAMES + VIDEO)
                binge_minutes = 300  # 5 saat
                binge_sec = binge_minutes * 60
                binge_hour = random.randint(12, 15)
                binge_minute = random.randint(0, 59)
                binge_start = datetime.strptime(f"{day_str} {binge_hour}:{binge_minute}", "%Y-%m-%d %H:%M")
                binge_end = binge_start + timedelta(seconds=binge_sec)

                session = AppSession(
                    user_id=user_uuid,
                    device_id=device_uuid,
                    package_name=binge_pkg,
                    started_at=binge_start,
                    ended_at=binge_end,
                    source="mock_script",
                    payload={"mock": True, "binge": True}
                )
                session_batch.append(session)
                daily_stats[binge_pkg] = daily_stats.get(binge_pkg, 0) + binge_sec

            # Gün bitti, o günün DailyUsageLog kayıtlarını oluştur
            for pkg, total_sec in daily_stats.items():
                app_name = get_app_name_guess(pkg)
                
                log_entry = DailyUsageLog(
                    user_id=user_uuid,
                    device_id=device_uuid,
                    usage_date=day_date_obj, # Date objesi
                    package_name=pkg,
                    app_name=app_name,
                    total_seconds=total_sec,
                    updated_at=datetime.utcnow()
                )
                daily_log_batch.append(log_entry)

            current_day += timedelta(days=1)

        # Toplu Kayıt İşlemi
        print(f"💾 {len(session_batch)} Session ve {len(daily_log_batch)} Günlük Log kaydediliyor...")
        
        db.bulk_save_objects(session_batch)
        db.bulk_save_objects(daily_log_batch)
        
        # Katalog Güncelleme (AppCatalog)
        print("📚 Katalog kontrol ediliyor...")
        for pkg in ALL_PACKAGES:
            get_or_create_app_entry(db, pkg)

        db.commit()

        # FeatureDaily yeniden hesapla ki kategoriler doğru yansısın
        print("🧮 FeatureDaily yeniden hesaplanıyor...")
        day_ptr = start_date.date()
        end_day = end_date.date()
        while day_ptr <= end_day:
            calculate_daily_features(str(user_uuid), day_ptr, db)
            day_ptr += timedelta(days=1)
        print(f"✅ {label} tamamlandı! Dashboard dolu olmalı.")

    except Exception as e:
        print(f"❌ BEKLENMEYEN HATA ({label}): {e}")
        db.rollback()


if __name__ == "__main__":
    for u, d, label, style in PERSONAS:
        create_mock_history(u, d, label, style)
    db.close()