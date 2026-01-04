# app/services/ai_engine.py
import os
import random
from datetime import date, timedelta
from statistics import mean
from typing import Dict, List, Tuple
import csv

from sqlalchemy.orm import Session

from app.models.core import FeatureDaily, UserSettings
from app.models.risk import RiskAssessment, RiskDimension, RiskLevel

class AIEngine:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self.has_data = True
        self.settings = self._load_user_settings()

    def _get_mock_data_if_needed(self):
        """
        Geliştirme aşamasında frontend'i beslemek için kullanılacak.
        Prod ortamında bu fonksiyon devre dışı bırakılacak.
        """
        # TODO: Eğer self.has_data False ise ve DEBUG modundaysak;
        #       Rastgele FeatureDaily objeleri (High risk, Low risk vb.) üretip self.history'ye ata.
        pass

    def calculate_risk_score(self, allow_mock: bool = True) -> Dict:
        """
        Kullanıcının dijital bağımlılık riskini hesaplar.
        Çıktı: 0-100 arası skor ve 'Düşük/Orta/Yüksek' etiketi.
        """
        history, using_mock = self._get_history(days=14, allow_mock=allow_mock)
        settings = self.settings

        if not history:
            self.has_data = False
            return {"score": 0, "level": "Veri Yok", "details": {}}

        # Ağırlıklar (toplam 1.0)
        W_NIGHT = 0.40
        W_LIMIT = 0.30
        W_MIX = 0.20
        W_WEEKEND = 0.10

        # 1) Gece kullanımı: 60 dk ve üstü tam risk kabul edildi
        night_avg = mean([h.night_minutes for h in history])
        night_score = min(100, int(round((night_avg / 60) * 100)))

        # 2) Günlük limit aşımı: limit yoksa nötr 50 ver; hafta sonu/tatil gevşeme payı ekle
        limit_score = self._compute_limit_score(
            history,
            settings.daily_limit_minutes,
            settings.weekend_relax_pct or 0,
        )

        # 3) Kategori dağılımı: oyun + sosyal oranı
        mix_avg = mean([(float(h.gaming_ratio or 0) + float(h.social_ratio or 0)) for h in history])
        total_avg = mean([h.total_minutes for h in history])
        mix_score = min(100, int(round(mix_avg * 100)))

        # 4) Hafta sonu/tatil aşırı yükü: hafta içi ortalamaya göre fark
        weekend_vals = [h.total_minutes for h in history if h.weekend or h.is_holiday]
        weekday_vals = [h.total_minutes for h in history if not h.weekend and not h.is_holiday]
        if weekday_vals:
            weekend_penalty = max(
                (mean(weekend_vals) - mean(weekday_vals)) / max(mean(weekday_vals), 1),
                0,
            ) if weekend_vals else 0
        else:
            weekend_penalty = 0
        weekend_score = min(100, int(round(weekend_penalty * 100)))

        composite = (
            W_NIGHT * night_score
            + W_LIMIT * limit_score
            + W_MIX * mix_score
            + W_WEEKEND * weekend_score
        )
        score = int(round(composite))
        level = self._map_level(score)

        confidence = min(len(history) / 14.0, 1.0)

        details = {
            "night_minutes_avg": round(night_avg, 1),
            "night_score": night_score,
            "total_minutes_avg": round(total_avg, 1),
            "limit_score": limit_score,
            "mix_ratio_avg": round(mix_avg, 2),
            "mix_score": mix_score,
            "weekend_score": weekend_score,
            "weekend_relax_pct": settings.weekend_relax_pct,
            "data_points": len(history),
            "method": "rule",
            "confidence": round(confidence, 2),
        }

        # Persist et (idempotent upsert)
        if not using_mock:
            self._persist_risk(score, level, details)

        return {"score": score, "level": level, "details": details}

    def determine_profile(self, allow_mock: bool = True) -> Dict:
        """
        Kullanıcıyı persona ile eşleştirir.
        Öncelik: ML sınıflandırıcı (eğitim CSV varsa + sklearn). Yoksa kural tabanlı.
        Dönen yapı: {"label": str, "probabilities": List[{label, probability}]}
        """
        history, _ = self._get_history(days=30, allow_mock=allow_mock)
        if not history:
            return {"label": "Profil Belirlenemedi", "probabilities": []}

        # ML ile dene
        ml_pred = self._determine_profile_ml(history)
        if ml_pred:
            return ml_pred

        # kural tabanlı fallback
        night_avg = mean([h.night_minutes for h in history])
        gaming_avg = mean([float(h.gaming_ratio or 0) for h in history])
        social_avg = mean([float(h.social_ratio or 0) for h in history])
        weekend_avg = mean([h.total_minutes for h in history if h.weekend]) if any(h.weekend for h in history) else 0
        weekday_avg = mean([h.total_minutes for h in history if not h.weekend]) if any((not h.weekend) for h in history) else 0

        if night_avg > 45:
            label = "Gece Kuşu"
        elif gaming_avg > 0.4:
            label = "Sıkı Oyuncu"
        elif social_avg > 0.4:
            label = "Sosyal Medya Tutkunu"
        elif weekend_avg > weekday_avg * 1.25 and weekend_avg > 90:
            label = "Hafta Sonu Odaklı"
        else:
            label = "Dengeli Kullanıcı"

        return {"label": label, "probabilities": []}

    def predict_next_week(self, allow_mock: bool = True, use_ml: bool = True) -> Dict:
        """
        Gelecek haftaki tahmini ekran süresi.
        Varsayılan: küçük veri için hafif bir RandomForest tahmini; veri çok azsa (<5 gün)
        trend tabanlı fallback.
        """
        history, _ = self._get_history(days=30, allow_mock=allow_mock)
        if not history:
            return {"daily_avg": 0, "weekly_total": 0, "daily_series": []}

        # kronolojik sıraya al
        ordered = sorted(history, key=lambda h: h.date)

        # ML tabanlı tahmin (RandomForest)
        series = None
        if use_ml:
            series = self._forecast_with_random_forest(ordered)

        if not series:
            series = self._forecast_with_trend(ordered)

        if not series:
            return {"daily_avg": 0, "weekly_total": 0, "daily_series": [], "start_weekday": None}

        weekly_total = sum(series)
        daily_avg = int(round(mean(series)))
        start_weekday = (ordered[-1].date + timedelta(days=1)).weekday()
        return {"daily_avg": daily_avg, "weekly_total": weekly_total, "daily_series": series, "start_weekday": start_weekday}

    def _forecast_with_random_forest(self, ordered: List[FeatureDaily]) -> List[int]:
        from sklearn.ensemble import RandomForestRegressor

        if len(ordered) < 5:
            return []

        # Özellikler: önceki gün toplamı, weekday, weekend bayrağı
        totals = [h.total_minutes for h in ordered]
        features: List[List[float]] = []
        targets: List[float] = []
        for i in range(1, len(ordered)):
            prev_total = totals[i - 1]
            wd = ordered[i].weekday
            weekend = 1 if (ordered[i].weekend or ordered[i].is_holiday) else 0
            features.append([prev_total, wd, weekend])
            targets.append(float(totals[i]))

        if len(features) < 3:
            return []

        model = RandomForestRegressor(
            n_estimators=80,
            max_depth=4,
            random_state=42,
        )
        model.fit(features, targets)

        # İleriye doğru 7 gün tahmin (iteratif, son günün çıktısını bir sonraki giriş yap)
        series: List[int] = []
        last_total = totals[-1]
        last_date = ordered[-1].date
        for step in range(1, 8):
            day = last_date + timedelta(days=step)
            wd = day.weekday()
            weekend = 1 if wd >= 5 else 0
            pred = model.predict([[last_total, wd, weekend]])[0]
            safe_pred = max(int(round(pred)), 0)
            series.append(safe_pred)
            last_total = safe_pred

        return series

    def _forecast_with_trend(self, ordered: List[FeatureDaily]) -> List[int]:
        if len(ordered) < 2:
            return []

        totals = [h.total_minutes for h in ordered]
        deltas = [totals[i] - totals[i - 1] for i in range(1, len(totals))]
        trend = mean(deltas) if deltas else 0
        base = mean(totals)

        series: List[int] = []
        current = base + trend
        for _ in range(7):
            series.append(max(int(round(current)), 0))
            current += trend

        return series

    def _determine_profile_ml(self, history: List[FeatureDaily]) -> Dict | None:
        """
        Eğitilmiş bir CSV varsa (varsayılan yol: app/assets/persona_training.csv) LogisticRegression ile
        sınıflandırma yapar. Başarısız olursa None döner.
        CSV formatı (header): label,night_avg,total_avg,gaming_ratio,social_ratio,weekend_ratio
        """
        train_path = os.getenv("PERSONA_TRAIN_PATH", "app/assets/persona_training.csv")
        if not os.path.exists(train_path):
            return None

        try:
            from sklearn.ensemble import HistGradientBoostingClassifier
        except ImportError:
            return None

        rows: List[Tuple[str, List[float]]] = []
        with open(train_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                try:
                    label = r["label"].strip()
                    feats = [
                        float(r["night_avg"]),
                        float(r["total_avg"]),
                        float(r["gaming_ratio"]),
                        float(r["social_ratio"]),
                        float(r.get("weekend_ratio", 0.0)),
                    ]
                    rows.append((label, feats))
                except Exception:
                    continue

        if len(rows) < 8:
            return None

        labels = [r[0] for r in rows]
        X = [r[1] for r in rows]

        model = HistGradientBoostingClassifier(max_depth=5, max_iter=120, random_state=42)
        model.fit(X, labels)

        feats_current = self._aggregate_profile_features(history)
        if not feats_current:
            return None

        pred = model.predict([feats_current])[0]
        probabilities: List[Dict[str, float]] = []
        if hasattr(model, "predict_proba"):
            try:
                raw = [float(p) for p in model.predict_proba([feats_current])[0]]
                T = 1.5
                tempered = [pow(max(p, 1e-6), 1 / T) for p in raw]
                s = sum(tempered)
                tempered = [p / s for p in tempered]
                # blend with uniform to avoid 100%
                k = len(tempered)
                alpha = 0.9
                blended = [alpha * p + (1 - alpha) * (1.0 / k) for p in tempered]
                s2 = sum(blended)
                blended = [p / s2 for p in blended]
                for label, p in zip(model.classes_, blended):
                    probabilities.append({"label": str(label), "probability": float(p)})
            except Exception:
                probabilities = []

        return {"label": str(pred), "probabilities": probabilities}

    def _aggregate_profile_features(self, history: List[FeatureDaily]) -> List[float]:
        if not history:
            return []

        night_avg = mean([h.night_minutes for h in history])
        total_avg = mean([h.total_minutes for h in history])
        gaming_avg = mean([float(h.gaming_ratio or 0) for h in history])
        social_avg = mean([float(h.social_ratio or 0) for h in history])
        weekend_vals = [h.total_minutes for h in history if h.weekend]
        weekday_vals = [h.total_minutes for h in history if not h.weekend]
        weekend_ratio = 0.0
        if weekend_vals and weekday_vals:
            weekend_ratio = mean(weekend_vals) / max(mean(weekday_vals), 1.0)

        return [night_avg, total_avg, gaming_avg, social_avg, weekend_ratio]

    def get_smart_recommendations(self, risk_level: str, profile: str) -> List[str]:
        """
        Risk ve Profile göre ebeveyne aksiyon önerileri sunar.
        """
        recommendations = []

        if risk_level.lower() == "yüksek":
            recommendations.append("Günlük süre limitini düşür ve bildirimleri kısıtla.")
        elif risk_level.lower() == "orta":
            recommendations.append("Hafta içi ekran süresini %10 azaltmayı dene.")

        if profile.lower().startswith("gece"):
            recommendations.append("Gece kullanımını 1 saat erkene kapatmayı ayarla.")
        if "oyuncu" in profile.lower():
            recommendations.append("Oyun kategorisine özel günlük limit belirle.")
        if not recommendations:
            recommendations.append("Mevcut ayarları sürdür, düzenli takibe devam et.")

        return recommendations

    # --- Internal helpers ---
    def _load_feature_history(self, days: int) -> List[FeatureDaily]:
        today = date.today()
        cutoff = today - timedelta(days=days)
        return (
            self.db.query(FeatureDaily)
            .filter(
                FeatureDaily.user_id == self.user_id,
                FeatureDaily.date >= cutoff,
                FeatureDaily.date < today,  # bugünün verisini dışla
            )
            .order_by(FeatureDaily.date.desc())
            .all()
        )

    def _get_history(self, days: int, allow_mock: bool) -> Tuple[List[FeatureDaily], bool]:
        history = self._load_feature_history(days=days)
        if history:
            self.has_data = True
            return history, False

        if allow_mock and self._is_mock_enabled():
            mock_hist = self._build_mock_history(days=days)
            self.has_data = False
            return mock_hist, True

        self.has_data = False
        return [], False

    def _load_user_settings(self) -> UserSettings:
        return self.db.query(UserSettings).filter(UserSettings.user_id == self.user_id).first() or UserSettings(
            daily_limit_minutes=None,
            nightly_start=None,
            nightly_end=None,
            weekend_relax_pct=None,
            min_night_minutes=None,
            min_session_seconds=None,
            session_app_seconds=None,
        )

    def _map_level(self, score: int) -> str:
        if score >= 67:
            return "Yüksek"
        if score >= 34:
            return "Orta"
        return "Düşük"

    def _is_mock_enabled(self) -> bool:
        flag = os.getenv("AI_DEBUG_MOCK", "false").lower() in {"1", "true", "yes"}
        return flag

    def _compute_limit_score(self, history: List[FeatureDaily], limit: int | None, weekend_relax_pct: int) -> int:
        if not limit or limit <= 0:
            return 50

        relax = max(weekend_relax_pct or 0, 0) / 100.0
        scores = []
        for h in history:
            day_limit = limit * (1 + relax) if (h.weekend or h.is_holiday) else limit
            over_pct = max((h.total_minutes - day_limit) / max(day_limit, 1), 0)
            scores.append(over_pct)

        if not scores:
            return 50
        return min(100, int(round(mean(scores) * 100)))

    def _build_mock_history(self, days: int) -> List[FeatureDaily]:
        today = date.today()
        items: List[FeatureDaily] = []
        for i in range(days):
            d = today - timedelta(days=i)
            total = random.randint(60, 240)
            night = random.randint(0, 80)
            gaming_ratio = round(random.uniform(0.05, 0.5), 2)
            social_ratio = round(random.uniform(0.05, 0.5), 2)
            items.append(
                FeatureDaily(
                    user_id=self.user_id,
                    date=d,
                    total_minutes=total,
                    night_minutes=night,
                    gaming_ratio=gaming_ratio,
                    social_ratio=social_ratio,
                    session_count=random.randint(3, 25),
                    weekday=d.weekday(),
                    weekend=d.weekday() >= 5,
                    is_holiday=False,
                )
            )
        return items

    def _persist_risk(self, score: int, level_label: str, details: Dict):
        as_of = date.today()

        # Meta tablolarda kaydı hazırla
        dim = self._get_or_create_dimension(key="overall", display_name="Genel Risk")
        lvl = self._get_or_create_level(level_label)

        prob = round(score / 100, 3)

        entry = (
            self.db.query(RiskAssessment)
            .filter_by(user_id=self.user_id, as_of_date=as_of, dimension_id=dim.id)
            .first()
        )
        if not entry:
            entry = RiskAssessment(
                user_id=self.user_id,
                as_of_date=as_of,
                dimension_id=dim.id,
            )
            self.db.add(entry)

        entry.level_id = lvl.id
        entry.prob = prob
        entry.model_key = "rule_v1"
        entry.features = {"score": score, "level": level_label, **details}

        self.db.commit()

    def _get_or_create_dimension(self, key: str, display_name: str) -> RiskDimension:
        obj = self.db.query(RiskDimension).filter_by(key=key).first()
        if obj:
            return obj
        obj = RiskDimension(key=key, display_name=display_name)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def _get_or_create_level(self, label: str) -> RiskLevel:
        label_lower = label.lower()
        mapping = {
            "düşük": ("low", 1),
            "dusuk": ("low", 1),
            "orta": ("medium", 2),
            "yüksek": ("high", 3),
            "yuksek": ("high", 3),
        }
        key, rank = mapping.get(label_lower, ("medium", 2))

        obj = self.db.query(RiskLevel).filter_by(key=key).first()
        if obj:
            return obj
        obj = RiskLevel(key=key, rank=rank)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj