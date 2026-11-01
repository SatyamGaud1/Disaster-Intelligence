"""
Unit and integration tests for Agricultural Drought Risk Prediction ML Engine.
Verifies training, 5-fold cross-validation metrics, predictions, uncertainty estimation,
explainability, and persistence.
"""

from pathlib import Path
import tempfile
import pytest
import pandas as pd
from app.ml.drought_risk_model import DroughtRiskPredictor
from app.ml.create_drought_dataset import generate_drought_benchmark_dataset


@pytest.fixture(scope="module")
def drought_training_df():
    """Generates a temporary benchmark drought training dataset."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_path = Path(tmp_dir) / "test_drought_dataset.csv"
        generate_drought_benchmark_dataset(output_path=csv_path, n_samples=200, seed=42)
        yield pd.read_csv(csv_path)


@pytest.fixture(scope="module")
def trained_drought_predictor(drought_training_df):
    """Provides an in-memory trained drought predictor instance."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        model_path = Path(tmp_dir) / "test_drought_model.joblib"
        predictor = DroughtRiskPredictor(model_path=model_path)
        predictor.train_and_evaluate(drought_training_df)
        yield predictor


def test_drought_model_training_and_metrics(drought_training_df):
    """Verify that training computes rigorous 5-fold cross-validation evaluation metrics."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        model_path = Path(tmp_dir) / "model_metrics_drought_test.joblib"
        predictor = DroughtRiskPredictor(model_path=model_path)
        metrics = predictor.train_and_evaluate(drought_training_df)

        assert metrics["total_samples"] == len(drought_training_df)
        assert metrics["accuracy"] >= 0.85
        assert metrics["recall"] >= 0.85
        assert metrics["roc_auc"] >= 0.90

        cm = metrics["confusion_matrix"]
        assert cm["true_positive"] + cm["false_positive"] + cm["true_negative"] + cm["false_negative"] == len(drought_training_df)

        importances = metrics["feature_importances"]
        assert len(importances) == 5
        assert "ndvi_anomaly" in importances
        assert "ndwi_moisture" in importances


def test_high_drought_risk_prediction(trained_drought_predictor):
    """Test severe NDVI drop, negative NDWI, low VCI, and high rain deficit yields HIGH risk category."""
    res = trained_drought_predictor.predict_risk(
        ndvi_anomaly=-0.35,
        ndwi_moisture=-0.28,
        vci_percent=14.0,
        precipitation_deficit_pct=78.0,
        soil_temperature_c=41.0
    )

    assert res["risk_category"] == "HIGH"
    assert res["risk_score"] >= 70.0
    assert "factor_contributions" in res
    assert len(res["factor_contributions"]) == 5
    assert len(res["top_risk_drivers"]) > 0
    assert "explanation" in res


def test_low_drought_risk_prediction(trained_drought_predictor):
    """Test positive NDVI, positive NDWI, high VCI, minimal deficit yields LOW risk category."""
    res = trained_drought_predictor.predict_risk(
        ndvi_anomaly=0.08,
        ndwi_moisture=0.22,
        vci_percent=78.0,
        precipitation_deficit_pct=15.0,
        soil_temperature_c=24.0
    )

    assert res["risk_category"] == "LOW"
    assert res["risk_score"] < 40.0


def test_borderline_drought_uncertainty(trained_drought_predictor):
    """Verify uncertainty metric on borderline vegetative stress conditions."""
    res = trained_drought_predictor.predict_risk(
        ndvi_anomaly=-0.14,
        ndwi_moisture=-0.04,
        vci_percent=42.0,
        precipitation_deficit_pct=42.0,
        soil_temperature_c=31.0
    )

    assert "uncertainty_pct" in res
    assert "uncertainty_level" in res
    assert 0.0 <= res["uncertainty_pct"] <= 100.0


def test_drought_model_save_and_load(drought_training_df):
    """Verify serialization to joblib file and reload integrity."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "persistent_drought_model.joblib"
        p1 = DroughtRiskPredictor(model_path=target)
        p1.train_and_evaluate(drought_training_df)
        assert target.exists()

        p2 = DroughtRiskPredictor(model_path=target)
        assert p2.is_trained is True
        res = p2.predict_risk(-0.30, -0.20, 18.0, 70.0, 39.0)
        assert res["risk_category"] in ("LOW", "MEDIUM", "HIGH")

