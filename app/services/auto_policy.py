import statistics
from datetime import date, datetime, timedelta, time
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.core import FeatureDaily, UserSettings, DailyUsageLog, AppCatalog
from app.models.policy import PolicyRule
from app.services.categorizer import get_or_create_app_entry
from app.services.category_constants import canonicalize_category_key

RISK_CATEGORIES = {"games", "social", "video", "short_video", "short-video", "video_short"}

class AutoPolicyResult:
    def __init__(self):
        self.window_days: int = 7
        self.stage1_daily_limit: int = 0
        self.stage2_daily_limit: int = 0
        self.weekend_relax_pct: int = 0
        self.app_limits: List[dict] = []
        self.bedtime_start: Optional[str] = None
        self.bedtime_end: Optional[str] = None
        self.fallback_used: bool = False
        self.message: Optional[str] = None


def _pick_window(db: Session, user_id: str) -> int:
    today = date.today()
    for days in (30, 21, 14, 7):
        start = today - timedelta(days=days)
        count = db.query(FeatureDaily).filter(FeatureDaily.user_id == user_id, FeatureDaily.date >= start).count()
        if count >= max(4, days // 2):
            return days
    return 0


def _compute_age(birth_date: Optional[date]) -> Optional[int]:
    if birth_date is None:
        return None
    today = date.today()
    years = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        years -= 1
    return max(years, 0)


def _age_group_bounds(birth_date: Optional[date]):
    # returns (min_cap_limit, app_cap, bedtime_start, bedtime_end)
    age = _compute_age(birth_date)
    if age is None:
        return 100, 70, time(21, 30), time(7, 0)
    if age <= 8:
        return 90, 60, time(21, 0), time(7, 0)
    return 105, 75, time(22, 0), time(7, 0)


def _clamp(val, lo, hi):
    return max(lo, min(hi, val))


def _calc_limits(dailies: List[FeatureDaily], min_cap: int) -> tuple[int, int, float, float, float]:
    totals = [float(d.total_minutes or 0) for d in dailies]
    if not totals:
        return min_cap, min_cap, 0, 0, 0
    mu = statistics.mean(totals)
    sigma = statistics.pstdev(totals) if len(totals) > 1 else 0.0
    target = int(round(_clamp(mu - 0.5 * sigma, min_cap, 150)))
    stage1 = int(round(max(target, mu * 0.8))) if mu > 0 else target
    stage1 = min(stage1, 150)
    return stage1, target, mu, sigma, max(totals)


def _weekend_relax(dailies: List[FeatureDaily]) -> int:
    weekdays = [float(d.total_minutes or 0) for d in dailies if not d.weekend]
    weekends = [float(d.total_minutes or 0) for d in dailies if d.weekend]
    if not weekdays or not weekends:
        return 0
    mu_wd = statistics.mean(weekdays)
    mu_we = statistics.mean(weekends)
    if mu_wd <= 0:
        return 0
    ratio = mu_we / mu_wd
    if ratio >= 1.6:
        return 0
    relax = (ratio - 1) if ratio > 1 else 0
    relax_pct = int(round(_clamp(relax, 0, 0.3) * 100))
    return relax_pct


def _aggregate_apps(db: Session, user_id: str, days: int):
    start = date.today() - timedelta(days=days)
    rows = db.query(DailyUsageLog).filter(DailyUsageLog.user_id == user_id, DailyUsageLog.usage_date >= start).all()
    app_totals = {}
    total_minutes = 0.0
    for r in rows:
        minutes = float(r.total_seconds or 0) / 60.0
        if minutes <= 0:
            continue
        total_minutes += minutes
        app_totals.setdefault(r.package_name, 0.0)
        app_totals[r.package_name] += minutes
    return app_totals, total_minutes


def _categorize(db: Session, package: str) -> Optional[str]:
    entry = db.query(AppCatalog).filter_by(package_name=package).first()
    if entry and entry.category and entry.category.key:
        return canonicalize_category_key(entry.category.key)
    # fallback: create/lookup
    entry = get_or_create_app_entry(db, package)
    if entry.category and entry.category.key:
        return canonicalize_category_key(entry.category.key)
    return None


def _generate_auto_policy(db: Session, user_id: str, birth_date: Optional[date], persist: bool) -> AutoPolicyResult:
    result = AutoPolicyResult()

    window = _pick_window(db, user_id)
    if window == 0:
        result.fallback_used = True
        result.window_days = 7
    else:
        result.window_days = window

    dailies = []
    if result.window_days > 0:
        start = date.today() - timedelta(days=result.window_days)
        dailies = db.query(FeatureDaily).filter(FeatureDaily.user_id == user_id, FeatureDaily.date >= start).all()

    min_cap, app_cap, bedtime_start_t, bedtime_end_t = _age_group_bounds(birth_date)
    stage1, stage2, mu, sigma, _ = _calc_limits(dailies, min_cap)

    if not dailies:
        result.fallback_used = True
        stage1 = stage2 = min_cap

    weekend_relax_pct = _weekend_relax(dailies)

    # per-app limits
    app_totals, total_minutes = _aggregate_apps(db, user_id, result.window_days or 7)
    app_limits = []
    if total_minutes > 0:
        for pkg, mins in sorted(app_totals.items(), key=lambda x: x[1], reverse=True):
            share = mins / total_minutes
            if share < 0.1 and mins < 60:
                continue
            cat = _categorize(db, pkg)
            risk = cat in RISK_CATEGORIES
            if share > 0.35 or (risk and share > 0.25):
                limit_val = mins * 0.7
                cap_val = app_cap if risk else app_cap + 15
                limit_val = int(round(min(limit_val, cap_val)))
                limit_val = max(limit_val, 15)
                app_limits.append({
                    "package_name": pkg,
                    "limit_minutes": limit_val,
                    "category": cat,
                    "share": round(share, 3),
                })
            if len(app_limits) >= 4:
                break

    if persist:
        # persist: clear old system_auto rules
        db.query(PolicyRule).filter(PolicyRule.user_id == user_id, PolicyRule.source == "system_auto").delete()

        # stage1 rule (global daily limit via settings)
        settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        if not settings:
            settings = UserSettings(user_id=user_id)
            db.add(settings)
        settings.daily_limit_minutes = stage1
        settings.weekend_relax_pct = weekend_relax_pct
        settings.nightly_start = bedtime_start_t
        settings.nightly_end = bedtime_end_t
        db.flush()

        now = datetime.utcnow()
        # stage2 rule stored as future-effective limit (optional for reference)
        rule_stage2 = PolicyRule(
            user_id=user_id,
            action="limit",
            source="system_auto",
            param_int=stage2,
            active=True,
            effective_at=now + timedelta(days=7),
        )
        db.add(rule_stage2)

        # per-app limit rules
        for item in app_limits:
            db.add(PolicyRule(
                user_id=user_id,
                action="limit",
                source="system_auto",
                target_package=item["package_name"],
                param_int=item["limit_minutes"],
                active=True,
                effective_at=now,
            ))
            # gece block kuralı (kategori riskli ve nightMinutes varsa? hızlı heuristik: riskli ise block window)
            if item.get("category") in RISK_CATEGORIES:
                db.add(PolicyRule(
                    user_id=user_id,
                    action="block",
                    source="system_auto",
                    target_package=item["package_name"],
                    param_int=0,
                    active=True,
                    effective_at=now,
                    local_start=bedtime_start_t,
                    local_end=bedtime_end_t,
                    dow_mask=127,
                ))

        # bedtime block (global)
        db.add(PolicyRule(
            user_id=user_id,
            action="block",
            source="system_auto",
            target_package=None,
            param_int=0,
            active=True,
            effective_at=now,
            local_start=bedtime_start_t,
            local_end=bedtime_end_t,
            dow_mask=127,
        ))

        db.commit()

    result.stage1_daily_limit = stage1
    result.stage2_daily_limit = stage2
    result.weekend_relax_pct = weekend_relax_pct
    result.app_limits = app_limits
    result.bedtime_start = bedtime_start_t.strftime("%H:%M") if bedtime_start_t else None
    result.bedtime_end = bedtime_end_t.strftime("%H:%M") if bedtime_end_t else None
    if result.fallback_used:
        result.message = "Yetersiz veri; yaş bazlı varsayılanlar uygulandı."
    return result


def preview_auto_policy(db: Session, user_id: str, birth_date: Optional[date]) -> AutoPolicyResult:
    return _generate_auto_policy(db, user_id, birth_date, persist=False)


def apply_auto_policy(db: Session, user_id: str, birth_date: Optional[date]) -> AutoPolicyResult:
    return _generate_auto_policy(db, user_id, birth_date, persist=True)
