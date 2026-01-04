# app/routers/ai.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.ai import AIDashboardResponse
from app.services.ai_engine import AIEngine

router = APIRouter(prefix="/ai", tags=["AI"])

@router.get("/dashboard/{user_id}", response_model=AIDashboardResponse)
def get_ai_dashboard(
    user_id: str,
    db: Session = Depends(get_db),
):
    # Engine'i başlat
    engine = AIEngine(db, user_id)
    
    # Veri yoksa backend otomatik mock'a düşer; client tarafında toggle gerekmiyor
    risk = engine.calculate_risk_score(allow_mock=True)
    profile = engine.determine_profile(allow_mock=True)
    forecast = engine.predict_next_week(allow_mock=True)
    recs = engine.get_smart_recommendations(risk['level'], profile['label'])
    
    return AIDashboardResponse(
        risk_analysis=risk,
        user_profile=profile,
        forecast=forecast,
        suggestions=recs,
    )