# app/models/policy.py
from sqlalchemy import (
    Column, String, Text, DateTime, Time,
    Integer, Boolean, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID
from app.db import Base
from datetime import datetime


class PolicyRule(Base):
    __tablename__ = "policy_rule"

    id = Column(Integer, primary_key=True, autoincrement=True)
    child_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    source = Column(String)  # "system" / "parent" vs
    target_category_id = Column(Integer)  # FK app_category.id (şimdilik boş bırakıyoruz)
    target_package = Column(Text)
    action = Column(String)  # "block", "limit", "warn"
    param_int = Column(Integer)
    action_mask = Column(Integer)
    local_start = Column(Time)
    local_end = Column(Time)
    active = Column(Boolean, default=True)
    effective_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
