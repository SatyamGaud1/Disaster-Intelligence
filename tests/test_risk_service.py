"""
Integration tests for ML Risk Prediction Service and API endpoints.
Verifies metrics retrieval, prediction calculation, input validation, and regional zone queries.
"""

import pytest
from app import create_app
from app.config import Config
from app.database import init_db


@pytest.fixture
def client():
    """Provides a test client for API integration testing."""
    class TestConfig(Config):
        TESTING = True

    app = create_app(TestConfig)
    with app.app_context():
        init_db()
        with app.test_client() as c:
            yield c


def test_get_fire_ml_metrics(client):
    """Test GET /api/risk/fire/metrics returns validation metrics and feature importances."""
    res = client.get("/api/risk/fire/metrics")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["is_trained"] is True
    assert "metrics" in data
    assert "accuracy" in data["metrics"]
    assert "feature_importances" in data["metrics"]
    assert len(data["features"]) == 5


def test_predict_fire_risk_high(client):
    """Test POST /api/risk/fire/predict with hot and dry weather predicts HIGH risk."""
    payload = {
        "temperature_c": 38.5,
        "relative_humidity_pct": 14.0,
        "wind_speed_kmh": 28.0,
        "rainfall_mm": 0.0,
        "vegetation_ndvi": 0.16
    }
    res = client.post("/api/risk/fire/predict", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    pred = data["prediction"]
    assert pred["risk_category"] == "HIGH"
    assert pred["risk_score"] >= 70.0
    assert "factor_contributions" in pred
    assert len(pred["top_risk_drivers"]) > 0


def test_predict_fire_risk_low(client):
    """Test POST /api/risk/fire/predict with cool and wet weather predicts LOW risk."""
    payload = {
        "temperature_c": 19.0,
        "relative_humidity_pct": 82.0,
        "wind_speed_kmh": 8.0,
        "rainfall_mm": 18.0,
        "vegetation_ndvi": 0.65
    }
    res = client.post("/api/risk/fire/predict", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    pred = data["prediction"]
    assert pred["risk_category"] == "LOW"
    assert pred["risk_score"] < 40.0


def test_predict_fire_risk_invalid_input(client):
    """Test POST /api/risk/fire/predict with out-of-range input returns 400 Bad Request."""
    payload = {
        "temperature_c": 35.0,
        "relative_humidity_pct": 150.0  # Invalid > 100%
    }
    res = client.post("/api/risk/fire/predict", json=payload)
    assert res.status_code == 400
    data = res.get_json()
    assert data["status"] == "error"
    assert "humidity" in data["message"].lower()


def test_get_monitored_fire_risk_zones(client):
    """Test GET /api/risk/fire/zones returns regional risk predictions."""
    res = client.get("/api/risk/fire/zones")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["count"] >= 3
    for zone in data["zones"]:
        assert "zone_id" in zone
        assert "risk_category" in zone
        assert "risk_score" in zone
        assert "uncertainty_level" in zone
        assert "top_drivers" in zone


def test_get_flood_ml_metrics(client):
    """Test GET /api/risk/flood/metrics returns validation metrics and feature importances."""
    res = client.get("/api/risk/flood/metrics")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["is_trained"] is True
    assert "metrics" in data
    assert data["metrics"]["accuracy"] >= 0.85
    assert len(data["features"]) == 5


def test_predict_flood_risk_high(client):
    """Test POST /api/risk/flood/predict with extreme rainfall and saturated soil predicts HIGH risk."""
    payload = {
        "precipitation_24h_mm": 190.0,
        "soil_moisture_pct": 92.0,
        "radar_backscatter_drop_db": 13.0,
        "elevation_m": 20.0,
        "river_proximity_km": 0.5
    }
    res = client.post("/api/risk/flood/predict", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    pred = data["prediction"]
    assert pred["risk_category"] == "HIGH"
    assert pred["risk_score"] >= 70.0
    assert "factor_contributions" in pred


def test_predict_flood_risk_low(client):
    """Test POST /api/risk/flood/predict with dry conditions predicts LOW risk."""
    payload = {
        "precipitation_24h_mm": 5.0,
        "soil_moisture_pct": 25.0,
        "radar_backscatter_drop_db": 1.5,
        "elevation_m": 250.0,
        "river_proximity_km": 12.0
    }
    res = client.post("/api/risk/flood/predict", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    pred = data["prediction"]
    assert pred["risk_category"] == "LOW"
    assert pred["risk_score"] < 40.0


def test_get_monitored_flood_risk_zones(client):
    """Test GET /api/risk/flood/zones returns monitored river basin risk predictions."""
    res = client.get("/api/risk/flood/zones")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["count"] >= 3
    for b in data["zones"]:
        assert "basin_id" in b
        assert "risk_category" in b
        assert "risk_score" in b


def test_get_drought_ml_metrics(client):
    """Test GET /api/risk/drought/metrics returns validation metrics and feature importances."""
    res = client.get("/api/risk/drought/metrics")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["is_trained"] is True
    assert "metrics" in data
    assert data["metrics"]["accuracy"] >= 0.85
    assert len(data["features"]) == 5


def test_predict_drought_risk_high(client):
    """Test POST /api/risk/drought/predict with severe negative NDVI/NDWI predicts HIGH risk."""
    payload = {
        "ndvi_anomaly": -0.38,
        "ndwi_moisture": -0.29,
        "vci_percent": 12.0,
        "precipitation_deficit_pct": 82.0,
        "soil_temperature_c": 42.0
    }
    res = client.post("/api/risk/drought/predict", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    pred = data["prediction"]
    assert pred["risk_category"] == "HIGH"
    assert pred["risk_score"] >= 70.0
    assert "factor_contributions" in pred


def test_predict_drought_risk_low(client):
    """Test POST /api/risk/drought/predict with healthy canopy predicts LOW risk."""
    payload = {
        "ndvi_anomaly": 0.06,
        "ndwi_moisture": 0.19,
        "vci_percent": 72.0,
        "precipitation_deficit_pct": 14.0,
        "soil_temperature_c": 25.0
    }
    res = client.post("/api/risk/drought/predict", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    pred = data["prediction"]
    assert pred["risk_category"] == "LOW"
    assert pred["risk_score"] < 40.0


def test_get_monitored_drought_risk_zones(client):
    """Test GET /api/risk/drought/zones returns agricultural belt risk predictions."""
    res = client.get("/api/risk/drought/zones")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["count"] >= 3
    for z in data["zones"]:
        assert "zone_id" in z
        assert "risk_category" in z
        assert "risk_score" in z


def test_get_cyclone_ml_metrics(client):
    """Test GET /api/risk/cyclone/metrics returns cross-validation evaluation metrics."""
    res = client.get("/api/risk/cyclone/metrics")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["is_trained"] is True
    assert "metrics" in data
    assert "accuracy" in data["metrics"]
    assert "feature_importances" in data["metrics"]
    assert len(data["features"]) == 5


def test_predict_cyclone_risk_high(client):
    """Test POST /api/risk/cyclone/predict with extreme cyclone parameters predicts HIGH risk."""
    payload = {
        "central_pressure_hpa": 935.0,
        "max_sustained_wind_kmh": 205.0,
        "sea_surface_temp_c": 30.5,
        "storm_forward_speed_kmh": 12.0,
        "coastal_distance_km": 30.0
    }
    res = client.post("/api/risk/cyclone/predict", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    pred = data["data"]
    assert pred["risk_category"] == "HIGH"
    assert pred["risk_score"] >= 70.0
    assert "classifications" in pred
    assert len(pred["top_risk_drivers"]) > 0


def test_predict_cyclone_risk_low(client):
    """Test POST /api/risk/cyclone/predict with mild depression predicts LOW risk."""
    payload = {
        "central_pressure_hpa": 1008.0,
        "max_sustained_wind_kmh": 45.0,
        "sea_surface_temp_c": 25.0,
        "storm_forward_speed_kmh": 25.0,
        "coastal_distance_km": 400.0
    }
    res = client.post("/api/risk/cyclone/predict", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    pred = data["data"]
    assert pred["risk_category"] == "LOW"
    assert pred["risk_score"] < 40.0


def test_get_monitored_cyclone_risk_zones(client):
    """Test GET /api/risk/cyclone/zones returns coastal maritime sector risk predictions."""
    res = client.get("/api/risk/cyclone/zones")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["count"] >= 3
    for z in data["zones"]:
        assert "zone_id" in z
        assert "risk_category" in z
        assert "risk_score" in z
        assert "classifications" in z


def test_cyclone_tracking_api_endpoints(client):
    """Test cyclone tracking, track coordinates, and advisory API endpoints."""
    # Active systems
    r_act = client.get("/api/cyclone/active")
    assert r_act.status_code == 200
    act_data = r_act.get_json()
    assert act_data["status"] == "success"
    assert len(act_data["systems"]) >= 1

    # Tracks
    r_trk = client.get("/api/cyclone/tracks?storm_id=2023-ARB-BIPARJOY")
    assert r_trk.status_code == 200
    trk_data = r_trk.get_json()
    assert trk_data["status"] == "success"
    assert len(trk_data["data"]["observed_track"]) > 0
    assert len(trk_data["data"]["forecast_track"]) > 0

    # Advisories
    r_adv = client.get("/api/cyclone/advisories")
    assert r_adv.status_code == 200
    adv_data = r_adv.get_json()
    assert adv_data["status"] == "success"
    assert len(adv_data["advisories"]) >= 1




