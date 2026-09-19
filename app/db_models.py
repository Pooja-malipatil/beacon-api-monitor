import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

def gen_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    services = relationship("Service", back_populates="owner", cascade="all, delete-orphan")
    groups = relationship("ServiceGroup", back_populates="owner", cascade="all, delete-orphan")


class ServiceGroup(Base):
    __tablename__ = "service_groups"
    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="groups")
    services = relationship("Service", back_populates="group")


class Service(Base):
    __tablename__ = "services"
    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    method = Column(String, default="GET")
    expected_status = Column(Integer, default=200)
    interval_seconds = Column(Integer, default=60)
    timeout_seconds = Column(Integer, default=5)
    is_active = Column(Boolean, default=True)
    status = Column(String, default="pending")       # healthy / degraded / down / pending
    consecutive_failures = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    group_id = Column(String, ForeignKey("service_groups.id"), nullable=True)

    owner = relationship("User", back_populates="services")
    group = relationship("ServiceGroup", back_populates="services")
    health_checks = relationship("HealthCheck", back_populates="service", cascade="all, delete-orphan")
    incidents = relationship("Incident", back_populates="service", cascade="all, delete-orphan")
    alert_rules = relationship("AlertRule", back_populates="service", cascade="all, delete-orphan")


class HealthCheck(Base):
    __tablename__ = "health_checks"
    id = Column(String, primary_key=True, default=gen_uuid)
    service_id = Column(String, ForeignKey("services.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    success = Column(Boolean, nullable=False)
    status_code = Column(Integer, nullable=True)
    response_time_ms = Column(Float, nullable=True)
    error_message = Column(String, nullable=True)

    service = relationship("Service", back_populates="health_checks")


class Incident(Base):
    __tablename__ = "incidents"
    id = Column(String, primary_key=True, default=gen_uuid)
    service_id = Column(String, ForeignKey("services.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    status = Column(String, default="open")          # open / resolved
    reason = Column(String, nullable=True)
    
    @property
    def duration_seconds(self):
            if self.resolved_at:
                return (self.resolved_at - self.started_at).total_seconds()
            return None

    service = relationship("Service", back_populates="incidents")


class AlertRule(Base):
    __tablename__ = "alert_rules"
    id = Column(String, primary_key=True, default=gen_uuid)
    service_id = Column(String, ForeignKey("services.id"), nullable=False)
    rule_type = Column(String, nullable=False)        # response_time / consecutive_failures / uptime
    threshold = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)

    service = relationship("Service", back_populates="alert_rules")
    
    
    