import asyncio
import time
import logging
import httpx
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Monitor, PingLog
from app.config import settings

logger = logging.getLogger(__name__)

FAILURE_THRESHOLD = 3
REQUEST_TIMEOUT_SECONDS = 5.0


async def send_discord_alert(message: str) -> None:
    """Sends a notification to Discord if DISCORD_WEBHOOK_URL is configured."""
    if not settings.discord_webhook_url:
        logger.info("Alert (Discord webhook not set): %s", message)
        return

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(settings.discord_webhook_url, json={"content": message})
    except Exception as exc:
        logger.error("Failed to send Discord alert: %s", exc)


async def ping_single_url(client: httpx.AsyncClient, url: str) -> dict:
    """Pings one URL and returns status code, latency in ms, and up/down boolean."""
    start = time.perf_counter()
    try:
        response = await client.get(url, follow_redirects=True)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        is_up = 200 <= response.status_code < 400
        return {
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "is_up": is_up,
            "error_message": None if is_up else f"HTTP {response.status_code}",
        }
    except httpx.TimeoutException:
        return {
            "status_code": None,
            "latency_ms": None,
            "is_up": False,
            "error_message": f"Timeout after {REQUEST_TIMEOUT_SECONDS}s",
        }
    except httpx.RequestError as exc:
        return {
            "status_code": None,
            "latency_ms": None,
            "is_up": False,
            "error_message": str(exc),
        }


async def run_health_checks() -> None:
    """Fetches all active monitors, pings them concurrently, and updates DB state."""
    db: Session = SessionLocal()
    try:
        monitors = db.query(Monitor).filter(Monitor.is_active.is_(True)).all()
        if not monitors:
            return

        # Ping all URLs concurrently in parallel using one shared HTTP client
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            tasks = [ping_single_url(client, m.url) for m in monitors]
            results = await asyncio.gather(*tasks)

        for monitor, result in zip(monitors, results):
            # 1. Record the individual ping log
            log_entry = PingLog(
                monitor_id=monitor.id,
                status_code=result["status_code"],
                latency_ms=result["latency_ms"],
                is_up=result["is_up"],
                error_message=result["error_message"],
            )
            db.add(log_entry)

            # 2. State machine for 3-strike alerting & recovery
            if result["is_up"]:
                if monitor.current_status == "DOWN":
                    await send_discord_alert(
                        f"✅ **RECOVERED:** `{monitor.name}` ({monitor.url}) is back UP ({result['latency_ms']} ms)."
                    )
                monitor.consecutive_failures = 0
                monitor.current_status = "UP"
            else:
                monitor.consecutive_failures += 1
                if monitor.consecutive_failures == FAILURE_THRESHOLD:
                    monitor.current_status = "DOWN"
                    await send_discord_alert(
                        f"🚨 **DOWN ALERT:** `{monitor.name}` ({monitor.url}) failed {FAILURE_THRESHOLD} times in a row. Error: `{result['error_message']}`"
                    )
                elif monitor.consecutive_failures > FAILURE_THRESHOLD:
                    monitor.current_status = "DOWN"

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Error during health check cycle: %s", exc)
    finally:
        db.close()