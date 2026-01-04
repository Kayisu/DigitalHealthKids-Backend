# app/routers/policy.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
from app.schemas.policy import ToggleBlockRequest, AutoPolicyResponse

from app.db import get_db
from app.models.policy import PolicyRule
from app.models.core import UserSettings
from app.schemas.policy import (
    PolicyResponse, 
    Bedtime, 
    PolicySettingsRequest, 
    BlockAppRequest,
)
from app.services.auto_policy import apply_auto_policy, preview_auto_policy
from app.models.core import User

# Basit öneri seti (MVP): risk ve tahmine göre ebeveyne gösterilecek, otomatik uygulama yok
RECOMMENDATIONS = [
    {
        "id": "reduce_weekday_10",
        "label": "Hafta içi günlük süreyi %10 azalt",
        "applies": lambda risk, profile: risk.lower() in {"orta", "yüksek"},
    },
    {
        "id": "block_games_weeknights",
        "label": "Hafta içi akşam oyunları 21:00 sonrası kısıtla",
        "applies": lambda risk, profile: "oyuncu" in profile.lower(),
    },
    {
        "id": "sleep_mode",
        "label": "Gece kullanımını 1 saat erkene kapat",
        "applies": lambda risk, profile: "gece" in profile.lower(),
    },
    {
        "id": "social_cut_15",
        "label": "Sosyal medya süresini %15 düşür",
        "applies": lambda risk, profile: "sosyal" in profile.lower() or risk.lower() == "yüksek",
    },
]

router = APIRouter()

# --- YARDIMCI FONKSİYON ---
# Tekrar tekrar yazmamak için policy cevabını üreten fonksiyon
def _build_policy_response(user_id: UUID, db: Session) -> PolicyResponse:
    # 1. Engelli listesini al
    rules = db.query(PolicyRule).filter(
        PolicyRule.user_id == user_id,
        PolicyRule.active == True,
        PolicyRule.action == "block"
    ).all()
    blocked_list = [r.target_package for r in rules if r.target_package]

    # 2. Ayarları çek
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    
    # Başlangıçta her şey "Yok" (None)
    final_limit = None
    final_bedtime = None

    if settings:
        # Eğer veritabanında limit varsa al, yoksa None kalır.
        final_limit = settings.daily_limit_minutes 
        
        # Sadece hem başlangıç hem bitiş saati varsa Bedtime objesi oluştur
        if settings.nightly_start and settings.nightly_end:
            final_bedtime = Bedtime(
                start=settings.nightly_start.strftime("%H:%M"), 
                end=settings.nightly_end.strftime("%H:%M")
            )

    weekend_extra = settings.weekend_relax_pct if settings else 0

    return PolicyResponse(
        user_id=user_id,
        daily_limit_minutes=final_limit, 
        blocked_apps=blocked_list,
        bedtime=final_bedtime,
        weekend_extra_minutes=weekend_extra or 0,
    )

# --- ENDPOINTLER ---

@router.get("/current", response_model=PolicyResponse)
def get_current_policy(user_id: UUID, db: Session = Depends(get_db)):
    """Mevcut kuralları getir (Telefona inen veri)"""
    return _build_policy_response(user_id, db)


