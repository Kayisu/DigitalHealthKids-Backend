import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict
import uuid

current_file_path = os.path.abspath(__file__)
scripts_dir = os.path.dirname(current_file_path)
app_dir = os.path.dirname(scripts_dir)
project_root = os.path.dirname(app_dir)

if project_root not in sys.path:
    sys.path.append(project_root)

from app.db import SessionLocal
from app.models.core import AppSession, DailyUsageLog
from app.services.analytics import calculate_daily_features

# Heavy persona IDs (from generate_history.py)
HEAVY_USER_ID = uuid.UUID("30210d15-0821-41c5-bf59-510ac5b72f7b")


def adjust_sunday_usage():
    db = SessionLocal()
    try:
        print("🎯 Heavy kullanıcı pazar günleri yarıya indiriliyor...")

        modified_dates = set()
        sunday_sessions = (
            db.query(AppSession)
            .filter(AppSession.user_id == HEAVY_USER_ID)
            .all()
        )

        sunday_totals = defaultdict(int)
        session_touched = 0
        for sess in sunday_sessions:
            if sess.started_at.weekday() != 6:  # 6: Sunday
                continue
            duration = (sess.ended_at - sess.started_at).total_seconds()
            if duration <= 0:
                continue
            new_duration = max(int(duration / 2), 60)  # en az 1 dk kalsın
            sess.ended_at = sess.started_at + timedelta(seconds=new_duration)
            session_touched += 1
            usage_date = sess.started_at.date()
            sunday_totals[(usage_date, sess.package_name)] += new_duration
            modified_dates.add(usage_date)

        # DailyUsageLog totals should match adjusted sessions (not half twice)
        daily_touched = 0
        for (usage_date, pkg), total_sec in sunday_totals.items():
            log = (
                db.query(DailyUsageLog)
                .filter(
                    DailyUsageLog.user_id == HEAVY_USER_ID,
                    DailyUsageLog.usage_date == usage_date,
                    DailyUsageLog.package_name == pkg,
                )
                .first()
            )
            if log:
                log.total_seconds = int(total_sec)
                log.updated_at = datetime.utcnow()
                daily_touched += 1

        db.commit()
        print(f"✓ {session_touched} session, {daily_touched} günlük kayıt yarıya indirildi.")

        # FeatureDaily yeniden hesapla
        for day in sorted(modified_dates):
            calculate_daily_features(str(HEAVY_USER_ID), day, db)
        db.commit()
        print(f"✓ {len(modified_dates)} gün için FeatureDaily güncellendi.")

    except Exception as e:
        db.rollback()
        print(f"❌ Hata: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    adjust_sunday_usage()
