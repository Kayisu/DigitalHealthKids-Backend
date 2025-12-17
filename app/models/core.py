# app/models/core.py
from sqlalchemy import (
    Column, String, Text, DateTime, ForeignKey,
    Integer, Boolean, Date, DECIMAL, SmallInteger, Time
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db import Base
import uuid
from datetime import datetime

# 1. TEMEL TABLOLAR
class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(Text)
    email = Column(Text, unique=True)
    birth_year = Column(Integer) # <-- AI için yaş verisi
    created_at = Column(DateTime, default=datetime.utcnow)

class Device(Base):
    __tablename__ = "device"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    platform = Column(String)
    model = Column(Text)
    os_version = Column(Text)
    enrolled_at = Column(DateTime)
    revoked_at = Column(DateTime)
    user = relationship("User", backref="devices")

class AppSession(Base):
    __tablename__ = "app_session"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    device_id = Column(UUID(as_uuid=True), ForeignKey("device.id"), nullable=False)
    package_name = Column(Text, nullable=False)
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    source = Column(String)
    payload = Column(JSONB)
    user = relationship("User", backref="sessions")

class UserSettings(Base):
    __tablename__ = "user_settings"
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    timezone = Column(String)
    daily_limit_minutes = Column(Integer, default=120) 
    nightly_start = Column(Time)
    nightly_end = Column(Time)
    min_night_minutes = Column(Integer)
    weekend_relax_pct = Column(Integer)
    min_session_seconds = Column(Integer)
    session_app_seconds = Column(Integer)
    user = relationship("User", backref="settings")

class AppCategory(Base):
    __tablename__ = "app_category"
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(Text, unique=True, nullable=False)
    display_name = Column(Text, nullable=False)

class AppCatalog(Base):
    __tablename__ = "app_catalog"
    package_name = Column(Text, primary_key=True)
    app_name = Column(Text, nullable=False)
    category_id = Column(Integer, ForeignKey("app_category.id"))
    category = relationship("AppCategory", backref="apps")
class DailyAppUsageView(Base):
    __tablename__ = "view_daily_app_usage"
    user_id = Column(UUID(as_uuid=True), primary_key=True)
    usage_date = Column(Date, primary_key=True)
    package_name = Column(Text, primary_key=True)
    total_minutes = Column(Integer)
    session_count = Column(Integer)

# 2. AI & ANALYTICS TABLOLARI (Refactor Edilmiş Hali)
class FeatureDaily(Base):
    __tablename__ = "feature_daily"
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    date = Column(Date, primary_key=True)
    total_minutes = Column(Integer, nullable=False, default=0)
    night_minutes = Column(Integer, default=0) # Gece ihlal süresi
    gaming_ratio = Column(DECIMAL(4,2), default=0.0)
    social_ratio = Column(DECIMAL(4,2), default=0.0)
    session_count = Column(Integer, default=0)
    weekday = Column(SmallInteger) # 0=Pzt, 6=Paz
    weekend = Column(Boolean)
    is_holiday = Column(Boolean, default=False)

class WeeklyForecast(Base):
    __tablename__ = "weekly_forecast"
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    as_of_date = Column(Date, primary_key=True)
    horizon_week = Column(SmallInteger, primary_key=True)
    scenario = Column(String, primary_key=True)
    target = Column(String)
    yhat_lo = Column(Integer)
    yhat_hi = Column(Integer)
    model_key = Column(String)
class DailyUsageLog(Base):
    __tablename__ = "daily_usage_log"
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    device_id = Column(UUID(as_uuid=True), ForeignKey("device.id"), primary_key=True) 
    usage_date = Column(Date, primary_key=True)
    package_name = Column(Text, primary_key=True)
    app_name = Column(Text)
    total_seconds = Column(Integer)
    updated_at = Column(DateTime, default=datetime.utcnow)
