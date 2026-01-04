from sqlalchemy import Column, Date, Integer, SmallInteger, String, ForeignKey, DECIMAL
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db import Base


class RiskDimension(Base):
    __tablename__ = "risk_dimension"

    id = Column(SmallInteger, primary_key=True, autoincrement=True)
    key = Column(String, unique=True, nullable=False)
    display_name = Column(String)


class RiskLevel(Base):
    __tablename__ = "risk_level"

    id = Column(SmallInteger, primary_key=True, autoincrement=True)
    key = Column(String, unique=True, nullable=False)
    rank = Column(SmallInteger, nullable=False)


class RiskAssessment(Base):
    __tablename__ = "risk_assessment"

    user_id = Column(UUID(as_uuid=True), primary_key=True)
    as_of_date = Column(Date, primary_key=True)
    dimension_id = Column(SmallInteger, ForeignKey("risk_dimension.id"), primary_key=True)
    level_id = Column(SmallInteger, ForeignKey("risk_level.id"), nullable=False)
    prob = Column(DECIMAL(4, 3))
    model_key = Column(String)
    features = Column(JSONB)

    dimension = relationship("RiskDimension")
    level = relationship("RiskLevel")
