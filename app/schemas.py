from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: str
    email: str

    class Config:
        from_attributes = True   # lets this be built directly from a SQLAlchemy User object

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    
from typing import Optional
from datetime import datetime

class ServiceCreate(BaseModel):
    name: str
    url: str
    method: str = "GET"
    expected_status: int = 200
    interval_seconds: int = 60
    timeout_seconds: int = 5
    group_id: Optional[str] = None

class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    method: Optional[str] = None
    expected_status: Optional[int] = None
    interval_seconds: Optional[int] = None
    timeout_seconds: Optional[int] = None
    is_active: Optional[bool] = None
    group_id: Optional[str] = None

class ServiceOut(BaseModel):
    id: str
    name: str
    url: str
    method: str
    expected_status: int
    interval_seconds: int
    timeout_seconds: int
    is_active: bool
    status: str
    consecutive_failures: int
    created_at: datetime
    group_id: Optional[str] = None

    class Config:
        from_attributes = True
        
class HealthCheckOut(BaseModel):
    id: str
    timestamp: datetime
    success: bool
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True
        
        
class IncidentOut(BaseModel):
    id: str
    service_id: str
    started_at: datetime
    resolved_at: Optional[datetime] = None
    status: str
    reason: Optional[str] = None
    duration_seconds: Optional[float] = None

    class Config:
        from_attributes = True
        
        
class AlertRuleCreate(BaseModel):
    rule_type: str      # "response_time" | "consecutive_failures" | "uptime"
    threshold: float

class AlertRuleOut(BaseModel):
    id: str
    service_id: str
    rule_type: str
    threshold: float
    is_active: bool

    class Config:
        from_attributes = True

class TriggeredAlertOut(BaseModel):
    service_id: str
    service_name: str
    rule_type: str
    threshold: float
    current_value: float
    message: str
    
class PaginatedHealthChecks(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[HealthCheckOut]
    
class ServiceStatsOut(BaseModel):
    service_id: str
    service_name: str
    uptime_24h: Optional[float] = None
    uptime_7d: Optional[float] = None
    avg_response_time_ms: Optional[float] = None
    min_response_time_ms: Optional[float] = None
    max_response_time_ms: Optional[float] = None
    total_checks: int
    
class GroupCreate(BaseModel):
    name: str

class GroupOut(BaseModel):
    id: str
    name: str
    created_at: datetime

    class Config:
        from_attributes = True

class GroupSummaryOut(BaseModel):
    id: str
    name: str
    total_services: int
    healthy: int
    degraded: int
    down: int
    
class DashboardOut(BaseModel):
    total_services: int
    healthy: int
    degraded: int
    down: int
    active_incidents: int
    avg_response_time_ms: Optional[float] = None
    overall_uptime_24h: Optional[float] = None
    recent_incidents: List[IncidentOut]