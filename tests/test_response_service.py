"""
Unit and integration tests for Emergency Response & Helping Organization Tracking System.
Tests organization directories, geospatial proximity queries, emergency request dispatch,
lifecycle transitions, audit trails, authentication, telemetry, and REST API endpoints.
"""

import tempfile
from pathlib import Path
import pytest
from app import create_app
from app.config import Config
from app.database import get_db, init_db
from app.services.response_service import (
    haversine_distance,
    seed_default_organizations,
    get_organizations,
    get_organization_by_id,
    find_nearby_organizations,
    create_emergency_request,
    update_request_status,
    get_emergency_requests,
    get_request_history,
    get_response_dashboard_stats,
    authenticate_org_user,
    get_user_by_token,
    record_team_location,
    get_latest_team_location,
    RESPONSE_STATUSES,
    ORGANIZATION_CATEGORIES
)


@pytest.fixture
def app_and_client():
    """Configures a fresh Flask test app and client with an isolated temporary SQLite database."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_db_path = Path(tmp_dir) / "test_response.db"

        class TestSettings(Config):
            TESTING = True
            DATABASE_PATH = test_db_path
            SECRET_KEY = "test-secret-key-emergency-response"

        app = create_app(TestSettings)

        with app.app_context():
            init_db(app)
            db = get_db()
            # Seed a sample incident to attach emergency requests to
            db.execute(
                """
                INSERT INTO incidents (
                    incident_uid, hazard_type, title, summary,
                    centroid_lat, centroid_lon, priority_level, priority_score,
                    confidence_score, affected_area_sqkm, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "INC-TEST-001", "FIRE", "Simulated Gujarat Wildfire",
                    "Forest fire near Gir sanctuary perimeter",
                    21.1500, 70.8000, "CRITICAL", 92.5, 0.95, 45.2, "ACTIVE"
                )
            )
            db.commit()

        with app.test_client() as client:
            yield app, client


def test_haversine_distance_calculation():
    """Verify great-circle spherical distance computation."""
    # Ahmedabad (23.0225, 72.5714) to Mumbai (19.0760, 72.8777) is roughly 440-445 km
    dist = haversine_distance(23.0225, 72.5714, 19.0760, 72.8777)
    assert 435.0 <= dist <= 450.0

    # Distance to identical point is 0
    assert haversine_distance(22.0, 70.0, 22.0, 70.0) == 0.0


def test_seed_default_organizations(app_and_client):
    """Verify that default verified organizations and responder users are seeded."""
    app, _ = app_and_client
    with app.app_context():
        orgs = get_organizations()
        assert len(orgs) >= 9

        categories = {o["category"] for o in orgs}
        assert "NDRF" in categories
        assert "SDRF" in categories
        assert "Fire Department" in categories
        assert "Hospitals" in categories
        assert "Ambulance Services" in categories


def test_get_organizations_filtering(app_and_client):
    """Test filtering organizations by category and availability status."""
    app, _ = app_and_client
    with app.app_context():
        ndrf_orgs = get_organizations(category="NDRF")
        assert len(ndrf_orgs) >= 1
        for o in ndrf_orgs:
            assert o["category"] == "NDRF"

        available_orgs = get_organizations(availability="AVAILABLE")
        assert len(available_orgs) >= 1
        for o in available_orgs:
            assert o["availability_status"] == "AVAILABLE"


def test_find_nearby_organizations_sorting(app_and_client):
    """Test that nearby organizations are returned sorted by nearest distance."""
    app, _ = app_and_client
    with app.app_context():
        # Point near Rajkot, Gujarat (22.3039, 70.8022)
        results = find_nearby_organizations(22.3039, 70.8022, limit=10)
        assert len(results) > 0

        # Assert monotonically increasing distance
        distances = [r["distance_km"] for r in results]
        assert distances == sorted(distances)

        # First result should have distance, proximity tier and label
        first = results[0]
        assert "distance_km" in first
        assert "proximity_tier" in first
        assert first["proximity_tier"] in ["IMMEDIATE_RESPONSE", "REGIONAL_SUPPORT", "STRATEGIC_RESERVE"]


def test_emergency_request_dispatch_and_audit(app_and_client):
    """Test dispatching an emergency request, verifying audit log and notification."""
    app, _ = app_and_client
    with app.app_context():
        db = get_db()
        inc = db.execute("SELECT id FROM incidents LIMIT 1").fetchone()
        org = db.execute("SELECT id FROM organizations LIMIT 1").fetchone()

        result = create_emergency_request(
            incident_id=inc["id"],
            org_id=org["id"],
            requester_name="Commander Sharma",
            remarks="Immediate evacuation support required"
        )
        assert result["status"] == "success"
        req_id = result["request_id"]
        assert result["current_status"] == "Pending"

        # Verify audit history was recorded
        history = get_request_history(req_id)
        assert len(history) >= 1
        assert history[0]["new_status"] == "Pending"

        # Duplicate request prevention
        dup = create_emergency_request(incident_id=inc["id"], org_id=org["id"])
        assert dup["status"] == "warning"
        assert dup["request_id"] == req_id


