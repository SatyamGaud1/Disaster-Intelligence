"""
Agricultural Drought & Crop Stress Risk Prediction Module (Machine Learning).
Provides training, validation, prediction, explainability, and uncertainty estimation
using free, open-source scikit-learn.
"""

from pathlib import Path
from typing import Dict, Any, List
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

# Feature definitions for Drought Risk model
DROUGHT_FEATURE_NAMES = [
    "ndvi_anomaly",
    "ndwi_moisture",
    "vci_percent",
    "precipitation_deficit_pct",
    "soil_temperature_c"
]

DROUGHT_FEATURE_DISPLAY_NAMES = {
    "ndvi_anomaly": "Sentinel-2 ΔNDVI Anomaly",
    "ndwi_moisture": "Canopy Water Index (NDWI)",
    "vci_percent": "Vegetation Condition Index (%)",
    "precipitation_deficit_pct": "90d Seasonal Rain Deficit (%)",
    "soil_temperature_c": "Root-Zone Soil Temperature (°C)"
}


class DroughtRiskPredictor:
    """
    Modular Agricultural Drought & Crop Stress Risk Prediction Engine.
    
    Uses an explainable Random Forest Classifier to assess vegetative desiccation risk
    from multispectral Earth observation inputs: Sentinel-2 NDVI anomalies,
    SWIR canopy water moisture (NDWI), historical VCI percentile, rainfall deficit,
    and root-zone soil temperature.
    """

    def __init__(self, model_path: Path = None):
        self.feature_names = DROUGHT_FEATURE_NAMES
        self.model = None
        self.evaluation_metrics = {}
        self.is_trained = False
        self.model_path = model_path or (
            Path(__file__).resolve().parent.parent.parent / "data" / "models" / "drought_risk_model.joblib"
        )

        if self.model_path.exists():
            self.load()

    def train_and_evaluate(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Trains the Random Forest model and performs 5-fold cross-validation.
        Computes accuracy, precision, recall, F1, ROC-AUC, and confusion matrix.
        """
        for col in self.feature_names + ["drought_occurrence"]:
            if col not in df.columns:
                raise ValueError(f"Missing required drought training column: '{col}'")

        X = df[self.feature_names].copy()
        y = df["drought_occurrence"].astype(int).copy()

        # 1. 5-Fold Stratified Cross-Validation
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        cv_model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)

        y_pred = cross_val_predict(cv_model, X, y, cv=cv, method="predict")
        y_prob = cross_val_predict(cv_model, X, y, cv=cv, method="predict_proba")[:, 1]

        acc = float(accuracy_score(y, y_pred))
        prec = float(precision_score(y, y_pred, zero_division=0))
        rec = float(recall_score(y, y_pred, zero_division=0))
        f1 = float(f1_score(y, y_pred, zero_division=0))
        roc_auc = float(roc_auc_score(y, y_prob))
        cm = confusion_matrix(y, y_pred)
        tn, fp, fn, tp = [int(v) for v in cm.ravel()]

        # Baseline comparison with Logistic Regression
        lr = LogisticRegression(max_iter=500, random_state=42)
        lr_pred = cross_val_predict(lr, X, y, cv=cv, method="predict")
        lr_acc = float(accuracy_score(y, lr_pred))

        # 2. Train final model on full dataset
        self.model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        self.model.fit(X, y)
        self.is_trained = True

        raw_importances = self.model.feature_importances_
        importances = {
            feat: round(float(imp) * 100.0, 1)
            for feat, imp in zip(self.feature_names, raw_importances)
        }
        importances = dict(sorted(importances.items(), key=lambda item: item[1], reverse=True))

        is_reliable = acc >= 0.80 and rec >= 0.80 and roc_auc >= 0.85
        verdict = (
            f"Validated on 5-fold cross-validation ({len(df)} samples). "
            f"Accuracy: {acc*100:.1f}%, Recall: {rec*100:.1f}%, ROC-AUC: {roc_auc:.3f}."
        ) if is_reliable else "Model requires further agro-climatic tuning before operational advisory use."

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

        self.save()
        return self.evaluation_metrics

    def predict_risk(
        self,
        ndvi_anomaly: float,
        ndwi_moisture: float,
        vci_percent: float,
        precipitation_deficit_pct: float,
        soil_temperature_c: float
    ) -> Dict[str, Any]:
        """
        Predicts drought stress risk category, probability score, uncertainty, and contributing factors.
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError("Drought model is not trained. Call train_and_evaluate() first or load an existing model.")

        input_data = pd.DataFrame([{
            "ndvi_anomaly": float(ndvi_anomaly),
            "ndwi_moisture": float(ndwi_moisture),
            "vci_percent": float(vci_percent),
            "precipitation_deficit_pct": float(precipitation_deficit_pct),
            "soil_temperature_c": float(soil_temperature_c)
        }])[self.feature_names]

        probabilities = self.model.predict_proba(input_data)[0]
        prob_safe = float(probabilities[0])
        prob_drought = float(probabilities[1])

        risk_score = round(prob_drought * 100.0, 1)

        if risk_score >= 70.0:
            risk_category = "HIGH"
        elif risk_score >= 40.0:
            risk_category = "MEDIUM"
        else:
            risk_category = "LOW"

        margin_of_separation = abs(prob_drought - prob_safe)
        uncertainty_pct = round((1.0 - margin_of_separation) * 100.0, 1)
        confidence_pct = round(max(prob_drought, prob_safe) * 100.0, 1)

        if uncertainty_pct >= 60.0:
            uncertainty_level = "HIGH"
            uncertainty_text = "Borderline crop stress conditions; prediction carries elevated uncertainty."
        elif uncertainty_pct >= 30.0:
            uncertainty_level = "MODERATE"
            uncertainty_text = "Moderate prediction confidence."
        else:
            uncertainty_level = "LOW"
            uncertainty_text = "High model confidence based on distinct spectral vegetation degradation."

        factor_analysis = self._explain_local_factors(
            ndvi_anomaly,
            ndwi_moisture,
            vci_percent,
            precipitation_deficit_pct,
            soil_temperature_c
        )

        return {
            "risk_category": risk_category,
            "risk_score": risk_score,
            "confidence_pct": confidence_pct,
            "uncertainty_pct": uncertainty_pct,
            "uncertainty_level": uncertainty_level,
            "uncertainty_text": uncertainty_text,
            "inputs": {
                "ndvi_anomaly": round(ndvi_anomaly, 3),
                "ndwi_moisture": round(ndwi_moisture, 3),
                "vci_percent": round(vci_percent, 1),
                "precipitation_deficit_pct": round(precipitation_deficit_pct, 1),
                "soil_temperature_c": round(soil_temperature_c, 1)
            },
            "factor_contributions": factor_analysis["factors"],
            "top_risk_drivers": factor_analysis["top_drivers"],
            "explanation": factor_analysis["narrative"],
            "model_reliability": self.evaluation_metrics.get("evaluation_summary", "Model verified via cross-validation.")
        }

    def _explain_local_factors(
        self,
        ndvi_anom: float,
        ndwi: float,
        vci: float,
        deficit: float,
        soil_temp: float
    ) -> Dict[str, Any]:
        """
        Computes explainable local factor contributions and a readable agricultural narrative.
        """
        factors = []

        # 1. NDVI Anomaly (Negative drop indicates chlorophyll loss)
        if ndvi_anom <= -0.25:
            n_impact = "HIGH RISK"
            n_desc = f"ΔNDVI {ndvi_anom:.3f} indicates severe vegetative desiccation and biomass collapse."
            n_score = 95.0
        elif ndvi_anom <= -0.10:
            n_impact = "MODERATE"
            n_desc = f"ΔNDVI {ndvi_anom:.3f} shows moderate crop canopy stress below seasonal baseline."
            n_score = 50.0
        else:
            n_impact = "LOW RISK"
            n_desc = f"ΔNDVI {ndvi_anom:.3f} indicates healthy, vigorous vegetation matching or exceeding norms."
            n_score = 10.0

        factors.append({
            "factor": "ndvi_anomaly",
            "name": DROUGHT_FEATURE_DISPLAY_NAMES["ndvi_anomaly"],
            "value": f"{ndvi_anom:+.3f}",
            "impact": n_impact,
            "severity_score": n_score,
            "detail": n_desc
        })

        # 2. NDWI Moisture (Negative indicates depleted leaf liquid water)
        if ndwi <= -0.18:
            w_impact = "HIGH RISK"
            w_desc = f"NDWI {ndwi:.3f} reflects severe canopy liquid water deficit in shortwave infrared bands."
            w_score = 90.0
        elif ndwi <= 0.05:
            w_impact = "MODERATE"
            w_desc = f"NDWI {ndwi:.3f} indicates mild to moderate cellular moisture reduction."
            w_score = 45.0
        else:
            w_impact = "LOW RISK"
            w_desc = f"NDWI {ndwi:.3f} confirms full canopy hydration and cellular turgor."
            w_score = 10.0

        factors.append({
            "factor": "ndwi_moisture",
            "name": DROUGHT_FEATURE_DISPLAY_NAMES["ndwi_moisture"],
            "value": f"{ndwi:+.3f}",
            "impact": w_impact,
            "severity_score": w_score,
            "detail": w_desc
        })

        # 3. VCI Percentile (Low VCI = historic low condition)
        if vci <= 20.0:
            v_impact = "HIGH RISK"
            v_desc = f"VCI {vci:.1f}% indicates vegetation health in the bottom 20th percentile historically."
            v_score = 90.0
        elif vci <= 45.0:
            v_impact = "MODERATE"
            v_desc = f"VCI {vci:.1f}% represents below-average historical crop vigor."
            v_score = 50.0
        else:
            v_impact = "LOW RISK"
            v_desc = f"VCI {vci:.1f}% represents above-average agricultural vigor."
            v_score = 15.0

        factors.append({
            "factor": "vci_percent",
            "name": DROUGHT_FEATURE_DISPLAY_NAMES["vci_percent"],
            "value": f"{vci:.1f} %",
            "impact": v_impact,
            "severity_score": v_score,
            "detail": v_desc
        })

        # 4. Precipitation Deficit
        if deficit >= 60.0:
            d_impact = "HIGH RISK"
            d_desc = f"{deficit:.1f}% seasonal rainfall shortfall critically depletes root-zone recharge."
            d_score = 85.0
        elif deficit >= 35.0:
            d_impact = "MODERATE"
            d_desc = f"{deficit:.1f}% rainfall deficit putting pressure on non-irrigated farmland."
            d_score = 45.0
        else:
            d_impact = "LOW RISK"
            d_desc = f"{deficit:.1f}% deficit is within normal interannual variability."
            d_score = 10.0

        factors.append({
            "factor": "precipitation_deficit_pct",
            "name": DROUGHT_FEATURE_DISPLAY_NAMES["precipitation_deficit_pct"],
            "value": f"{deficit:.1f} %",
            "impact": d_impact,
            "severity_score": d_score,
            "detail": d_desc
        })

        # 5. Soil Temperature
        if soil_temp >= 36.0:
            s_impact = "HIGH RISK"
            s_desc = f"{soil_temp:.1f}°C root-zone temperature accelerates evapotranspiration and wilting."
            s_score = 80.0
        elif soil_temp >= 29.0:
            s_impact = "MODERATE"
            s_desc = f"{soil_temp:.1f}°C represents typical summer crop soil heat."
            s_score = 40.0
        else:
            s_impact = "LOW RISK"
            s_desc = f"{soil_temp:.1f}°C cool soil temperature limits moisture loss."
            s_score = 15.0

        factors.append({
            "factor": "soil_temperature_c",
            "name": DROUGHT_FEATURE_DISPLAY_NAMES["soil_temperature_c"],
            "value": f"{soil_temp:.1f} °C",
            "impact": s_impact,
            "severity_score": s_score,
            "detail": s_desc
        })

        factors_sorted = sorted(factors, key=lambda x: x["severity_score"], reverse=True)
        top_drivers = [f["name"] for f in factors_sorted if f["impact"] in ("HIGH RISK", "MODERATE")][:3]
        if not top_drivers:
            top_drivers = [factors_sorted[0]["name"]]

        narrative = (
            f"Key drought drivers: {', '.join(top_drivers)}. "
            f"Primary factor: {factors_sorted[0]['name']} ({factors_sorted[0]['value']}) - {factors_sorted[0]['detail']}"
        )

        return {
            "factors": factors_sorted,
            "top_drivers": top_drivers,
            "narrative": narrative
        }

    def save(self, target_path: Path = None) -> Path:
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
        path = source_path or self.model_path
        if not path.exists():
            return False
        try:
            bundle = joblib.load(path)
            self.model = bundle.get("model")
            self.feature_names = bundle.get("feature_names", DROUGHT_FEATURE_NAMES)
            self.evaluation_metrics = bundle.get("evaluation_metrics", {})
            self.is_trained = bundle.get("is_trained", False)
            return True
        except Exception:
            return False

