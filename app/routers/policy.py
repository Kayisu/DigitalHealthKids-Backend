from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID

from app.db import get_db
from app.models.policy import PolicyRule
from app.schemas.policy import PolicyResponse, Bedtime
from pydantic import BaseModel

router = APIRouter()
class ToggleBlockRequest(BaseModel):
    user_id: UUID
    package_name: str

@router.get("/current", response_model=PolicyResponse)
def get_current_policy(user_id: UUID, db: Session = Depends(get_db)):
    # 1. Veritabanından bu çocuğa ait, aktif ve 'block' olan kuralları çek
    rules = db.query(PolicyRule).filter(
        PolicyRule.user_id == user_id,
        PolicyRule.active == True,
        PolicyRule.action == "block"
    ).all()

    # 2. Paket isimlerini listeye çevir (Örn: ["com.instagram.android"])
    blocked_apps = [r.target_package for r in rules if r.target_package]

    return PolicyResponse(
        user_id=user_id,
        daily_limit_minutes=120, # MVP: Sabit değer
        blocked_apps=blocked_apps,
        bedtime=Bedtime(start="21:30", end="07:00"), # MVP: Sabit değer
    )
    

@router.post("/toggle-block", response_model=PolicyResponse)
def toggle_app_block(payload: ToggleBlockRequest, db: Session = Depends(get_db)):
    # 1. Mevcut kuralı bul
    rule = db.query(PolicyRule).filter(
        PolicyRule.user_id == payload.user_id,
        PolicyRule.target_package == payload.package_name,
        PolicyRule.action == "block"
    ).first()

    if rule:
        # Kural varsa durumunu tersine çevir (Aktif <-> Pasif)
        rule.active = not rule.active
    else:
        # Kural yoksa yeni oluştur (Default: Aktif)
        new_rule = PolicyRule(
            user_id=payload.user_id,
            source="parent_manual",
            target_category_id=None,
            target_package=payload.package_name,
            action="block",
            active=True
        )
        db.add(new_rule)

    db.commit()

    # Güncel listeyi dön (Frontend tek seferde güncellesin)
    return get_current_policy(payload.user_id, db)