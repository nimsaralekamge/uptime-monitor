# API Uptime & Latency Monitoring Service

![CI/CD Pipeline](https://github.com/nimsaralekamge/uptime-monitor/actions/workflows/ci.yml/badge.svg)

A containerized backend and observability service that continuously monitors registered HTTP/API endpoints, tracks response latency and historical uptime in PostgreSQL, triggers 3-strike Discord webhook alerts on downtime, and exposes real-time telemetry to Prometheus and Grafana.

---

## Architecture

```text
                    +-------------------+
                    |   Client / User   |
                    +---------+---------+
                              | REST API (:8000)
                              v
+-------------------------------------------------------------+
|                  FastAPI Application (:8000)                |
|  - CRUD Endpoints (/api/monitors)                           |
|  - Async Health Worker (APScheduler + httpx.AsyncClient)    |
|  - Telemetry (/metrics) & Readiness (/health)               |
+------+----------------------+-----------------------+-------+
       | SQLAlchemy           | 3-Strike Alert        | Scrape (:9090)
       v                      v                       v
+--------------+      +---------------+      +----------------+
| PostgreSQL 16|      |Discord Webhook|      |   Prometheus   |
| (Persistent) |      | (DOWN / UP)   |      +--------+-------+
+--------------+      +---------------+               |
                                                      v
                                             +----------------+
                                             |    Grafana     |
                                             | Dashboard:3000 |
                                             +----------------+
```

---

## Key Engineering Highlights

* **Concurrent Non-Blocking Health Checks:** Uses `asyncio.gather` with a shared `httpx.AsyncClient` connection pool to ping all active endpoints in parallel and measure high-precision latency (`time.perf_counter()`).
* **Alert Fatigue Prevention (3-Strike State Machine):** Triggers a Discord alert only when an endpoint fails 3 consecutive checks (`consecutive_failures == 3`), suppresses duplicate alerts during prolonged outages, and sends a recovery alert once the service returns `UP`.
* **Optimized PostgreSQL Indexing:** Uses a composite index on `(monitor_id, checked_at)` so historical log queries stay fast ($O(\log N)$) as ping logs scale, alongside database-side `COUNT(*)` uptime aggregations.
* **Production Multi-Stage Docker Build:** Separates dependency compilation (`builder`) from a lean runtime image (`runtime`) executing under a dedicated non-root user (`appuser`).
* **Full Observability Stack:** Auto-instruments HTTP RED metrics (Rate, Errors, Duration) via `/metrics`, scraped every 5 seconds by Prometheus and visualized in Grafana.
* **Automated CI/CD Pipeline:** GitHub Actions runs isolated `pytest` integration tests on every push/PR and builds + pushes tagged images (`latest` and `github.sha`) to GitHub Container Registry (`ghcr.io`).

---

## Tech Stack

* **Backend:** Python 3.12, FastAPI, Uvicorn, SQLAlchemy, Pydantic v2, APScheduler, HTTPX
* **Database:** PostgreSQL 16 (SQLite in-memory via Dependency Injection for CI tests)
* **DevOps & Observability:** Docker, Docker Compose, GitHub Actions, GHCR, Prometheus, Grafana

---

## Quick Start (Docker Compose)

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/nimsaralekamge/uptime-monitor.git](https://github.com/nimsaralekamge/uptime-monitor.git)
   cd uptime-monitor
   ```

2. **Configure environment variables (optional Discord webhook):**
   ```bash
   cp .env.example .env
   ```

3. **Start the entire stack (API, PostgreSQL, Prometheus, Grafana):**
   ```bash
   docker compose up --build -d
   ```