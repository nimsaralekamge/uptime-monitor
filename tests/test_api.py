import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db

# In-memory SQLite database isolated strictly for testing
SQLALCHEMY_TEST_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Swap the production PostgreSQL dependency for our isolated test DB
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_create_and_list_monitors():
    # 1. Create a monitor
    payload = {
        "name": "GitHub API",
        "url": "https://api.github.com",
        "interval_seconds": 30,
    }
    create_res = client.post("/api/monitors", json=payload)
    assert create_res.status_code == 201
    data = create_res.json()
    assert data["name"] == "GitHub API"
    assert data["current_status"] == "PENDING"
    assert data["consecutive_failures"] == 0

    # 2. List monitors
    list_res = client.get("/api/monitors")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1


def test_prevent_duplicate_url():
    payload = {"name": "Example", "url": "https://example.com"}
    first = client.post("/api/monitors", json=payload)
    assert first.status_code == 201

    duplicate = client.post("/api/monitors", json=payload)
    assert duplicate.status_code == 409


def test_reject_invalid_url():
    payload = {"name": "Broken", "url": "not-a-valid-url"}
    response = client.post("/api/monitors", json=payload)
    assert response.status_code == 422


def test_get_history_and_delete_monitor():
    create_res = client.post(
        "/api/monitors",
        json={"name": "Google", "url": "https://www.google.com"},
    )
    monitor_id = create_res.json()["id"]

    # Check history endpoint
    history_res = client.get(f"/api/monitors/{monitor_id}/history")
    assert history_res.status_code == 200
    history_data = history_res.json()
    assert history_data["uptime_percentage"] == 100.0
    assert history_data["total_checks"] == 0

    # Delete monitor
    del_res = client.delete(f"/api/monitors/{monitor_id}")
    assert del_res.status_code == 204

    # Confirm 404 after deletion
    missing_res = client.get(f"/api/monitors/{monitor_id}/history")
    assert missing_res.status_code == 404