"""
Unit and integration tests for Flood Monitoring (Copernicus Sentinel-1 SAR,
NASA GPM rainfall correlation, DBSCAN floodplain clustering, and SQLite persistence).
"""

import tempfile
from pathlib import Path
import pytest
import pandas as pd

from app import create_app
from app.config import Config
from app.database import init_db, get_db
from app.services.flood_service import (
    load_flood_data,
    cluster_flood_zones,
    calculate_transparent_flood_priority,
    compute_flood_geometry_and_evidence,
    process_flood_incidents,
    ingest_flood_data_to_db,
)


@pytest.fixture
def test_flood_app():
    """Provides a Flask application instance backed by an isolated temporary SQLite database."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_db_path = Path(tmp_dir) / "test_flood.db"

        class FloodTestConfig(Config):
            TESTING = True
            DATABASE_PATH = test_db_path

        app = create_app(FloodTestConfig)
        with app.app_context():
            init_db()
            yield app


def test_load_flood_data():
    """Verify loading and numeric sanitization of Sentinel-1 and GPM data."""
    df = load_flood_data()
    assert not df.empty
    assert "latitude" in df.columns
    assert "longitude" in df.columns
    assert "sar_backscatter_db" in df.columns
    assert "backscatter_diff_db" in df.columns
    assert "inundation_prob" in df.columns
    assert "gpm_rainfall_mm_24h" in df.columns
    assert "anomaly_magnitude" in df.columns

    # Verify backscatter drop values are negative decibels
    assert (df["sar_backscatter_db"] < 0).all()
    assert (df["backscatter_diff_db"] < 0).all()
    assert (df["inundation_prob"] >= 0.0).all() and (df["inundation_prob"] <= 1.0).all()


def test_flood_dbscan_clustering():
    """Verify that close flooded radar pixels are clustered together by DBSCAN."""
    sample_data = pd.DataFrame([
        {"latitude": 26.1820, "longitude": 91.7450, "backscatter_diff_db": -11.2, "inundation_prob": 0.95, "gpm_rainfall_mm_24h": 160.0, "anomaly_magnitude": 11.2},
        {"latitude": 26.1895, "longitude": 91.7510, "backscatter_diff_db": -10.3, "inundation_prob": 0.94, "gpm_rainfall_mm_24h": 160.0, "anomaly_magnitude": 10.3},
        {"latitude": 13.7560, "longitude": 100.5018, "backscatter_diff_db": -6.7, "inundation_prob": 0.73, "gpm_rainfall_mm_24h": 50.0, "anomaly_magnitude": 6.7},
    ])

    clustered = cluster_flood_zones(sample_data, eps_km=12.0, min_samples=2)
    assert "cluster_id" in clustered.columns

    # First two points in Brahmaputra should be in the same cluster
    assert clustered.iloc[0]["cluster_id"] == clustered.iloc[1]["cluster_id"]
    assert clustered.iloc[0]["cluster_id"] >= 0

    # Distant point in Thailand should be noise (-1)
    assert clustered.iloc[2]["cluster_id"] == -1


def test_transparent_flood_priority_scoring():
    """Verify deterministic multi-factor flood priority calculation."""
    catastrophic_flood = pd.DataFrame([
        {"sar_backscatter_db": -24.0, "backscatter_diff_db": -12.5, "inundation_prob": 0.98, "gpm_rainfall_mm_24h": 210.0, "anomaly_magnitude": 12.5},
        {"sar_backscatter_db": -23.5, "backscatter_diff_db": -12.0, "inundation_prob": 0.97, "gpm_rainfall_mm_24h": 210.0, "anomaly_magnitude": 12.0},
        {"sar_backscatter_db": -24.5, "backscatter_diff_db": -13.0, "inundation_prob": 0.99, "gpm_rainfall_mm_24h": 215.0, "anomaly_magnitude": 13.0},
    ])

    result = calculate_transparent_flood_priority(catastrophic_flood)
    assert "priority_score" in result
    assert "priority_level" in result
    assert "factors" in result
    assert "stats" in result

    # A cluster with >200mm rain and -12dB drop should receive CRITICAL priority
    assert result["priority_score"] >= 80.0
    assert result["priority_level"] == "CRITICAL"
    assert result["factors"]["inundation_factor"] == 100.0
    assert result["factors"]["rainfall_factor"] == 100.0


def test_compute_flood_geometry():
    """Verify centroid weighted by backscatter drop anomaly and area estimation."""
    cluster = pd.DataFrame([
        {"latitude": 26.0, "longitude": 91.0, "anomaly_magnitude": 5.0},
        {"latitude": 26.1, "longitude": 91.1, "anomaly_magnitude": 15.0},  # 3x larger anomaly pulls centroid
    ])

    geom = compute_flood_geometry_and_evidence(cluster)
    assert "centroid_lat" in geom
    assert "centroid_lon" in geom
    assert "inundated_area_sqkm" in geom
    assert "uncertainty_score" in geom

    # Centroid should be pulled towards 26.1, 91.1
    assert geom["centroid_lat"] > 26.06
    assert geom["centroid_lon"] > 91.06
    assert geom["inundated_area_sqkm"] > 0


def test_sqlite_flood_ingestion(test_flood_app):
    """Verify that ingest_flood_data_to_db inserts hazards, incidents, updates status, and logs audit."""
    with test_flood_app.app_context():
        db = get_db()
        ingest_result = ingest_flood_data_to_db(db)

        assert ingest_result["status"] == "success"
        assert ingest_result["inundation_pixels_ingested"] > 0
        assert ingest_result["flood_incidents_formed"] > 0

        # Verify hazards table in SQLite
        hazard_count = db.execute("SELECT COUNT(*) FROM hazards WHERE source = 'SENTINEL_1';").fetchone()[0]
        assert hazard_count == ingest_result["inundation_pixels_ingested"]

        # Verify incidents table in SQLite
        incident_count = db.execute("SELECT COUNT(*) FROM incidents WHERE hazard_type = 'FLOOD';").fetchone()[0]
        assert incident_count == ingest_result["flood_incidents_formed"]

        # Verify source_sync_status for Sentinel-1 & NASA GPM
        s1_row = db.execute("SELECT * FROM source_sync_status WHERE source_name = 'SENTINEL_1';").fetchone()
        assert s1_row["status"] == "READY"
        assert s1_row["records_count"] == hazard_count

        gpm_row = db.execute("SELECT * FROM source_sync_status WHERE source_name = 'NASA_GPM';").fetchone()
        assert gpm_row["status"] == "READY"

        # Verify audit log
        audit_row = db.execute("SELECT * FROM audit_logs WHERE action = 'SENTINEL1_GPM_SYNC';").fetchone()
        assert audit_row is not None


def test_flood_api_endpoints(test_flood_app):
    """Test REST API endpoints for the flood module."""
    with test_flood_app.test_client() as client:
        # Trigger flood sync
        sync_res = client.post("/api/flood/sync")
        assert sync_res.status_code == 200
        sync_data = sync_res.get_json()
        assert sync_data["status"] == "success"

        # Check flood incidents API
        inc_res = client.get("/api/flood/incidents")
        assert inc_res.status_code == 200
        inc_data = inc_res.get_json()
        assert inc_data["status"] == "success"
        assert len(inc_data["incidents"]) > 0

        # Check flood inundation pixels API
        inundation_res = client.get("/api/flood/inundation")
        assert inundation_res.status_code == 200
        inundation_data = inundation_res.get_json()
        assert inundation_data["status"] == "success"
        assert len(inundation_data["inundation_pixels"]) > 0

        # Check dedicated frontend route /flood
        page_res = client.get("/flood")
        assert page_res.status_code == 200
        page_html = page_res.get_data(as_text=True)
        assert "Copernicus Sentinel-1" in page_html
        assert "NASA GPM" in page_html

