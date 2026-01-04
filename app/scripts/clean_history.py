import os
import sys
import uuid

from datetime import datetime

current_file_path = os.path.abspath(__file__)
scripts_dir = os.path.dirname(current_file_path)
app_dir = os.path.dirname(scripts_dir)
project_root = os.path.dirname(app_dir)

if project_root not in sys.path:
    sys.path.append(project_root)

from app.db import SessionLocal
from app.models.core import DailyUsageLog, AppSession, FeatureDaily
from app.models.risk import RiskAssessment
from app.models.core import User, Device

# Hedef kullanıcı/cihaz listesi (generate_history.py ile uyumlu)
PERSONAS = [
    ("30210d15-0821-41c5-bf59-510ac5b72f7b", "36d61160-7f5a-412a-b8c4-8138d25b49d7"),
    ("f6a7d251-1250-4df5-ab8b-04c684157292", "7c327f1e-4bf1-4166-862c-47d3afd27b78"),
    ("0f8c537d-e2b1-4763-bac6-ccbf09dd87d9", "278d0184-db51-438b-b21f-42a4eb9f044d"),
    ("27ca606a-e236-48ff-addf-49943fe00eec", "98cc7ea5-f2f0-4d32-9ad4-a16d034bcf8b"),
]

# Kullanıcı/cihazları da silmek isterseniz True yapın
DELETE_USERS_AND_DEVICES = False


def clean_history():
    db = SessionLocal()
    try:
        print("🧹 Temizlik başlıyor...")
        for user_id_str, device_id_str in PERSONAS:
            try:
                user_uuid = uuid.UUID(user_id_str)
                device_uuid = uuid.UUID(device_id_str)
            except ValueError:
                print(f"❌ UUID formatı hatalı: {user_id_str} / {device_id_str}")
                continue

            print(f"-- {user_uuid} temizleniyor")

            deleted_log = db.query(DailyUsageLog).filter(DailyUsageLog.user_id == user_uuid).delete()
            print(f"   ➜ DailyUsageLog: {deleted_log}")

            deleted_session = db.query(AppSession).filter(AppSession.user_id == user_uuid).delete()
            print(f"   ➜ AppSession: {deleted_session}")

            deleted_feat = db.query(FeatureDaily).filter(FeatureDaily.user_id == user_uuid).delete()
            print(f"   ➜ FeatureDaily: {deleted_feat}")

            deleted_risk = db.query(RiskAssessment).filter(RiskAssessment.user_id == user_uuid).delete()
            print(f"   ➜ RiskAssessment: {deleted_risk}")

            if DELETE_USERS_AND_DEVICES:
                db.query(Device).filter(Device.id == device_uuid).delete()
                db.query(User).filter(User.id == user_uuid).delete()
                print("   ➜ User & Device silindi")

        db.commit()
        print("✅ Temizlik tamamlandı.")
    except Exception as e:
        db.rollback()
        print(f"❌ Temizlik hata verdi: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    clean_history()