@router.post("/auto-apply", response_model=AutoPolicyResponse)
def auto_apply_policy(user_id: UUID, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    result = apply_auto_policy(db, str(user_id), user.birth_date)
    return AutoPolicyResponse(
        user_id=user_id,
        window_days=result.window_days,
        stage1_daily_limit=result.stage1_daily_limit,
        stage2_daily_limit=result.stage2_daily_limit,
        weekend_relax_pct=result.weekend_relax_pct,
        app_limits=result.app_limits,
        bedtime_start=result.bedtime_start,
        bedtime_end=result.bedtime_end,
        fallback_used=result.fallback_used,
        message=result.message,
    )


@router.get("/auto-preview", response_model=AutoPolicyResponse)
def auto_preview_policy(user_id: UUID, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    result = preview_auto_policy(db, str(user_id), user.birth_date)
    return AutoPolicyResponse(
        user_id=user_id,
        window_days=result.window_days,
        stage1_daily_limit=result.stage1_daily_limit,
        stage2_daily_limit=result.stage2_daily_limit,
        weekend_relax_pct=result.weekend_relax_pct,
        app_limits=result.app_limits,
        bedtime_start=result.bedtime_start,
        bedtime_end=result.bedtime_end,
        fallback_used=result.fallback_used,
        message=result.message,
    )


@router.get("/recommendations")
def get_policy_recommendations(risk_level: str, profile: str):
    """
    AI çıktılarına göre ebeveyne gösterilecek öneri listesi (uygulama yok).
    """
    risk_level = (risk_level or "").lower()
    profile = (profile or "").lower()
    recs = [r["label"] for r in RECOMMENDATIONS if r["applies"](risk_level, profile)]
    if not recs:
        recs = ["Mevcut ayarları sürdür, düzenli takibe devam et."]
    return {"suggestions": recs}

@router.put("/settings", response_model=PolicyResponse)
def update_settings(
    user_id: UUID, 
    payload: PolicySettingsRequest, 
    db: Session = Depends(get_db)
):
    """Limit ve Uyku saatlerini güncelle"""
    
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if not settings:
        settings = UserSettings(user_id=user_id)
        db.add(settings)

    t_start = None
    t_end = None

    # Eğer mobilden saat verisi geldiyse (Switch AÇIK ise) parse et
    if payload.bedtime_start and payload.bedtime_end:
        try:
            t_start = datetime.strptime(payload.bedtime_start, "%H:%M").time()
            t_end = datetime.strptime(payload.bedtime_end, "%H:%M").time()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM")
    # --- DÜZELTME BİTİŞİ ---

    # 3. Verileri güncelle (Artık None değerleri de kabul ediliyor)
    settings.daily_limit_minutes = payload.daily_limit_minutes # Bu zaten Optional idi
    settings.nightly_start = t_start
    settings.nightly_end = t_end
    settings.weekend_relax_pct = payload.weekend_relax_pct
    
    if payload.blocked_packages is not None:
        # 1. Gelen liste (Set olarak işlem yapmak daha hızlı)
        new_blocked_set = set(payload.blocked_packages)

        # 2. Mevcut kuralları çek
        existing_rules = db.query(PolicyRule).filter(
            PolicyRule.user_id == user_id,
            PolicyRule.action == "block"
        ).all()

        # Mevcut kuralları bir map'e al: {package_name: rule_object}
        rules_map = {r.target_package: r for r in existing_rules}

        # 3. Gelen listedeki her paket için işlem yap
        for pkg in new_blocked_set:
            if pkg in rules_map:
                # Kural zaten var, aktif değilse aktifleştir
                if not rules_map[pkg].active:
                    rules_map[pkg].active = True
            else:
                # Kural yok, yeni oluştur
                new_rule = PolicyRule(
                    user_id=user_id,
                    target_package=pkg,
                    action="block",
                    source="parent_settings",
                    active=True,
                    effective_at=datetime.utcnow()
                )
                db.add(new_rule)
        
        # 4. Listede OLMAYAN ama veritabanında AKTİF olanları pasife çek (Yasağı kaldırılanlar)
        for pkg, rule in rules_map.items():
            if pkg not in new_blocked_set and rule.active:
                rule.active = False
    
    db.commit()
    
    return _build_policy_response(user_id, db)

@router.post("/block", response_model=PolicyResponse)
def block_app(
    user_id: UUID, 
    payload: BlockAppRequest, 
    db: Session = Depends(get_db)
):
    """Bir uygulamayı yasaklar listesine ekle"""
    
    # Zaten böyle bir kural var mı?
    existing_rule = db.query(PolicyRule).filter(
        PolicyRule.user_id == user_id,
        PolicyRule.target_package == payload.package_name,
        PolicyRule.action == "block"
    ).first()

    if existing_rule:
        # Varsa ve pasifse aktifleştir
        existing_rule.active = True
    else:
        # Yoksa yeni kural yarat
        new_rule = PolicyRule(
            user_id=user_id,
            target_package=payload.package_name,
            action="block",
            source="parent_manual",
            active=True,
            effective_at=datetime.utcnow()
        )
        db.add(new_rule)
    
    db.commit()
    return _build_policy_response(user_id, db)

@router.post("/unblock", response_model=PolicyResponse)
def unblock_app(
    user_id: UUID, 
    payload: BlockAppRequest, 
    db: Session = Depends(get_db)
):
    """Bir uygulamanın yasağını kaldır"""
    
    rule = db.query(PolicyRule).filter(
        PolicyRule.user_id == user_id,
        PolicyRule.target_package == payload.package_name,
        PolicyRule.action == "block"
    ).first()

    if rule:
        # Silmek yerine pasife çekiyoruz (Soft Delete) - Raporlama için daha iyi
        rule.active = False
        db.commit()

    return _build_policy_response(user_id, db)

@router.post("/toggle-block", response_model=PolicyResponse)
def toggle_block(
    payload: ToggleBlockRequest, # Body'den gelen veri
    db: Session = Depends(get_db)
):
    """Varsa yasağı kaldır, yoksa yasakla (Aç/Kapa)"""
    
    # Kural var mı diye bak
    existing_rule = db.query(PolicyRule).filter(
        PolicyRule.user_id == payload.user_id,
        PolicyRule.target_package == payload.package_name,
        PolicyRule.action == "block"
    ).first()

    if existing_rule:
        # Kural varsa tersine çevir (True -> False veya False -> True)
        existing_rule.active = not existing_rule.active
    else:
        # Kural hiç yoksa, "Aktif" olarak yeni oluştur
        new_rule = PolicyRule(
            user_id=payload.user_id,
            target_package=payload.package_name,
            action="block",
            source="parent_manual",
            active=True,
            effective_at=datetime.utcnow()
        )
        db.add(new_rule)
    
    db.commit()
    return _build_policy_response(payload.user_id, db) 