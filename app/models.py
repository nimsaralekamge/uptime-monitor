from datetime import datetime, timezone
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database import Base


class Monitor(Base):
    __tablename__ = "monitors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    url = Column(String, nullable=False, unique=True)
    interval_seconds = Column(Integer, nullable=False, default=60)
    is_active = Column(Boolean, nullable=False, default=True)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    current_status = Column(String(10), nullable=False, default="PENDING")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # One-to-Many relationship: deleting a Monitor deletes all its PingLogs
    logs = relationship("PingLog", back_populates="monitor", cascade="all, delete-orphan")


class PingLog(Base):
    __tablename__ = "ping_logs"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    monitor_id = Column(Integer, ForeignKey("monitors.id", ondelete="CASCADE"), nullable=False)
    status_code = Column(Integer, nullable=True)  # NULL if DNS failure or timeout
    latency_ms = Column(Float, nullable=True)
    is_up = Column(Boolean, nullable=False)
    error_message = Column(String, nullable=True)
    checked_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    monitor = relationship("Monitor", back_populates="logs")

    __table_args__ = (
        Index("idx_ping_logs_monitor_time", "monitor_id", "checked_at"),
    )