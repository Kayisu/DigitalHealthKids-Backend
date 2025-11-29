# app/models/core.py
from sqlalchemy import (
    Column, String, Text, DateTime, ForeignKey,
    Boolean, Integer, Time
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db import Base
import uuid
from datetime import datetime


class User(Base):
    __tablename__ = "users"

    # DB tarafında şu kolonların olduğunu varsayıyoruz:
    # id (uuid), full_name (text), email (text), created_at (timestamp)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(Text)
    email = Column(Text, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # role, parent_id ve parent relationship KALDIRILDI
    # çünkü artık users tablosunda bu kolonlar yok ve SELECT sırasında hata veriyordu.


class Device(Base):
    __tablename__ = "device"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    platform = Column(String)       # "android" vs
    model = Column(Text)
    os_version = Column(Text)
    enrolled_at = Column(DateTime)
    revoked_at = Column(DateTime)

    user = relationship("User", backref="devices")


class AppSession(Base):
    __tablename__ = "app_session"

    id = Column(Integer, primary_key=True, autoincrement=True)
    child_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    device_id = Column(UUID(as_uuid=True), ForeignKey("device.id"), nullable=False)
    package_name = Column(Text, nullable=False)
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    source = Column(String)
    payload = Column(JSONB)

    child = relationship("User", backref="sessions")
    device = relationship("Device", backref="sessions")
