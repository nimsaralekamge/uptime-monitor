from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from prometheus_fastapi_instrumentator import Instrumentator

from app.database import engine, Base, get_db
from app.models import Monitor, PingLog
from app.schemas import MonitorCreate, MonitorResponse, MonitorHistoryResponse
from app.worker import run_health_checks

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    Base.metadata.create_all(bind=engine)
    scheduler.add_job(
        run_health_checks,
        trigger="interval",
        seconds=15,
        id="health_check_job",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    yield
    # --- Shutdown ---
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="API Uptime & Latency Monitoring Service",
    version="1.0.0",
    lifespan=lifespan,
)

# Exposes /metrics automatically for Prometheus
Instrumentator().instrument(app).expose(app)


@app.get("/health", tags=["Operations"])
def health_check():
    return {"status": "healthy"}


@app.post(
    "/api/monitors",
    response_model=MonitorResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Monitors"],
)
def create_monitor(payload: MonitorCreate, db: Session = Depends(get_db)):
    url_str = str(payload.url)
    existing = db.query(Monitor).filter(Monitor.url == url_str).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This URL is already registered.",
        )

    monitor = Monitor(
        name=payload.name,
        url=url_str,
        interval_seconds=payload.interval_seconds,
    )
    db.add(monitor)
    db.commit()
    db.refresh(monitor)
    return monitor


@app.get("/api/monitors", response_model=List[MonitorResponse], tags=["Monitors"])
def list_monitors(db: Session = Depends(get_db)):
    return db.query(Monitor).order_by(Monitor.id.asc()).all()


@app.get(
    "/api/monitors/{monitor_id}/history",
    response_model=MonitorHistoryResponse,
    tags=["Monitors"],
)
def get_monitor_history(monitor_id: int, db: Session = Depends(get_db)):
    monitor = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")

    total_checks = (
        db.query(func.count(PingLog.id))
        .filter(PingLog.monitor_id == monitor_id)
        .scalar()
        or 0
    )
    successful_checks = (
        db.query(func.count(PingLog.id))
        .filter(PingLog.monitor_id == monitor_id, PingLog.is_up.is_(True))
        .scalar()
        or 0
    )

    uptime_percentage = (
        round((successful_checks / total_checks) * 100, 2) if total_checks > 0 else 100.0
    )

    recent_logs = (
        db.query(PingLog)
        .filter(PingLog.monitor_id == monitor_id)
        .order_by(PingLog.checked_at.desc())
        .limit(50)
        .all()
    )

    return MonitorHistoryResponse(
        monitor=monitor,
        uptime_percentage=uptime_percentage,
        total_checks=total_checks,
        recent_logs=recent_logs,
    )


@app.delete(
    "/api/monitors/{monitor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Monitors"],
)
def delete_monitor(monitor_id: int, db: Session = Depends(get_db)):
    monitor = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")

    db.delete(monitor)
    db.commit()
    return None