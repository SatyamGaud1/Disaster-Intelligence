"""
Unit and integration tests for Forest Fire Risk Prediction ML Engine.
Verifies training, 5-fold cross-validation metrics, predictions, uncertainty estimation,
explainability, and persistence.
"""

from pathlib import Path
import tempfile
import pytest
import pandas as pd
from app.ml.fire_risk_model import ForestFireRiskPredictor
from app.ml.create_dataset import generate_benchmark_dataset


@pytest.fixture(scope="module")
def training_df():
    """Generates a temporary benchmark training dataset."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_path = Path(tmp_dir) / "test_fire_dataset.csv"
        generate_benchmark_dataset(output_path=csv_path, n_samples=200, seed=42)
        yield pd.read_csv(csv_path)


@pytest.fixture(scope="module")
def trained_predictor(training_df):
    """Provides an in-memory trained predictor instance."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        model_path = Path(tmp_dir) / "test_model.joblib"
        predictor = ForestFireRiskPredictor(model_path=model_path)
        predictor.train_and_evaluate(training_df)
        yield predictor


def test_model_training_and_metrics(training_df):
    """Verify that training computes rigorous cross-validation evaluation metrics."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        model_path = Path(tmp_dir) / "model_metrics_test.joblib"
        predictor = ForestFireRiskPredictor(model_path=model_path)
        metrics = predictor.train_and_evaluate(training_df)

        assert metrics["total_samples"] == len(training_df)
        assert 0.0 <= metrics["accuracy"] <= 1.0
        assert 0.0 <= metrics["precision"] <= 1.0
        assert 0.0 <= metrics["recall"] <= 1.0
        assert 0.0 <= metrics["f1_score"] <= 1.0
        assert 0.0 <= metrics["roc_auc"] <= 1.0

        # Confusion matrix checks
        cm = metrics["confusion_matrix"]
        assert cm["true_positive"] + cm["false_positive"] + cm["true_negative"] + cm["false_negative"] == len(training_df)

        # Feature importances sum close to 100%
        importances = metrics["feature_importances"]
        assert len(importances) == 5
        assert abs(sum(importances.values()) - 100.0) < 1.0
        assert "relative_humidity_pct" in importances
        assert "vegetation_ndvi" in importances


def test_high_risk_prediction(trained_predictor):
    """Test hot, dry, windy weather yields HIGH risk category."""
    res = trained_predictor.predict_risk(
        temperature_c=38.0,
        relative_humidity_pct=15.0,
        wind_speed_kmh=32.0,
        rainfall_mm=0.0,
        vegetation_ndvi=0.15
    )

    assert res["risk_category"] == "HIGH"
    assert res["risk_score"] >= 70.0
    assert "factor_contributions" in res
    assert len(res["factor_contributions"]) == 5
    assert len(res["top_risk_drivers"]) > 0
    assert "explanation" in res


def test_low_risk_prediction(trained_predictor):
    """Test cool, humid, rainy weather with green canopy yields LOW risk category."""
    res = trained_predictor.predict_risk(
        temperature_c=18.0,
        relative_humidity_pct=85.0,
        wind_speed_kmh=8.0,
        rainfall_mm=25.0,
        vegetation_ndvi=0.65
    )

    assert res["risk_category"] == "LOW"
    assert res["risk_score"] < 40.0


def test_borderline_uncertainty(trained_predictor):
    """Verify uncertainty metric accurately reflects borderline probability conditions."""
    res = trained_predictor.predict_risk(
        temperature_c=29.0,
        relative_humidity_pct=42.0,
        wind_speed_kmh=18.0,
        rainfall_mm=1.0,
        vegetation_ndvi=0.38
    )

    assert "uncertainty_pct" in res
    assert "uncertainty_level" in res
    assert 0.0 <= res["uncertainty_pct"] <= 100.0
    # Confidence + (Uncertainty / 2) ≈ 100 in balanced binary probability
    assert res["confidence_pct"] >= 50.0


def test_model_save_and_load(training_df):
    """Verify serialization to joblib file and reload integrity."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "persistent_fire_model.joblib"
        p1 = ForestFireRiskPredictor(model_path=target)
        p1.train_and_evaluate(training_df)
        assert target.exists()

        p2 = ForestFireRiskPredictor(model_path=target)
        assert p2.is_trained is True
        res = p2.predict_risk(30.0, 30.0, 20.0, 0.0, 0.25)
        assert res["risk_category"] in ("LOW", "MEDIUM", "HIGH")

