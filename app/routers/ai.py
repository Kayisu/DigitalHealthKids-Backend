# app/routers/ai.py
from fastapi import APIRouter, Depends
from requests import Session
from app.db import get_db
from app.services.ai_engine import AIEngine

router = APIRouter(prefix="/ai", tags=["AI"])

@router.get("/dashboard/{user_id}")
def get_ai_dashboard(user_id: str, db: Session = Depends(get_db)):
    # Engine'i başlat
    engine = AIEngine(db, user_id)
    
    # TODO: Mock Data switch'i (Query param veya env variable ile kontrol edilebilir)
    # engine._get_mock_data_if_needed() 
    
    # Adım adım hesaplamaları çağır
    risk = engine.calculate_risk_score()
    profile = engine.determine_profile()
    forecast = engine.predict_next_week()
    recs = engine.get_smart_recommendations(risk['level'], profile)
    
    # TODO: Response modelini oluştur ve return et.
    return {
        "risk_analysis": risk,
        "user_profile": profile,
        "forecast": forecast,
        "suggestions": recs
    }