"""
Flood Inundation Risk Prediction Module (Machine Learning).
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

# Feature definitions for Flood Risk model
FLOOD_FEATURE_NAMES = [
    "precipitation_24h_mm",
    "soil_moisture_pct",
    "radar_backscatter_drop_db",
    "elevation_m",
    "river_proximity_km"
]

FLOOD_FEATURE_DISPLAY_NAMES = {
    "precipitation_24h_mm": "24h Accumulated Rainfall (mm)",
    "soil_moisture_pct": "Soil Saturation Moisture (%)",
    "radar_backscatter_drop_db": "Sentinel-1 SAR Drop (dB)",
    "elevation_m": "Terrain Elevation (m)",
    "river_proximity_km": "Distance to River Basin (km)"
}


class FloodRiskPredictor:
    """
    Modular Flood Risk Prediction Engine.
    
    Uses an explainable Random Forest Classifier to assess inundation risk
    from hydrological and radar inputs: NASA GPM precipitation, soil moisture,
    Sentinel-1 SAR backscatter drop, terrain elevation, and river proximity.
    """

    def __init__(self, model_path: Path = None):
        self.feature_names = FLOOD_FEATURE_NAMES
        self.model = None
        self.evaluation_metrics = {}
        self.is_trained = False
        self.model_path = model_path or (
            Path(__file__).resolve().parent.parent.parent / "data" / "models" / "flood_risk_model.joblib"
        )

        if self.model_path.exists():
            self.load()

    def train_and_evaluate(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Trains the Random Forest model and performs 5-fold cross-validation.
        Computes accuracy, precision, recall, F1, ROC-AUC, and confusion matrix.
        """
        for col in self.feature_names + ["flood_occurrence"]:
            if col not in df.columns:
                raise ValueError(f"Missing required flood training column: '{col}'")

        X = df[self.feature_names].copy()
        y = df["flood_occurrence"].astype(int).copy()

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
        ) if is_reliable else "Model requires further tuning or additional hydrological sensor calibration."

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
        precipitation_24h_mm: float,
        soil_moisture_pct: float,
        radar_backscatter_drop_db: float,
        elevation_m: float,
        river_proximity_km: float
    ) -> Dict[str, Any]:
        """
        Predicts flood inundation risk category, probability score, uncertainty, and contributing factors.
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError("Flood model is not trained. Call train_and_evaluate() first or load an existing model.")

        input_data = pd.DataFrame([{
            "precipitation_24h_mm": float(precipitation_24h_mm),
            "soil_moisture_pct": float(soil_moisture_pct),
            "radar_backscatter_drop_db": float(radar_backscatter_drop_db),
            "elevation_m": float(elevation_m),
            "river_proximity_km": float(river_proximity_km)
        }])[self.feature_names]

        probabilities = self.model.predict_proba(input_data)[0]
        prob_safe = float(probabilities[0])
        prob_flood = float(probabilities[1])

        risk_score = round(prob_flood * 100.0, 1)

        if risk_score >= 70.0:
            risk_category = "HIGH"
        elif risk_score >= 40.0:
            risk_category = "MEDIUM"
        else:
            risk_category = "LOW"

        margin_of_separation = abs(prob_flood - prob_safe)
        uncertainty_pct = round((1.0 - margin_of_separation) * 100.0, 1)
        confidence_pct = round(max(prob_flood, prob_safe) * 100.0, 1)

        if uncertainty_pct >= 60.0:
            uncertainty_level = "HIGH"
            uncertainty_text = "Borderline hydrological conditions; prediction carries elevated uncertainty."
        elif uncertainty_pct >= 30.0:
            uncertainty_level = "MODERATE"
            uncertainty_text = "Moderate prediction confidence."
        else:
            uncertainty_level = "LOW"
            uncertainty_text = "High model confidence based on distinct radar & precipitation indicators."

        factor_analysis = self._explain_local_factors(
            precipitation_24h_mm,
            soil_moisture_pct,
            radar_backscatter_drop_db,
            elevation_m,
            river_proximity_km
        )

        return {
            "risk_category": risk_category,
            "risk_score": risk_score,
            "confidence_pct": confidence_pct,
            "uncertainty_pct": uncertainty_pct,
            "uncertainty_level": uncertainty_level,
            "uncertainty_text": uncertainty_text,
            "inputs": {
                "precipitation_24h_mm": round(precipitation_24h_mm, 1),
                "soil_moisture_pct": round(soil_moisture_pct, 1),
                "radar_backscatter_drop_db": round(radar_backscatter_drop_db, 1),
                "elevation_m": round(elevation_m, 1),
                "river_proximity_km": round(river_proximity_km, 2)
            },
            "factor_contributions": factor_analysis["factors"],
            "top_risk_drivers": factor_analysis["top_drivers"],
            "explanation": factor_analysis["narrative"],
            "model_reliability": self.evaluation_metrics.get("evaluation_summary", "Model verified via cross-validation.")
        }

    def _explain_local_factors(
        self,
        rain: float,
        soil: float,
        sar_drop: float,
        elev: float,
        dist: float
    ) -> Dict[str, Any]:
        """
        Computes explainable local factor contributions and a readable hydrological narrative.
        """
        factors = []

        # 1. Precipitation
        if rain >= 120.0:
            r_impact = "HIGH RISK"
            r_desc = f"{rain:.1f} mm torrential 24h rainfall exceeds river catchment discharge capacity."
            r_score = 95.0
        elif rain >= 50.0:
            r_impact = "MODERATE"
            r_desc = f"{rain:.1f} mm sustained rain causing elevated runoff."
            r_score = 50.0
        else:
            r_impact = "LOW RISK"
            r_desc = f"{rain:.1f} mm light precipitation well within standard drainage thresholds."
            r_score = 10.0

        factors.append({
            "factor": "precipitation_24h_mm",
            "name": FLOOD_FEATURE_DISPLAY_NAMES["precipitation_24h_mm"],
            "value": f"{rain:.1f} mm",
            "impact": r_impact,
            "severity_score": r_score,
            "detail": r_desc
        })

        # 2. Soil Moisture
        if soil >= 80.0:
            s_impact = "HIGH RISK"
            s_desc = f"{soil:.1f}% soil saturation prevents water infiltration, converting rain directly into surface runoff."
            s_score = 90.0
        elif soil >= 55.0:
            s_impact = "MODERATE"
            s_desc = f"{soil:.1f}% soil moisture with moderate infiltration buffering."
            s_score = 45.0
        else:
            s_impact = "LOW RISK"
            s_desc = f"{soil:.1f}% unsaturated soil provides high absorption capacity."
            s_score = 15.0

        factors.append({
            "factor": "soil_moisture_pct",
            "name": FLOOD_FEATURE_DISPLAY_NAMES["soil_moisture_pct"],
            "value": f"{soil:.1f} %",
            "impact": s_impact,
            "severity_score": s_score,
            "detail": s_desc
        })

        # 3. Sentinel-1 SAR Backscatter Drop
        if sar_drop >= 9.0:
            sar_impact = "HIGH RISK"
            sar_desc = f"-{sar_drop:.1f} dB radar drop signals specular reflection from open standing surface water."
            sar_score = 95.0
        elif sar_drop >= 5.0:
            sar_impact = "MODERATE"
            sar_desc = f"-{sar_drop:.1f} dB drop indicates waterlogged or saturated terrain."
            sar_score = 50.0
        else:
            sar_impact = "LOW RISK"
            sar_desc = f"-{sar_drop:.1f} dB normal terrestrial radar backscatter."
            sar_score = 15.0

        factors.append({
            "factor": "radar_backscatter_drop_db",
            "name": FLOOD_FEATURE_DISPLAY_NAMES["radar_backscatter_drop_db"],
            "value": f"-{sar_drop:.1f} dB",
            "impact": sar_impact,
            "severity_score": sar_score,
            "detail": sar_desc
        })

        # 4. Elevation (Lower elevation = higher accumulation risk)
        if elev <= 40.0:
            e_impact = "HIGH RISK"
            e_desc = f"{elev:.1f} m lowland elevation acts as a catchment collection trough."
            e_score = 80.0
        elif elev <= 120.0:
            e_impact = "MODERATE"
            e_desc = f"{elev:.1f} m moderate elevation with gradual drainage."
            e_score = 40.0
        else:
            e_impact = "LOW RISK"
            e_desc = f"{elev:.1f} m upland terrain naturally sheds gravitational runoff."
            e_score = 10.0

        factors.append({
            "factor": "elevation_m",
            "name": FLOOD_FEATURE_DISPLAY_NAMES["elevation_m"],
            "value": f"{elev:.1f} m",
            "impact": e_impact,
            "severity_score": e_score,
            "detail": e_desc
        })

        # 5. River Proximity (Closer to river = higher overtopping risk)
        if dist <= 1.5:
            d_impact = "HIGH RISK"
            d_desc = f"{dist:.2f} km proximity to main river channel exposes zone to embankment overtopping."
            d_score = 85.0
        elif dist <= 5.0:
            d_impact = "MODERATE"
            d_desc = f"{dist:.2f} km distance from river corridor in secondary floodplain."
            d_score = 45.0
        else:
            d_impact = "LOW RISK"
            d_desc = f"{dist:.2f} km distance buffered from direct fluvial overflow."
            d_score = 10.0

        factors.append({
            "factor": "river_proximity_km",
            "name": FLOOD_FEATURE_DISPLAY_NAMES["river_proximity_km"],
            "value": f"{dist:.2f} km",
            "impact": d_impact,
            "severity_score": d_score,
            "detail": d_desc
        })

        factors_sorted = sorted(factors, key=lambda x: x["severity_score"], reverse=True)
        top_drivers = [f["name"] for f in factors_sorted if f["impact"] in ("HIGH RISK", "MODERATE")][:3]
        if not top_drivers:
            top_drivers = [factors_sorted[0]["name"]]

        narrative = (
            f"Key flood drivers: {', '.join(top_drivers)}. "
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
            self.feature_names = bundle.get("feature_names", FLOOD_FEATURE_NAMES)
            self.evaluation_metrics = bundle.get("evaluation_metrics", {})
            self.is_trained = bundle.get("is_trained", False)
            return True
        except Exception:
            return False

