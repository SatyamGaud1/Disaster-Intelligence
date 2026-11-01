"""
Unit and integration tests for Forest Fire Monitoring (NASA FIRMS pipeline,
DBSCAN clustering, transparent priority scoring, and SQLite persistence).
"""

import json
import tempfile
from pathlib import Path
import pytest
import pandas as pd

from app import create_app
from app.config import Config
from app.database import init_db, get_db
from app.services.fire_service import (
    load_firms_data,
    cluster_fire_hotspots,
    calculate_transparent_fire_priority,
    compute_incident_geometry_and_evidence,
    process_fire_incidents,
    ingest_fire_data_to_db,
)


@pytest.fixture
def test_app():
    """Provides a Flask app instance backed by a temporary SQLite database."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_db_path = Path(tmp_dir) / "test_fire.db"

        class FireTestConfig(Config):
            TESTING = True
            DATABASE_PATH = test_db_path

        app = create_app(FireTestConfig)
        with app.app_context():
            init_db()
            yield app


def test_load_firms_data():
    """Verify loading and normalization of NASA FIRMS observations."""
    df = load_firms_data()
    assert not df.empty
    assert "latitude" in df.columns
    assert "longitude" in df.columns
    assert "frp" in df.columns
    assert "confidence_numeric" in df.columns
    assert "is_night" in df.columns

    # Verify data types and non-null values
    assert df["frp"].dtype in ("float64", "float32")
    assert (df["confidence_numeric"] >= 0.0).all() and (df["confidence_numeric"] <= 1.0).all()
    assert set(df["is_night"].unique()).issubset({0.0, 1.0})


def test_dbscan_clustering_groups_nearby_hotspots():
    """Verify that close fire hotspots are clustered together by DBSCAN with Haversine distance."""
    # Create two close points in California and one far away in India
    sample_data = pd.DataFrame([
        {"latitude": 34.2154, "longitude": -118.1523, "frp": 45.0, "confidence_numeric": 0.85, "is_night": 1.0, "daynight": "N"},
        {"latitude": 34.2189, "longitude": -118.1487, "frp": 60.0, "confidence_numeric": 0.95, "is_night": 1.0, "daynight": "N"},
        {"latitude": 28.6139, "longitude": 77.2090, "frp": 30.0, "confidence_numeric": 0.75, "is_night": 0.0, "daynight": "D"},
    ])

    clustered = cluster_fire_hotspots(sample_data, eps_km=8.0, min_samples=2)
    assert "cluster_id" in clustered.columns

    # First two points should belong to the same non-negative cluster
    assert clustered.iloc[0]["cluster_id"] == clustered.iloc[1]["cluster_id"]
    assert clustered.iloc[0]["cluster_id"] >= 0

    # Distant point should be noise (-1)
    assert clustered.iloc[2]["cluster_id"] == -1


def test_transparent_priority_scoring():
    """Verify deterministic multi-factor priority score calculation."""
    high_intensity_cluster = pd.DataFrame([
        {"latitude": 34.21, "longitude": -118.15, "frp": 95.0, "confidence_numeric": 0.95, "is_night": 1.0},
        {"latitude": 34.22, "longitude": -118.14, "frp": 120.0, "confidence_numeric": 0.95, "is_night": 1.0},
        {"latitude": 34.23, "longitude": -118.13, "frp": 110.0, "confidence_numeric": 0.95, "is_night": 1.0},
    ])

    result = calculate_transparent_fire_priority(high_intensity_cluster)
    assert "priority_score" in result
    assert "priority_level" in result
    assert "factors" in result
    assert "stats" in result

    # An intense nighttime cluster with >100MW FRP should receive CRITICAL priority
    assert result["priority_score"] >= 80.0
    assert result["priority_level"] == "CRITICAL"
    assert result["factors"]["frp_factor"] > 0
    assert result["factors"]["night_persistence_factor"] == 100.0


def test_incident_geometry_and_evidence():
    """Verify FRP-weighted centroid and area approximation."""
    cluster = pd.DataFrame([
        {"latitude": 30.0, "longitude": 70.0, "frp": 10.0},
        {"latitude": 30.1, "longitude": 70.1, "frp": 90.0},  # Much higher FRP pulling centroid
    ])

    geom = compute_incident_geometry_and_evidence(cluster)
    assert "centroid_lat" in geom
    assert "centroid_lon" in geom
    assert "affected_area_sqkm" in geom
    assert "uncertainty_score" in geom

    # Centroid should be heavily skewed toward 30.1, 70.1 due to FRP weighting
    assert geom["centroid_lat"] > 30.05
    assert geom["centroid_lon"] > 70.05
    assert geom["affected_area_sqkm"] > 0


def test_sqlite_fire_ingestion(test_app):
    """Verify that ingest_fire_data_to_db inserts hazards, incidents, updates status, and logs audit."""
    with test_app.app_context():
        db = get_db()
        ingest_result = ingest_fire_data_to_db(db)

        assert ingest_result["status"] == "success"
        assert ingest_result["hotspots_ingested"] > 0
        assert ingest_result["incidents_formed"] > 0

        # Verify hazards table in SQLite
        hazard_count = db.execute("SELECT COUNT(*) FROM hazards WHERE source = 'NASA_FIRMS';").fetchone()[0]
        assert hazard_count == ingest_result["hotspots_ingested"]

        # Verify incidents table in SQLite
        incident_count = db.execute("SELECT COUNT(*) FROM incidents WHERE hazard_type = 'FIRE';").fetchone()[0]
        assert incident_count == ingest_result["incidents_formed"]

        # Verify source_sync_status updated
        sync_row = db.execute("SELECT * FROM source_sync_status WHERE source_name = 'NASA_FIRMS';").fetchone()
        assert sync_row["status"] == "READY"
        assert sync_row["records_count"] == hazard_count

        # Verify audit log
        audit_row = db.execute("SELECT * FROM audit_logs WHERE action = 'NASA_FIRMS_SYNC';").fetchone()
        assert audit_row is not None


def test_fire_api_endpoints(test_app):
    """Test REST API endpoints for the fire module."""
    with test_app.test_client() as client:
        # Trigger fire sync
        sync_res = client.post("/api/fire/sync")
        assert sync_res.status_code == 200
        sync_data = sync_res.get_json()
        assert sync_data["status"] == "success"

        # Check fire incidents API
        inc_res = client.get("/api/fire/incidents")
        assert inc_res.status_code == 200
        inc_data = inc_res.get_json()
        assert inc_data["status"] == "success"
        assert len(inc_data["incidents"]) > 0

        # Check fire hotspots API
        hot_res = client.get("/api/fire/hotspots")
        assert hot_res.status_code == 200
        hot_data = hot_res.get_json()
        assert hot_data["status"] == "success"
        assert len(hot_data["hotspots"]) > 0

        # Check dedicated frontend route /fire
        page_res = client.get("/fire")
        assert page_res.status_code == 200
        page_html = page_res.get_data(as_text=True)
        assert "NASA FIRMS" in page_html
        assert "DBSCAN" in page_html

