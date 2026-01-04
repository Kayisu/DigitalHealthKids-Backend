# app/db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# DATABASE_URL artık ortam değişkeninden okunuyor; yoksa eski varsayılan kalır.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:finalspace@localhost:5432/childstats",
)

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL tanımlı değil; .env veya ortam değişkenini ayarlayın.")

SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() in {"1", "true", "yes", "on"}

engine = create_engine(
    DATABASE_URL,
    echo=SQL_ECHO,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


# FastAPI dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
