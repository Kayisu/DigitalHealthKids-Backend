# app/routers/policy.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from app.db import get_db
from app.models.policy import PolicyRule
from app.models.core import UserSettings
from app.schemas.policy import PolicyResponse, Bedtime

router = APIRouter()

@router.get("/current", response_model=PolicyResponse)
def get_current_policy(user_id: UUID, db: Session = Depends(get_db)):
    # 1. Blocklanan uygulamalar
    rules = db.query(PolicyRule).filter(
        PolicyRule.user_id == user_id,
        PolicyRule.active == True
    ).all()

    blocked_apps = [
        r.target_package for r in rules
        if r.action == "block" and r.target_package is not None
    ]

    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()

    # Varsayılanlar (Fallback)
    default_start = "21:30"
    default_end = "07:00"
    default_limit = 120

    start_str = default_start
    end_str = default_end
    limit_val = default_limit

    if settings:
        if settings.nightly_start:
            start_str = settings.nightly_start.strftime("%H:%M")
        
        if settings.nightly_end:
            end_str = settings.nightly_end.strftime("%H:%M")
            
        if settings.daily_limit_minutes is not None:
            limit_val = settings.daily_limit_minutes

    return PolicyResponse(
        user_id=user_id,
        daily_limit_minutes=limit_val,
        blocked_apps=blocked_apps,
        bedtime=Bedtime(start=start_str, end=end_str),
    )