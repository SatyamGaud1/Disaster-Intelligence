"""
Unit and integration tests for Cyclone Risk Prediction ML Engine.
Verifies training, 5-fold cross-validation metrics, predictions, uncertainty estimation,
intensity classification, explainability, and persistence.
"""

from pathlib import Path
import tempfile
import pytest
import pandas as pd
from app.ml.cyclone_risk_model import CycloneRiskPredictor
from app.ml.create_cyclone_dataset import generate_cyclone_benchmark_dataset


@pytest.fixture(scope="module")
def cyclone_training_df():
    """Generates a temporary benchmark cyclone training dataset."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_path = Path(tmp_dir) / "test_cyclone_dataset.csv"
        generate_cyclone_benchmark_dataset(output_path=csv_path, n_samples=250, seed=42)
        yield pd.read_csv(csv_path)


@pytest.fixture(scope="module")
def trained_cyclone_predictor(cyclone_training_df):
    """Provides an in-memory trained cyclone predictor instance."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        model_path = Path(tmp_dir) / "test_cyclone_model.joblib"
        predictor = CycloneRiskPredictor(model_path=model_path)
        predictor.train_and_evaluate(cyclone_training_df)
        yield predictor


def test_cyclone_model_training_and_metrics(cyclone_training_df):
    """Verify that training computes rigorous 5-fold cross-validation evaluation metrics."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        model_path = Path(tmp_dir) / "model_metrics_cyclone_test.joblib"
        predictor = CycloneRiskPredictor(model_path=model_path)
        metrics = predictor.train_and_evaluate(cyclone_training_df)

        assert metrics["total_samples"] == len(cyclone_training_df)
        assert metrics["accuracy"] >= 0.80
        assert metrics["recall"] >= 0.80
        assert metrics["roc_auc"] >= 0.85

        cm = metrics["confusion_matrix"]
        assert cm["true_positive"] + cm["false_positive"] + cm["true_negative"] + cm["false_negative"] == len(cyclone_training_df)

        importances = metrics["feature_importances"]
        assert len(importances) == 5
        assert "central_pressure_hpa" in importances
        assert "max_sustained_wind_kmh" in importances


def test_high_cyclone_risk_prediction(trained_cyclone_predictor):
    """Test intense cyclone (930 hPa, 210 km/h wind, warm SST, 25km coast) yields HIGH risk."""
    res = trained_cyclone_predictor.predict_risk(
        central_pressure_hpa=930.0,
        max_sustained_wind_kmh=210.0,
        sea_surface_temp_c=30.5,
        storm_forward_speed_kmh=14.0,
        coastal_distance_km=25.0
    )

    assert res["risk_category"] == "HIGH"
    assert res["risk_score"] >= 70.0
    assert "classifications" in res
    assert "Category 4" in res["classifications"]["saffir_simpson"] or "Category 5" in res["classifications"]["saffir_simpson"]
    assert len(res["top_risk_drivers"]) >= 1
    assert any(f["factor"] == "central_pressure_hpa" and f["severity_score"] >= 90 for f in res["factor_contributions"])


def test_low_cyclone_risk_prediction(trained_cyclone_predictor):
    """Test mild tropical depression far offshore yields LOW risk."""
    res = trained_cyclone_predictor.predict_risk(
        central_pressure_hpa=1008.0,
        max_sustained_wind_kmh=50.0,
        sea_surface_temp_c=25.0,
        storm_forward_speed_kmh=25.0,
        coastal_distance_km=450.0
    )

    assert res["risk_category"] == "LOW"
    assert res["risk_score"] < 40.0
    assert "Tropical Depression" in res["classifications"]["saffir_simpson"] or "Low" in res["classifications"]["imd_scale"] or "Depression" in res["classifications"]["imd_scale"]


def test_cyclone_uncertainty_quantification(trained_cyclone_predictor):
    """Test uncertainty fields are well-formed and bounded in [0, 100]."""
    res = trained_cyclone_predictor.predict_risk(
        central_pressure_hpa=985.0,
        max_sustained_wind_kmh=95.0,
        sea_surface_temp_c=27.5,
        storm_forward_speed_kmh=18.0,
        coastal_distance_km=140.0
    )

    assert 0.0 <= res["confidence_pct"] <= 100.0
    assert 0.0 <= res["uncertainty_pct"] <= 100.0
    assert res["uncertainty_level"] in ["LOW", "MODERATE", "HIGH"]
    assert len(res["uncertainty_text"]) > 0


def test_cyclone_model_save_and_load(cyclone_training_df):
    """Test serialization and loading round-trip with identical predictions."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        model_path = Path(tmp_dir) / "cyclone_roundtrip_test.joblib"
        p1 = CycloneRiskPredictor(model_path=model_path)
        p1.train_and_evaluate(cyclone_training_df)

        p2 = CycloneRiskPredictor(model_path=model_path)
        assert p2.is_trained is True

        res1 = p1.predict_risk(960.0, 140.0, 28.5, 20.0, 100.0)
        res2 = p2.predict_risk(960.0, 140.0, 28.5, 20.0, 100.0)
        assert res1["risk_score"] == res2["risk_score"]
        assert res1["risk_category"] == res2["risk_category"]

