"""
Unit and integration tests for Phase 4: Smart Evacuation & Safe Route Planner.
Verifies nearby shelter/hospital discovery, intelligent route calculation,
alternative route generation, hazard intersection risk classification,
shelter capacity constraints, and REST API endpoints.
"""

import tempfile
from pathlib import Path
import pytest
from app import create_app
from app.config import Config
from app.database import get_db, init_db
from app.services.evacuation_service import (
    haversine_distance,
    find_nearby_shelters,
    find_nearby_hospitals,
    get_shelter_by_id,
    update_shelter_occupancy,
    calculate_evacuation_routes,
    assess_route_risk,
    get_evacuation_hazards_geojson,
    get_evacuation_dashboard_stats
)


@pytest.fixture
def evac_client():
    """Configures a fresh Flask test client with an isolated temporary SQLite database."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_db_path = Path(tmp_dir) / "test_evac.db"

        class TestSettings(Config):
            TESTING = True
            DATABASE_PATH = test_db_path
            SECRET_KEY = "test-secret-key-evacuation-planner"

        app = create_app(TestSettings)

        with app.app_context():
            init_db(app)
            db = get_db()
            # Seed a sample incident to attach evacuation routes to
            db.execute(
                """
                INSERT INTO incidents (
                    incident_uid, hazard_type, title, summary,
                    centroid_lat, centroid_lon, priority_level, priority_score,
                    confidence_score, affected_area_sqkm, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "INC-EVAC-001", "CYCLONE", "Severe Cyclonic Storm Alert",
                    "Approaching Saurashtra coastal belt near Dwarka",
                    22.2442, 68.9685, "CRITICAL", 94.0, 0.98, 120.0, "ACTIVE"
                )
            )
            # Seed a high-confidence flood hazard point
            db.execute(
                """
                INSERT INTO hazards (
                    source, hazard_type, latitude, longitude, intensity_value,
                    confidence, observation_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("SENTINEL_1", "FLOOD", 22.3850, 69.5200, 0.85, 0.95, "2026-10-31T12:00:00Z")
            )
            # Seed an active fire hazard point
            db.execute(
                """
                INSERT INTO hazards (
                    source, hazard_type, latitude, longitude, intensity_value,
                    confidence, observation_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("NASA_FIRMS", "FIRE", 21.2800, 70.8400, 75.0, 0.92, "2026-10-31T12:00:00Z")
            )
            db.commit()

        with app.test_client() as client:
            yield app, client


def test_haversine_distance_computation():
    """Verifies spherical great-circle distance math."""
    # Jamnagar (22.4707, 70.0577) to Rajkot (22.3039, 70.8022) is roughly 80-85 km
    dist = haversine_distance(22.4707, 70.0577, 22.3039, 70.8022)
    assert 78.0 <= dist <= 90.0
    assert haversine_distance(22.0, 70.0, 22.0, 70.0) == 0.0


def test_nearby_shelters_discovery(evac_client):
    """Verifies discovering registered emergency shelters sorted by proximity."""
    app, _ = evac_client
    with app.app_context():
        # Query near Dwarka (22.2442, 68.9685)
        shelters = find_nearby_shelters(22.2442, 68.9685, limit=5)
        assert len(shelters) > 0
        assert shelters[0]["distance_km"] < 5.0  # Dwarka shelter itself
        assert "available_capacity" in shelters[0]
        assert "occupancy_pct" in shelters[0]
        assert shelters[0]["destination_type"] == "SHELTER"

        # Verify sorted ascending by distance
        distances = [s["distance_km"] for s in shelters]
        assert distances == sorted(distances)


def test_nearby_hospitals_discovery(evac_client):
    """Verifies discovering emergency hospitals and trauma centers sorted by proximity."""
    app, _ = evac_client
    with app.app_context():
        # Query near Jamnagar (22.4707, 70.0577)
        hospitals = find_nearby_hospitals(22.4707, 70.0577, limit=5)
        assert len(hospitals) > 0
        assert hospitals[0]["distance_km"] < 5.0  # GG Hospital Jamnagar
        assert "available_beds" in hospitals[0]
        assert hospitals[0]["destination_type"] == "HOSPITAL"

        distances = [h["distance_km"] for h in hospitals]
        assert distances == sorted(distances)


def test_shelter_capacity_validation_and_history(evac_client):
    """Tests updating shelter occupancy with capacity bounds and audit logging."""
    app, _ = evac_client
    with app.app_context():
        shelter = get_shelter_by_id(1)
        assert shelter is not None
        cap = shelter["capacity"]

        # Valid update
        res = update_shelter_occupancy(
            shelter_id=1,
            new_occupancy=450,
            updated_by="Officer Ramesh",
            remarks="Evacuees registered from coastal Sector 1"
        )
        assert res["status"] == "success"
        assert res["new_occupancy"] == 450
        assert res["available_capacity"] == cap - 450

        # Disallow exceeding capacity
        with pytest.raises(ValueError, match="exceed"):
            update_shelter_occupancy(shelter_id=1, new_occupancy=cap + 100)

        # Disallow negative occupancy
        with pytest.raises(ValueError, match="negative"):
            update_shelter_occupancy(shelter_id=1, new_occupancy=-10)

        # Disallow nonexistent shelter
        with pytest.raises(ValueError, match="not found"):
            update_shelter_occupancy(shelter_id=9999, new_occupancy=50)


def test_route_calculation_and_waypoints(evac_client):
    """Verifies primary and alternative route calculation from epicenter to destination."""
    app, _ = evac_client
    with app.app_context():
        # Dwarka (22.2442, 68.9685) to Jamnagar (22.4707, 70.0577)
        routes = calculate_evacuation_routes(
            origin_lat=22.2442,
            origin_lon=68.9685,
            dest_lat=22.4707,
            dest_lon=70.0577,
            incident_id=1
        )
        assert routes["status"] == "success"
        assert "primary_route" in routes
        assert "alternative_route" in routes

        primary = routes["primary_route"]
        alt = routes["alternative_route"]

        assert primary["distance_km"] > 100.0
        assert primary["duration_minutes"] > 60.0
        assert len(primary["coordinates"]) >= 10
        assert len(alt["coordinates"]) >= 10
        assert "risk_assessment" in primary


def test_hazard_intersection_risk_assessment(evac_client):
    """Verifies that route risk classification flags intersections with active flood/fire or closure."""
    app, _ = evac_client
    with app.app_context():
        # 1. Route intentionally constructed near the active flood point (22.3850, 69.5200)
        flood_path = [
            [22.3800, 69.5100],
            [22.3840, 69.5190],
            [22.3900, 69.5300]
        ]
        high_risk_eval = assess_route_risk(flood_path)
        assert high_risk_eval["risk_level"] == "HIGH_RISK"
        assert high_risk_eval["risk_score"] > 30.0
        assert any("flood" in w.lower() or "obstruction" in w.lower() for w in high_risk_eval["warnings"])

        # 2. Path far away from hazards evaluates to SAFE
        safe_path = [
            [23.5000, 72.0000],
            [23.5500, 72.1000],
            [23.6000, 72.2000]
        ]
        safe_eval = assess_route_risk(safe_path)
        assert safe_eval["risk_level"] == "SAFE"
        assert safe_eval["risk_score"] == 0.0


def test_evacuation_hazards_geojson(evac_client):
    """Verifies GeoJSON hazard overlay feature collection."""
    app, _ = evac_client
    with app.app_context():
        geojson = get_evacuation_hazards_geojson()
        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) >= 2
        first_feat = geojson["features"][0]
        assert "geometry" in first_feat
        assert "properties" in first_feat
        assert first_feat["properties"]["layer_type"] in ["ROAD_HAZARD", "SATELLITE_HAZARD"]


