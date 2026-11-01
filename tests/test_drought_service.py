"""
Unit and integration tests for Drought Monitoring (Copernicus Sentinel-2 MSI,
multispectral vegetation indices, DBSCAN agro-corridor clustering, and SQLite persistence).
"""

import tempfile
from pathlib import Path
import pytest
import pandas as pd

from app import create_app
from app.config import Config
from app.database import init_db, get_db
from app.services.drought_service import (
    load_drought_data,
    cluster_drought_zones,
    calculate_transparent_drought_priority,
    compute_drought_geometry_and_evidence,
    process_drought_incidents,
    ingest_drought_data_to_db,
)


@pytest.fixture
def test_drought_app():
    """Provides a Flask application instance backed by an isolated temporary SQLite database."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_db_path = Path(tmp_dir) / "test_drought.db"

        class DroughtTestConfig(Config):
            TESTING = True
            DATABASE_PATH = test_db_path

        app = create_app(DroughtTestConfig)
        with app.app_context():
            init_db()
            yield app


def test_load_drought_data():
    """Verify loading and numeric sanitization of Sentinel-2 vegetation indices."""
    df = load_drought_data()
    assert not df.empty
    assert "latitude" in df.columns
    assert "longitude" in df.columns
    assert "ndvi_current" in df.columns
    assert "ndvi_baseline" in df.columns
    assert "ndvi_anomaly" in df.columns
    assert "ndwi_moisture" in df.columns
    assert "vci_percent" in df.columns
    assert "anomaly_magnitude" in df.columns

    # Verify NDVI values are in valid remote sensing range (-1.0 to 1.0)
    assert (df["ndvi_current"] >= -1.0).all() and (df["ndvi_current"] <= 1.0).all()
    assert (df["vci_percent"] >= 0.0).all() and (df["vci_percent"] <= 100.0).all()
    assert (df["anomaly_magnitude"] >= 0.0).all()


def test_drought_dbscan_clustering():
    """Verify that close agricultural drought pixels are clustered together by DBSCAN."""
    sample_data = pd.DataFrame([
        {"latitude": 19.8760, "longitude": 75.3430, "ndvi_anomaly": -0.36, "ndwi_moisture": -0.28, "vci_percent": 14.0, "cloud_cover_percent": 2.0, "anomaly_magnitude": 0.36},
        {"latitude": 19.8820, "longitude": 75.3510, "ndvi_anomaly": -0.36, "ndwi_moisture": -0.31, "vci_percent": 12.0, "cloud_cover_percent": 1.8, "anomaly_magnitude": 0.36},
        {"latitude": 37.9838, "longitude": 23.7275, "ndvi_anomaly": -0.18, "ndwi_moisture": -0.12, "vci_percent": 32.0, "cloud_cover_percent": 1.2, "anomaly_magnitude": 0.18},
    ])

    clustered = cluster_drought_zones(sample_data, eps_km=25.0, min_samples=2)
    assert "cluster_id" in clustered.columns

    # First two points in Marathwada should belong to the same cluster
    assert clustered.iloc[0]["cluster_id"] == clustered.iloc[1]["cluster_id"]
    assert clustered.iloc[0]["cluster_id"] >= 0

    # Distant point in Greece should be noise (-1)
    assert clustered.iloc[2]["cluster_id"] == -1


def test_transparent_drought_priority_scoring():
    """Verify deterministic multi-factor drought priority calculation."""
    catastrophic_drought = pd.DataFrame([
        {"ndvi_current": 0.15, "ndvi_anomaly": -0.38, "ndwi_moisture": -0.35, "vci_percent": 8.0, "cloud_cover_percent": 1.5, "anomaly_magnitude": 0.38},
        {"ndvi_current": 0.14, "ndvi_anomaly": -0.36, "ndwi_moisture": -0.33, "vci_percent": 10.0, "cloud_cover_percent": 2.0, "anomaly_magnitude": 0.36},
        {"ndvi_current": 0.16, "ndvi_anomaly": -0.37, "ndwi_moisture": -0.34, "vci_percent": 9.0, "cloud_cover_percent": 1.0, "anomaly_magnitude": 0.37},
    ])

    result = calculate_transparent_drought_priority(catastrophic_drought)
    assert "priority_score" in result
    assert "priority_level" in result
    assert "factors" in result
    assert "stats" in result

    # Severe desiccation with -0.37 anomaly drop and <10% VCI should yield CRITICAL or HIGH priority
    assert result["priority_score"] >= 75.0
    assert result["factors"]["ndvi_anomaly_factor"] == 100.0
    assert result["factors"]["moisture_deficit_factor"] == 100.0


def test_compute_drought_geometry():
    """Verify centroid weighted by NDVI anomaly drop and affected area."""
    cluster = pd.DataFrame([
        {"latitude": 19.0, "longitude": 75.0, "anomaly_magnitude": 0.10, "cloud_cover_percent": 1.0},
        {"latitude": 19.1, "longitude": 75.1, "anomaly_magnitude": 0.40, "cloud_cover_percent": 1.0},  # 4x larger anomaly
    ])

    geom = compute_drought_geometry_and_evidence(cluster)
    assert "centroid_lat" in geom
    assert "centroid_lon" in geom
    assert "affected_area_sqkm" in geom
    assert "uncertainty_score" in geom

    # Centroid should be pulled toward 19.1, 75.1
    assert geom["centroid_lat"] > 19.05
    assert geom["centroid_lon"] > 75.05
    assert geom["affected_area_sqkm"] > 0


def test_sqlite_drought_ingestion(test_drought_app):
    """Verify that ingest_drought_data_to_db inserts hazards, incidents, updates status, and logs audit."""
    with test_drought_app.app_context():
        db = get_db()
        ingest_result = ingest_drought_data_to_db(db)

        assert ingest_result["status"] == "success"
        assert ingest_result["observations_ingested"] > 0
        assert ingest_result["drought_incidents_formed"] > 0

        # Verify hazards table in SQLite
        hazard_count = db.execute("SELECT COUNT(*) FROM hazards WHERE source = 'SENTINEL_2';").fetchone()[0]
        assert hazard_count == ingest_result["observations_ingested"]

        # Verify incidents table in SQLite
        incident_count = db.execute("SELECT COUNT(*) FROM incidents WHERE hazard_type = 'DROUGHT';").fetchone()[0]
        assert incident_count == ingest_result["drought_incidents_formed"]

        # Verify source_sync_status for Sentinel-2
        s2_row = db.execute("SELECT * FROM source_sync_status WHERE source_name = 'SENTINEL_2';").fetchone()
        assert s2_row["status"] == "READY"
        assert s2_row["records_count"] == hazard_count

        # Verify audit log
        audit_row = db.execute("SELECT * FROM audit_logs WHERE action = 'SENTINEL2_DROUGHT_SYNC';").fetchone()
        assert audit_row is not None


def test_drought_api_endpoints(test_drought_app):
    """Test REST API endpoints for the drought module."""
    with test_drought_app.test_client() as client:
        # Trigger drought sync
        sync_res = client.post("/api/drought/sync")
        assert sync_res.status_code == 200
        sync_data = sync_res.get_json()
        assert sync_data["status"] == "success"

        # Check drought incidents API
        inc_res = client.get("/api/drought/incidents")
        assert inc_res.status_code == 200
        inc_data = inc_res.get_json()
        assert inc_data["status"] == "success"
        assert len(inc_data["incidents"]) > 0

        # Check drought observations API
        obs_res = client.get("/api/drought/observations")
        assert obs_res.status_code == 200
        obs_data = obs_res.get_json()
        assert obs_data["status"] == "success"
        assert len(obs_data["observations"]) > 0

        # Check dedicated frontend route /drought
        page_res = client.get("/drought")
        assert page_res.status_code == 200
        page_html = page_res.get_data(as_text=True)
        assert "Copernicus Sentinel-2" in page_html
        assert "NDVI" in page_html

