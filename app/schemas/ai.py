from typing import Dict, List, Optional

from pydantic import BaseModel


class RiskDetails(BaseModel):
    night_minutes_avg: Optional[float] = None
    night_score: Optional[int] = None
    total_minutes_avg: Optional[float] = None
    limit_score: Optional[int] = None
    mix_ratio_avg: Optional[float] = None
    mix_score: Optional[int] = None
    weekend_score: Optional[int] = None
    weekend_relax_pct: Optional[int] = None
    data_points: Optional[int] = None
    method: Optional[str] = None
    confidence: Optional[float] = None


class RiskAnalysis(BaseModel):
    score: int
    level: str
    details: Dict[str, object] | RiskDetails


class ProfileProbability(BaseModel):
    label: str
    probability: float


class ProfilePrediction(BaseModel):
    label: str
    probabilities: Optional[List[ProfileProbability]] = None


class ForecastResponse(BaseModel):
    daily_avg: int
    weekly_total: int
    daily_series: List[int]
    start_weekday: Optional[int] = None


class AIDashboardResponse(BaseModel):
    risk_analysis: RiskAnalysis
    user_profile: ProfilePrediction
    forecast: ForecastResponse
    suggestions: List[str]