def test_update_request_status_lifecycle(app_and_client):
    """Test the complete 9-stage response lifecycle."""
    app, _ = app_and_client
    with app.app_context():
        db = get_db()
        inc = db.execute("SELECT id FROM incidents LIMIT 1").fetchone()
        org = db.execute("SELECT id FROM organizations LIMIT 1").fetchone()

        res = create_emergency_request(incident_id=inc["id"], org_id=org["id"])
        req_id = res["request_id"]

        # Step through lifecycle transitions
        lifecycle = [
            "Acknowledged",
            "Dispatched",
            "On The Way",
            "Arrived",
            "Assistance In Progress",
            "Completed"
        ]

        for st in lifecycle:
            upd = update_request_status(
                request_id=req_id,
                new_status=st,
                updated_by_name="Field Coordinator",
                remarks=f"Transitioned to {st}"
            )
            assert upd["status"] == "success"
            assert upd["new_status"] == st

        # Verify history has entries for each transition
        hist = get_request_history(req_id)
        assert len(hist) == len(lifecycle) + 1  # Initial Pending + 6 transitions

        # Verify terminal state protection: cannot update after Completed
        with pytest.raises(ValueError, match="terminal state"):
            update_request_status(request_id=req_id, new_status="On The Way")


def test_authorization_check_for_status_update(app_and_client):
    """Test that an organization user can only update requests assigned to their org."""
    app, _ = app_and_client
    with app.app_context():
        db = get_db()
        inc = db.execute("SELECT id FROM incidents LIMIT 1").fetchone()
        orgs = db.execute("SELECT id FROM organizations ORDER BY id ASC LIMIT 2").fetchall()
        org1_id, org2_id = orgs[0]["id"], orgs[1]["id"]

        res = create_emergency_request(incident_id=inc["id"], org_id=org1_id)
        req_id = res["request_id"]

        # Attempting to update with wrong org_id should raise PermissionError
        with pytest.raises(PermissionError, match="Unauthorized"):
            update_request_status(
                request_id=req_id,
                new_status="Acknowledged",
                verify_org_id=org2_id
            )

        # Updating with correct org_id should succeed
        success_upd = update_request_status(
            request_id=req_id,
            new_status="Acknowledged",
            verify_org_id=org1_id
        )
        assert success_upd["status"] == "success"


def test_responder_authentication(app_and_client):
    """Test organization user authentication with hashed passwords and tokens."""
    app, _ = app_and_client
    with app.app_context():
        # Valid login
        user = authenticate_org_user("ndrf_gujarat", "password123")
        assert user is not None
        assert user["username"] == "ndrf_gujarat"
        assert user["auth_token"] is not None
        assert user["role"] == "DISPATCHER"

        # Lookup by token
        by_token = get_user_by_token(user["auth_token"])
        assert by_token is not None
        assert by_token["id"] == user["id"]

        # Invalid password
        bad_pw = authenticate_org_user("ndrf_gujarat", "wrongpassword")
        assert bad_pw is None

        # Unknown username
        unknown = authenticate_org_user("nonexistent_user", "password123")
        assert unknown is None


def test_team_location_telemetry(app_and_client):
    """Test GPS telemetry updates for an active dispatch."""
    app, _ = app_and_client
    with app.app_context():
        db = get_db()
        inc = db.execute("SELECT id FROM incidents LIMIT 1").fetchone()
        org = db.execute("SELECT id FROM organizations LIMIT 1").fetchone()

        req = create_emergency_request(incident_id=inc["id"], org_id=org["id"])
        req_id = req["request_id"]

        # Record location
        loc_res = record_team_location(
            request_id=req_id,
            lat=22.3500,
            lon=70.7800,
            speed_kmh=45.5,
            heading=180.0
        )
        assert loc_res["status"] == "success"

        # Retrieve latest location
        latest = get_latest_team_location(req_id)
        assert latest is not None
        assert latest["latitude"] == 22.3500
        assert latest["longitude"] == 70.7800
        assert latest["speed_kmh"] == 45.5


def test_api_response_endpoints(app_and_client):
    """Test Flask REST API endpoints for emergency response."""
    _, client = app_and_client

    # 1. Categories endpoint
    r = client.get("/api/response/categories")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "success"
    assert len(data["categories"]) >= 8
    assert len(data["statuses"]) == 9

    # 2. Organizations endpoint
    r = client.get("/api/response/organizations")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "success"
    assert len(data["organizations"]) >= 9

    # 3. Stats endpoint
    r = client.get("/api/response/stats")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "success"
    assert "total_contacted" in data
    assert "pending_responses" in data

    # 4. Nearby endpoint
    r = client.get("/api/response/nearby?incident_id=1&limit=5")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "success"
    assert len(data["organizations"]) > 0

    # 5. Create request via API
    r = client.post(
        "/api/response/requests",
        json={"incident_id": 1, "organization_id": 1, "requester_name": "API Operator"}
    )
    assert r.status_code in [200, 201]
    req_data = r.get_json()
    req_id = req_data["request_id"]

    # 6. List requests
    r = client.get("/api/response/requests")
    assert r.status_code == 200
    data = r.get_json()
    assert len(data["requests"]) >= 1

    # 7. Login via API
    r = client.post(
        "/api/response/auth/login",
        json={"username": "ndrf_gujarat", "password": "password123"}
    )
    assert r.status_code == 200
    auth_data = r.get_json()
    token = auth_data["token"]
    assert token is not None

    # 8. Check auth/me with token
    r = client.get("/api/response/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    me = r.get_json()
    assert me["user"]["username"] == "ndrf_gujarat"

    # 9. Request audit history
    r = client.get(f"/api/response/requests/{req_id}/history")
    assert r.status_code == 200
    data = r.get_json()
    assert len(data["history"]) >= 1


def test_html_response_views(app_and_client):
    """Test that the Emergency Response and Organization Portal HTML pages render properly."""
    _, client = app_and_client

    # Emergency Response Dashboard view
    r = client.get("/response")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Emergency Response" in html
    assert "response-tracking-table-body" in html
    assert "disaster-map" in html

    # Organization Portal view
    r = client.get("/org-portal")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Organization Response Portal" in html
    assert "org-login-form" in html

    # Presentation view
    r = client.get("/presentation")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Hackathon Presentation" in html
