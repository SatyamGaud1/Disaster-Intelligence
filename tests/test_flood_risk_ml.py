"""
Unit and integration tests for Flood Risk Prediction ML Engine.
Verifies training, 5-fold cross-validation metrics, predictions, uncertainty estimation,
explainability, and persistence.
"""

from pathlib import Path
import tempfile
import pytest
import pandas as pd
from app.ml.flood_risk_model import FloodRiskPredictor
from app.ml.create_flood_dataset import generate_flood_benchmark_dataset


@pytest.fixture(scope="module")
def flood_training_df():
    """Generates a temporary benchmark flood training dataset."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_path = Path(tmp_dir) / "test_flood_dataset.csv"
        generate_flood_benchmark_dataset(output_path=csv_path, n_samples=200, seed=42)
        yield pd.read_csv(csv_path)


@pytest.fixture(scope="module")
def trained_flood_predictor(flood_training_df):
    """Provides an in-memory trained flood predictor instance."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        model_path = Path(tmp_dir) / "test_flood_model.joblib"
        predictor = FloodRiskPredictor(model_path=model_path)
        predictor.train_and_evaluate(flood_training_df)
        yield predictor


def test_flood_model_training_and_metrics(flood_training_df):
    """Verify that training computes rigorous 5-fold cross-validation evaluation metrics."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        model_path = Path(tmp_dir) / "model_metrics_flood_test.joblib"
        predictor = FloodRiskPredictor(model_path=model_path)
        metrics = predictor.train_and_evaluate(flood_training_df)

        assert metrics["total_samples"] == len(flood_training_df)
        assert metrics["accuracy"] >= 0.85
        assert metrics["recall"] >= 0.85
        assert metrics["roc_auc"] >= 0.90

        cm = metrics["confusion_matrix"]
        assert cm["true_positive"] + cm["false_positive"] + cm["true_negative"] + cm["false_negative"] == len(flood_training_df)

        importances = metrics["feature_importances"]
        assert len(importances) == 5
        assert "precipitation_24h_mm" in importances
        assert "radar_backscatter_drop_db" in importances


def test_high_flood_risk_prediction(trained_flood_predictor):
    """Test torrential rain, saturated soil, steep SAR drop, and river proximity yields HIGH risk category."""
    res = trained_flood_predictor.predict_risk(
        precipitation_24h_mm=185.0,
        soil_moisture_pct=88.0,
        radar_backscatter_drop_db=12.5,
        elevation_m=25.0,
        river_proximity_km=0.8
    )

    assert res["risk_category"] == "HIGH"
    assert res["risk_score"] >= 70.0
    assert "factor_contributions" in res
    assert len(res["factor_contributions"]) == 5
    assert len(res["top_risk_drivers"]) > 0
    assert "explanation" in res


def test_low_flood_risk_prediction(trained_flood_predictor):
    """Test light rain, dry soil, minimal radar drop, high elevation yields LOW risk category."""
    res = trained_flood_predictor.predict_risk(
        precipitation_24h_mm=12.0,
        soil_moisture_pct=35.0,
        radar_backscatter_drop_db=2.0,
        elevation_m=280.0,
        river_proximity_km=15.0
    )

    assert res["risk_category"] == "LOW"
    assert res["risk_score"] < 40.0


def test_borderline_flood_uncertainty(trained_flood_predictor):
    """Verify uncertainty metric on borderline hydrological conditions."""
    res = trained_flood_predictor.predict_risk(
        precipitation_24h_mm=65.0,
        soil_moisture_pct=60.0,
        radar_backscatter_drop_db=5.5,
        elevation_m=95.0,
        river_proximity_km=3.5
    )

    assert "uncertainty_pct" in res
    assert "uncertainty_level" in res
    assert 0.0 <= res["uncertainty_pct"] <= 100.0


def test_flood_model_save_and_load(flood_training_df):
    """Verify serialization to joblib file and reload integrity."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "persistent_flood_model.joblib"
        p1 = FloodRiskPredictor(model_path=target)
        p1.train_and_evaluate(flood_training_df)
        assert target.exists()

        p2 = FloodRiskPredictor(model_path=target)
        assert p2.is_trained is True
        res = p2.predict_risk(120.0, 75.0, 8.0, 45.0, 1.2)
        assert res["risk_category"] in ("LOW", "MEDIUM", "HIGH")

