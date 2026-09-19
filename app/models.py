from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class EndpointCreate(BaseModel):
    name: str
    url: str
    method: str = "GET"
    interval: int = 60  # seconds

class CheckResult(BaseModel):
    status_code: Optional[int]
    latency_ms: Optional[float]
    checked_at: datetime
    message: str

class Endpoint(EndpointCreate):
    id: str
    status: str = "pending"  # up / down / pending
    last_check: Optional[CheckResult] = None
    history: list[CheckResult] = []
    uptime_pct: float = 0.0