from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, HttpUrl, Field, ConfigDict


# --- Request Schema (What the client sends to POST /api/monitors) ---
class MonitorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, examples=["GitHub API"])
    url: HttpUrl = Field(..., examples=["https://api.github.com"])
    interval_seconds: int = Field(default=60, ge=10, le=3600)


# --- Response Schema for a single PingLog ---
class PingLogResponse(BaseModel):
    id: int
    status_code: Optional[int]
    latency_ms: Optional[float]
    is_up: bool
    error_message: Optional[str]
    checked_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Response Schema for a Monitor ---
class MonitorResponse(BaseModel):
    id: int
    name: str
    url: str
    interval_seconds: int
    is_active: bool
    consecutive_failures: int
    current_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Response Schema for Monitor History + Calculated Uptime ---
class MonitorHistoryResponse(BaseModel):
    monitor: MonitorResponse
    uptime_percentage: float
    total_checks: int
    recent_logs: List[PingLogResponse]