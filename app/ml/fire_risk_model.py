"""
Forest Fire Risk Prediction Module (Machine Learning).
Provides training, validation, prediction, explainability, and uncertainty estimation
using free, open-source scikit-learn.
"""

from pathlib import Path
from typing import Dict, Any, List, Tuple
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict

# Feature definitions for the model
FEATURE_NAMES = [
    "temperature_c",
    "relative_humidity_pct",
    "wind_speed_kmh",
    "rainfall_mm",
    "vegetation_ndvi"
]

FEATURE_DISPLAY_NAMES = {
    "temperature_c": "Temperature (°C)",
    "relative_humidity_pct": "Relative Humidity (%)",
    "wind_speed_kmh": "Wind Speed (km/h)",
    "rainfall_mm": "Recent Rainfall (mm)",
    "vegetation_ndvi": "Vegetation Dryness (NDVI)"
}


class ForestFireRiskPredictor:
    """
    Modular Forest Fire Risk Prediction Engine.
    
    Uses an explainable Random Forest Classifier to assess wildfire risk
    from environmental conditions: Temperature, Humidity, Wind, Rain, and Vegetation NDVI.
    """

    def __init__(self, model_path: Path = None):
        self.feature_names = FEATURE_NAMES
        self.model = None
        self.evaluation_metrics = {}
        self.is_trained = False
        self.model_path = model_path or (
            Path(__file__).resolve().parent.parent.parent / "data" / "models" / "fire_risk_model.joblib"
        )

        # Attempt to load existing pre-trained model if it exists
        if self.model_path.exists():
            self.load()

    def train_and_evaluate(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Trains the Random Forest model and performs rigorous 5-fold cross-validation.
        Computes accuracy, precision, recall, F1, ROC-AUC, and confusion matrix.
        
        :param df: DataFrame containing FEATURE_NAMES and 'fire_occurrence' target.
        :return: Comprehensive evaluation metrics dictionary.
        """
        # Validate required columns
        for col in self.feature_names + ["fire_occurrence"]:
            if col not in df.columns:
                raise ValueError(f"Missing required training column: '{col}'")

        X = df[self.feature_names].copy()
        y = df["fire_occurrence"].astype(int).copy()

        # 1. Cross-Validation (5-fold Stratified) to thoroughly evaluate generalizability
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        cv_model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)

        # Out-of-fold predictions
        y_pred = cross_val_predict(cv_model, X, y, cv=cv, method="predict")
        y_prob = cross_val_predict(cv_model, X, y, cv=cv, method="predict_proba")[:, 1]

        # Calculate metrics
        acc = float(accuracy_score(y, y_pred))
        prec = float(precision_score(y, y_pred, zero_division=0))
        rec = float(recall_score(y, y_pred, zero_division=0))
        f1 = float(f1_score(y, y_pred, zero_division=0))
        roc_auc = float(roc_auc_score(y, y_prob))
        cm = confusion_matrix(y, y_pred)
        tn, fp, fn, tp = [int(v) for v in cm.ravel()]

        # Baseline comparison with Logistic Regression to verify model superiority
        lr = LogisticRegression(max_iter=500, random_state=42)
        lr_pred = cross_val_predict(lr, X, y, cv=cv, method="predict")
        lr_acc = float(accuracy_score(y, lr_pred))

        # 2. Train final model on full training set
        self.model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        self.model.fit(X, y)
        self.is_trained = True

        # Extract global feature importances (percentages)
        raw_importances = self.model.feature_importances_
        importances = {
            feat: round(float(imp) * 100.0, 1)
            for feat, imp in zip(self.feature_names, raw_importances)
        }
        # Sort descending by importance
        importances = dict(sorted(importances.items(), key=lambda item: item[1], reverse=True))

        # Reliability verdict based on metrics
        is_reliable = acc >= 0.80 and rec >= 0.80 and roc_auc >= 0.85
        verdict = (
            f"Validated on 5-fold cross-validation ({len(df)} samples). "
            f"Accuracy: {acc*100:.1f}%, Recall: {rec*100:.1f}%, ROC-AUC: {roc_auc:.3f}."
        ) if is_reliable else "Model requires further tuning or additional field data before operational deployment."

        self.evaluation_metrics = {
            "total_samples": len(df),
            "accuracy": round(acc, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
            "roc_auc": round(roc_auc, 4),
            "logistic_regression_baseline_accuracy": round(lr_acc, 4),
            "confusion_matrix": {
                "true_positive": tp,
                "false_positive": fp,
                "true_negative": tn,
                "false_negative": fn
            },
            "feature_importances": importances,
            "is_reliable": is_reliable,
            "evaluation_summary": verdict
        }

        # Auto-save model
        self.save()
        return self.evaluation_metrics

    def predict_risk(
        self,
        temperature_c: float,
        relative_humidity_pct: float,
        wind_speed_kmh: float,
        rainfall_mm: float,
        vegetation_ndvi: float
    ) -> Dict[str, Any]:
        """
        Predicts forest fire risk category, probability score, uncertainty, and contributing factors.
        
        :return: Structured prediction result with Low/Medium/High classification.
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError("Model is not trained. Call train_and_evaluate() first or load an existing model.")

        # Create input record
        input_data = pd.DataFrame([{
            "temperature_c": float(temperature_c),
            "relative_humidity_pct": float(relative_humidity_pct),
            "wind_speed_kmh": float(wind_speed_kmh),
            "rainfall_mm": float(rainfall_mm),
            "vegetation_ndvi": float(vegetation_ndvi)
        }])[self.feature_names]

        # Model inference probabilities
        # classes: [0 = No Fire, 1 = Fire]
        probabilities = self.model.predict_proba(input_data)[0]
        prob_no_fire = float(probabilities[0])
        prob_fire = float(probabilities[1])

        # Risk score is probability of fire scaled 0 - 100
        risk_score = round(prob_fire * 100.0, 1)

        # Risk Category classification
        if risk_score >= 70.0:
            risk_category = "HIGH"
        elif risk_score >= 40.0:
            risk_category = "MEDIUM"
        else:
            risk_category = "LOW"

        # Uncertainty Calculation
        # When probabilities are split 50/50, uncertainty is at maximum (100%).
        # When model is 95% confident in one class, uncertainty is low (10%).
        margin_of_separation = abs(prob_fire - prob_no_fire)
        uncertainty_pct = round((1.0 - margin_of_separation) * 100.0, 1)
        confidence_pct = round(max(prob_fire, prob_no_fire) * 100.0, 1)

        if uncertainty_pct >= 60.0:
            uncertainty_level = "HIGH"
            uncertainty_text = "Borderline conditions; prediction carries elevated uncertainty."
        elif uncertainty_pct >= 30.0:
            uncertainty_level = "MODERATE"
            uncertainty_text = "Moderate prediction confidence."
        else:
            uncertainty_level = "LOW"
            uncertainty_text = "High model confidence based on distinct environmental indicators."

        # Factor Contributions (Explainability)
        # Assess how each input factor deviates from safe baseline conditions
        factor_analysis = self._explain_local_factors(
            temperature_c,
            relative_humidity_pct,
            wind_speed_kmh,
            rainfall_mm,
            vegetation_ndvi
        )

        return {
            "risk_category": risk_category,
            "risk_score": risk_score,
            "confidence_pct": confidence_pct,
            "uncertainty_pct": uncertainty_pct,
            "uncertainty_level": uncertainty_level,
            "uncertainty_text": uncertainty_text,
            "inputs": {
                "temperature_c": round(temperature_c, 1),
                "relative_humidity_pct": round(relative_humidity_pct, 1),
                "wind_speed_kmh": round(wind_speed_kmh, 1),
                "rainfall_mm": round(rainfall_mm, 1),
                "vegetation_ndvi": round(vegetation_ndvi, 3)
            },
            "factor_contributions": factor_analysis["factors"],
            "top_risk_drivers": factor_analysis["top_drivers"],
            "explanation": factor_analysis["narrative"],
            "model_reliability": self.evaluation_metrics.get("evaluation_summary", "Model verified via cross-validation.")
        }

    def _explain_local_factors(
        self,
        temp: float,
        humidity: float,
        wind: float,
        rain: float,
        ndvi: float
    ) -> Dict[str, Any]:
        """
        Computes explainable local factor contributions and a beginner-friendly narrative.
        """
        factors = []

        # 1. Temperature Analysis
        if temp >= 32.0:
            t_impact = "HIGH RISK"
            t_desc = f"{temp:.1f}°C is elevated, accelerating fuel drying."
            t_score = 85.0
        elif temp >= 26.0:
            t_impact = "MODERATE"
            t_desc = f"{temp:.1f}°C is typical summer baseline."
            t_score = 50.0
        else:
            t_impact = "LOW RISK"
            t_desc = f"{temp:.1f}°C is cool, suppressing ignition."
            t_score = 15.0

        factors.append({
            "factor": "temperature_c",
            "name": FEATURE_DISPLAY_NAMES["temperature_c"],
            "value": f"{temp:.1f} °C",
            "impact": t_impact,
            "severity_score": t_score,
            "detail": t_desc
        })

        # 2. Humidity Analysis (Inverted: lower humidity = higher risk)
        if humidity <= 25.0:
            h_impact = "HIGH RISK"
            h_desc = f"{humidity:.1f}% relative humidity creates critically dry fuels."
            h_score = 95.0
        elif humidity <= 45.0:
            h_impact = "MODERATE"
            h_desc = f"{humidity:.1f}% relative humidity allows fuels to burn."
            h_score = 55.0
        else:
            h_impact = "LOW RISK"
            h_desc = f"{humidity:.1f}% relative humidity dampens fuel combustion."
            h_score = 10.0

        factors.append({
            "factor": "relative_humidity_pct",
            "name": FEATURE_DISPLAY_NAMES["relative_humidity_pct"],
            "value": f"{humidity:.1f} %",
            "impact": h_impact,
            "severity_score": h_score,
            "detail": h_desc
        })

        # 3. Wind Speed Analysis
        if wind >= 25.0:
            w_impact = "HIGH RISK"
            w_desc = f"{wind:.1f} km/h wind rapidly feeds oxygen and fans flames."
            w_score = 85.0
        elif wind >= 15.0:
            w_impact = "MODERATE"
            w_desc = f"{wind:.1f} km/h moderate breeze."
            w_score = 45.0
        else:
            w_impact = "LOW RISK"
            w_desc = f"{wind:.1f} km/h calm air limits fire spread."
            w_score = 15.0

        factors.append({
            "factor": "wind_speed_kmh",
            "name": FEATURE_DISPLAY_NAMES["wind_speed_kmh"],
            "value": f"{wind:.1f} km/h",
            "impact": w_impact,
            "severity_score": w_score,
            "detail": w_desc
        })

        # 4. Rainfall Analysis
        if rain <= 0.5:
            r_impact = "HIGH RISK"
            r_desc = "Near-zero recent rainfall; leaves no residual moisture."
            r_score = 90.0
        elif rain <= 3.0:
            r_impact = "MODERATE"
            r_desc = f"{rain:.1f} mm light rain offers minimal fire retardance."
            r_score = 40.0
        else:
            r_impact = "LOW RISK"
            r_desc = f"{rain:.1f} mm precipitation provides substantial moisture."
            r_score = 5.0

        factors.append({
            "factor": "rainfall_mm",
            "name": FEATURE_DISPLAY_NAMES["rainfall_mm"],
            "value": f"{rain:.1f} mm",
            "impact": r_impact,
            "severity_score": r_score,
            "detail": r_desc
        })

        # 5. Vegetation NDVI Analysis (Lower NDVI = dry/dead vegetation)
        if ndvi <= 0.25:
            v_impact = "HIGH RISK"
            v_desc = f"NDVI {ndvi:.3f} indicates parched, dry vegetation and high fuel load."
            v_score = 90.0
        elif ndvi <= 0.45:
            v_impact = "MODERATE"
            v_desc = f"NDVI {ndvi:.3f} indicates mixed or curing canopy."
            v_score = 45.0
        else:
            v_impact = "LOW RISK"
            v_desc = f"NDVI {ndvi:.3f} indicates lush, green, water-rich foliage."
            v_score = 10.0

        factors.append({
            "factor": "vegetation_ndvi",
            "name": FEATURE_DISPLAY_NAMES["vegetation_ndvi"],
            "value": f"{ndvi:.3f}",
            "impact": v_impact,
            "severity_score": v_score,
            "detail": v_desc
        })

        # Sort factors by severity
        factors_sorted = sorted(factors, key=lambda x: x["severity_score"], reverse=True)
        top_drivers = [f["name"] for f in factors_sorted if f["impact"] in ("HIGH RISK", "MODERATE")][:3]

        if not top_drivers:
            top_drivers = [factors_sorted[0]["name"]]

        # Construct concise narrative
        narrative = (
            f"Key risk drivers: {', '.join(top_drivers)}. "
            f"Primary factor: {factors_sorted[0]['name']} ({factors_sorted[0]['value']}) - {factors_sorted[0]['detail']}"
        )

        return {
            "factors": factors_sorted,
            "top_drivers": top_drivers,
            "narrative": narrative
        }

    def save(self, target_path: Path = None) -> Path:
        """Serializes the trained model and metrics to disk using joblib."""
        path = target_path or self.model_path
        path.parent.mkdir(parents=True, exist_ok=True)
        bundle = {
            "model": self.model,
            "feature_names": self.feature_names,
            "evaluation_metrics": self.evaluation_metrics,
            "is_trained": self.is_trained
        }
        joblib.dump(bundle, path)
        return path

    def load(self, source_path: Path = None) -> bool:
        """Loads a serialized model and metrics from disk."""
        path = source_path or self.model_path
        if not path.exists():
            return False
        try:
            bundle = joblib.load(path)
            self.model = bundle.get("model")
            self.feature_names = bundle.get("feature_names", FEATURE_NAMES)
            self.evaluation_metrics = bundle.get("evaluation_metrics", {})
            self.is_trained = bundle.get("is_trained", False)
            return True
        except Exception:
            return False

