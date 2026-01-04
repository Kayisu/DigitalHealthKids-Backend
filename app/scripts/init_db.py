import os
from pathlib import Path
from sqlalchemy import text

# Proje kökünü path'e ekle
CURRENT = Path(__file__).resolve()
PROJECT_ROOT = CURRENT.parents[2]
if str(PROJECT_ROOT) not in os.sys.path:
    os.sys.path.append(str(PROJECT_ROOT))

from app.db import engine

SCHEMA_PATH = PROJECT_ROOT / "db" / "create.sql"


def apply_schema():
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_PATH}")

    sql = SCHEMA_PATH.read_text(encoding="utf-8")

    # Çoklu komut içeren dosya için tek seferde çalıştırıyoruz
    with engine.begin() as conn:
        conn.execute(text(sql))
    print("✅ Schema applied successfully.")


if __name__ == "__main__":
    apply_schema()
