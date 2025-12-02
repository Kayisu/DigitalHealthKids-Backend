# app/models/policy.py
from sqlalchemy import (
    Column, String, Text, DateTime, Time,
    Integer, Boolean, ForeignKey, DECIMAL, Date
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db import Base
from datetime import datetime

class PolicyRule(Base):
    __tablename__ = "policy_rule"
    id = Column(Integer, primary_key=True, autoincrement=True)
    # child_id -> user_id
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    source = Column(String) 
    target_category_id = Column(Integer)
    target_package = Column(Text)
    action = Column(String)  # "block", "limit"
    param_int = Column(Integer)
    local_start = Column(Time)
    local_end = Column(Time)
    active = Column(Boolean, default=True)
    effective_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)

class PolicyEffect(Base):
    __tablename__ = "policy_effect"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    policy_rule_id = Column(Integer, ForeignKey("policy_rule.id"), nullable=False)
    metric = Column(String)
    effect = Column(DECIMAL(6,3))
    as_of_date = Column(Date)
    model_key = Column(String)