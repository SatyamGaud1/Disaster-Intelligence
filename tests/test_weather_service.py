"""
Unit and integration tests for Free Weather Service & Open-Meteo Integration.
Verifies preset retrieval, geographic distance calculations, live meteorological retrieval,
offline station fallback, and simulator input mappings.
"""

import pytest
from app import create_app
from app.config import Config
from app.database import init_db
from app.services.weather_service import (
    get_weather_presets,
    get_live_weather,
    find_closest_station,
    haversine_distance
)


@pytest.fixture
def client():
    class TestConfig(Config):
        TESTING = True

    app = create_app(TestConfig)
    with app.app_context():
        init_db()
        with app.test_client() as c:
            yield c


def test_weather_presets_list():
    presets = get_weather_presets()
    assert len(presets) >= 5
    ids = [p["id"] for p in presets]
    assert "dwarka_gujarat" in ids
    assert "sundarbans_wb" in ids
    assert "puri_odisha" in ids


def test_haversine_distance_computation():
    # Distance between Dwarka and Puri
    dist = haversine_distance(22.24, 68.96, 19.81, 85.83)
    assert 1700.0 < dist < 1900.0


def test_find_closest_station():
    station, dist = find_closest_station(22.25, 68.95)
    assert station["id"] == "dwarka_gujarat"
    assert dist < 10.0


def test_get_live_weather_mappings():
    res = get_live_weather(22.24, 68.96)
    assert res["status"] == "success"
    assert "current_weather" in res
    assert "simulator_inputs" in res

    sim = res["simulator_inputs"]
    assert "fire" in sim
    assert "flood" in sim
    assert "cyclone" in sim
    assert "drought" in sim

    # Check cyclone fields
    cyc = sim["cyclone"]
    assert 870.0 <= cyc["central_pressure_hpa"] <= 1040.0
    assert 20.0 <= cyc["max_sustained_wind_kmh"] <= 300.0
    assert 20.0 <= cyc["sea_surface_temp_c"] <= 35.0


def test_api_weather_presets_endpoint(client):
    res = client.get("/api/weather/presets")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["count"] >= 5


def test_api_weather_live_endpoint(client):
    res = client.get("/api/weather/live?lat=19.81&lon=85.83")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "current_weather" in data
    assert "simulator_inputs" in data
    assert data["coordinates"] == [19.81, 85.83]