def test_evacuation_dashboard_stats(evac_client):
    """Verifies real-time summary telemetry counters."""
    app, _ = evac_client
    with app.app_context():
        stats = get_evacuation_dashboard_stats()
        assert stats["status"] == "success"
        assert stats["total_shelters"] >= 7
        assert stats["total_capacity"] > 5000
        assert stats["available_capacity"] > 0
        assert stats["operating_hospitals"] >= 5


def test_api_evacuation_endpoints(evac_client):
    """Tests REST API endpoints for smart evacuation planner."""
    _, client = evac_client

    # 1. Stats endpoint
    r = client.get("/api/evacuation/stats")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "success"
    assert data["total_shelters"] >= 7

    # 2. Shelters list
    r = client.get("/api/evacuation/shelters")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "success"
    assert len(data["shelters"]) >= 7

    # 3. Single shelter
    r = client.get("/api/evacuation/shelters/1")
    assert r.status_code == 200
    data = r.get_json()
    assert data["shelter"]["id"] == 1

    # 4. Hospitals list
    r = client.get("/api/evacuation/hospitals")
    assert r.status_code == 200
    data = r.get_json()
    assert data["count"] >= 5

    # 5. Nearby endpoint by incident_id
    r = client.get("/api/evacuation/nearby?incident_id=1&limit=5")
    assert r.status_code == 200
    data = r.get_json()
    assert len(data["shelters"]) > 0
    assert len(data["hospitals"]) > 0

    # 6. Route calculation endpoint
    r = client.post(
        "/api/evacuation/route",
        json={
            "origin_lat": 22.2442,
            "origin_lon": 68.9685,
            "dest_lat": 22.4707,
            "dest_lon": 70.0577,
            "incident_id": 1
        }
    )
    assert r.status_code == 200
    route_data = r.get_json()
    assert route_data["status"] == "success"
    assert "primary_route" in route_data
    assert "alternative_route" in route_data

    # 7. Update shelter occupancy via API
    r = client.post(
        "/api/evacuation/shelters/1/occupancy",
        json={"new_occupancy": 350, "updated_by": "Test Officer"}
    )
    assert r.status_code == 200
    upd_data = r.get_json()
    assert upd_data["new_occupancy"] == 350

    # 8. Invalid route request (missing coordinates) returns 400
    r = client.post("/api/evacuation/route", json={"origin_lat": 22.0})
    assert r.status_code == 400

    # 9. Hazards GeoJSON endpoint
    r = client.get("/api/evacuation/hazards")
    assert r.status_code == 200
    data = r.get_json()
    assert data["type"] == "FeatureCollection"


def test_html_evacuation_view(evac_client):
    """Tests that the Smart Evacuation dashboard HTML page renders successfully."""
    _, client = evac_client
    r = client.get("/evacuation")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Smart Evacuation" in html
    assert "evac-incident-select" in html
    assert "evac-destinations-container" in html
    assert "disaster-map" in html
    assert "evac-risk-banner" in html
    assert "evac-shelters-table-body" in html

