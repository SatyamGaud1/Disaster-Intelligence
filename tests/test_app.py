"""
Integration tests for Flask application routes, API responses, and error handlers.
"""

import tempfile
from pathlib import Path
import pytest
from app import create_app
from app.config import Config
from app.database import init_db


@pytest.fixture
def client():
    """Configures a fresh Flask test client with an isolated temporary SQLite database."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_db_path = Path(tmp_dir) / "test_app.db"

        class TestSettings(Config):
            TESTING = True
            DATABASE_PATH = test_db_path

        app = create_app(TestSettings)

        with app.app_context():
            init_db()

        with app.test_client() as client:
            yield client


def test_dashboard_home_page(client):
    """Test that the primary dashboard HTML page renders successfully."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Disaster Intel" in html
    assert "Multi-Hazard" in html
    assert "disaster-map" in html


def test_api_health_endpoint(client):
    """Test that the /api/health endpoint confirms backend and database health."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert data["database"]["status"] == "healthy"
    assert "version" in data


def test_api_sources_endpoint(client):
    """Test that default satellite sources are returned."""
    response = client.get("/api/sources")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert data["count"] >= 4
    source_names = [s["source_name"] for s in data["sources"]]
    assert "NASA_FIRMS" in source_names
    assert "SENTINEL_1" in source_names
    assert "SENTINEL_2" in source_names
    assert "NASA_GPM" in source_names


def test_api_stats_endpoint(client):
    """Test system metrics telemetry endpoint."""
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "metrics" in data
    assert "satellite_constellations" in data["metrics"]
    assert data["metrics"]["satellite_constellations"] == 4


def test_api_incidents_endpoint(client):
    """Test that sample/live incidents can be fetched."""
    response = client.get("/api/incidents")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert isinstance(data["incidents"], list)
    assert data["count"] > 0


def test_cyclone_module_page(client):
    """Test that the dedicated Cyclone module HTML page renders successfully."""
    response = client.get("/cyclone")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Tropical Cyclone" in html
    assert "cyclone-risk-form" in html
    assert "cyclone-select" in html


def test_404_error_handler(client):
    """Test that non-existent API endpoints return a structured 404 response."""
    response = client.get("/api/non-existent-endpoint")
    assert response.status_code == 404
    data = response.get_json()
    assert data["status"] == "error"
    assert data["code"] == 404

