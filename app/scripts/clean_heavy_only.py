import os
import sys
import uuid

current_file_path = os.path.abspath(__file__)
scripts_dir = os.path.dirname(current_file_path)
app_dir = os.path.dirname(scripts_dir)
project_root = os.path.dirname(app_dir)

if project_root not in sys.path:
    sys.path.append(project_root)

from app.db import SessionLocal
from app.models.core import DailyUsageLog, AppSession, FeatureDaily
from app.models.risk import RiskAssessment

HEAVY_USER_ID = uuid.UUID("30210d15-0821-41c5-bf59-510ac5b72f7b")


def clean_heavy_only():
    db = SessionLocal()
    try:
        print("🧹 Heavy kullanıcı verisi siliniyor...")

        deleted_log = db.query(DailyUsageLog).filter(DailyUsageLog.user_id == HEAVY_USER_ID).delete()
        deleted_session = db.query(AppSession).filter(AppSession.user_id == HEAVY_USER_ID).delete()
        deleted_feat = db.query(FeatureDaily).filter(FeatureDaily.user_id == HEAVY_USER_ID).delete()
        deleted_risk = db.query(RiskAssessment).filter(RiskAssessment.user_id == HEAVY_USER_ID).delete()

        db.commit()
        print(f"✓ DailyUsageLog: {deleted_log}, AppSession: {deleted_session}, FeatureDaily: {deleted_feat}, RiskAssessment: {deleted_risk}")
        print("✅ Temizlik tamamlandı (kullanıcı/cihaz silinmedi).")
    except Exception as e:
        db.rollback()
        print(f"❌ Hata: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    clean_heavy_only()
