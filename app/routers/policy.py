# app/routers/policy.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID

from app.db import get_db
from app.models.policy import PolicyRule
from app.schemas.policy import PolicyResponse, Bedtime

router = APIRouter()


@router.get("/current", response_model=PolicyResponse)
def get_current_policy(user_id: UUID, db: Session = Depends(get_db)):
    # Örnek: aktif block rule'larını toplayalım
    rules = db.query(PolicyRule).filter(
        PolicyRule.user_id == user_id,
        PolicyRule.active == True
    ).all()

    blocked_apps = [
        r.target_package for r in rules
        if r.action == "block" and r.target_package is not None
    ]

    # Şimdilik daily_limit + bedtime'i hardcode edelim
    # sonra user_settings tablosunu da modele ekleriz.
    return PolicyResponse(
        user_id=user_id,
        daily_limit_minutes=120,
        blocked_apps=blocked_apps,
        bedtime=Bedtime(start="21:30", end="07:00"),
    )
