# app/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# örnek: postgresql://user:password@localhost:5432/digital_health
DATABASE_URL = "postgresql+psycopg://postgres:finalspace@localhost:5432/childstats"

engine = create_engine(
    DATABASE_URL,
    echo=False,          # True yaparsan tüm SQL'leri görürsün
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
