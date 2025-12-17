# app/routers/policy.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
from app.schemas.policy import ToggleBlockRequest

from app.db import get_db
from app.models.policy import PolicyRule
from app.models.core import UserSettings
from app.schemas.policy import (
    PolicyResponse, 
    Bedtime, 
    PolicySettingsRequest, 
    BlockAppRequest
)

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

    return PolicyResponse(
        user_id=user_id,
        daily_limit_minutes=final_limit, 
        blocked_apps=blocked_list,
        bedtime=final_bedtime           
    )

# --- ENDPOINTLER ---

@router.get("/current", response_model=PolicyResponse)
def get_current_policy(user_id: UUID, db: Session = Depends(get_db)):
    """Mevcut kuralları getir (Telefona inen veri)"""
    return _build_policy_response(user_id, db)

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

    # --- 🔥 DÜZELTME BAŞLANGICI ---
    # Varsayılan olarak NULL (Kısıtlama yok)
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