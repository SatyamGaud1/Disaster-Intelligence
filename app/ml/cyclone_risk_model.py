"""
Cyclone Meteorological Risk Prediction Module (Machine Learning).
Provides training, validation, prediction, explainability, and uncertainty estimation
using free, open-source scikit-learn based on NOAA / IBTrACS and IMD atmospheric standards.
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

# Feature definitions for Cyclone Risk model
CYCLONE_FEATURE_NAMES = [
    "central_pressure_hpa",
    "max_sustained_wind_kmh",
    "sea_surface_temp_c",
    "storm_forward_speed_kmh",
    "coastal_distance_km"
]

CYCLONE_FEATURE_DISPLAY_NAMES = {
    "central_pressure_hpa": "Central Barometric Pressure (hPa)",
    "max_sustained_wind_kmh": "Max Sustained Wind (km/h)",
    "sea_surface_temp_c": "Sea Surface Temperature (°C)",
    "storm_forward_speed_kmh": "Forward Speed / Translation (km/h)",
    "coastal_distance_km": "Distance to Coastline (km)"
}


class CycloneRiskPredictor:
    """
    Modular Tropical Cyclone & Coastal Hazard Risk Prediction Engine.
    
    Uses an explainable Random Forest Classifier to assess severe storm threat
    from meteorological and oceanographic inputs: central barometric pressure,
    peak sustained wind velocity, sea surface thermal energy, storm forward speed,
    and coastline proximity.
    """

    def __init__(self, model_path: Path = None):
        self.feature_names = CYCLONE_FEATURE_NAMES
        self.model = None
        self.evaluation_metrics = {}
        self.is_trained = False
        self.model_path = model_path or (
            Path(__file__).resolve().parent.parent.parent / "data" / "models" / "cyclone_risk_model.joblib"
        )

        if self.model_path.exists():
            self.load()

    def train_and_evaluate(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Trains the Random Forest model and performs 5-fold cross-validation.
        Computes accuracy, precision, recall, F1, ROC-AUC, and confusion matrix.
        """
        for col in self.feature_names + ["cyclone_severe_risk"]:
            if col not in df.columns:
                raise ValueError(f"Missing required cyclone training column: '{col}'")

        X = df[self.feature_names].copy()
        y = df["cyclone_severe_risk"].astype(int).copy()

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
        ) if is_reliable else "Model requires further meteorological calibration."

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
        central_pressure_hpa: float,
        max_sustained_wind_kmh: float,
        sea_surface_temp_c: float,
        storm_forward_speed_kmh: float,
        coastal_distance_km: float
    ) -> Dict[str, Any]:
        """
        Predicts cyclone risk category, probability score, uncertainty, and contributing factors.
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError("Cyclone model is not trained. Call train_and_evaluate() first or load an existing model.")

        input_data = pd.DataFrame([{
            "central_pressure_hpa": float(central_pressure_hpa),
            "max_sustained_wind_kmh": float(max_sustained_wind_kmh),
            "sea_surface_temp_c": float(sea_surface_temp_c),
            "storm_forward_speed_kmh": float(storm_forward_speed_kmh),
            "coastal_distance_km": float(coastal_distance_km)
        }])[self.feature_names]

        probabilities = self.model.predict_proba(input_data)[0]
        prob_safe = float(probabilities[0])
        prob_severe = float(probabilities[1])

        risk_score = round(prob_severe * 100.0, 1)

        if risk_score >= 70.0:
            risk_category = "HIGH"
        elif risk_score >= 40.0:
            risk_category = "MEDIUM"
        else:
            risk_category = "LOW"

        margin_of_separation = abs(prob_severe - prob_safe)
        uncertainty_pct = round((1.0 - margin_of_separation) * 100.0, 1)
        confidence_pct = round(max(prob_severe, prob_safe) * 100.0, 1)

        if uncertainty_pct >= 60.0:
            uncertainty_level = "HIGH"
            uncertainty_text = "Borderline meteorological conditions; prediction carries elevated uncertainty."
        elif uncertainty_pct >= 30.0:
            uncertainty_level = "MODERATE"
            uncertainty_text = "Moderate prediction confidence."
        else:
            uncertainty_level = "LOW"
            uncertainty_text = "High model confidence based on distinct barometric & wind gradient signatures."

        classifications = self.classify_cyclone_intensity(max_sustained_wind_kmh, central_pressure_hpa)

        factor_analysis = self._explain_local_factors(
            central_pressure_hpa,
            max_sustained_wind_kmh,
            sea_surface_temp_c,
            storm_forward_speed_kmh,
            coastal_distance_km
        )

        return {
            "risk_category": risk_category,
            "risk_score": risk_score,
            "confidence_pct": confidence_pct,
            "uncertainty_pct": uncertainty_pct,
            "uncertainty_level": uncertainty_level,
            "uncertainty_text": uncertainty_text,
            "classifications": classifications,
            "inputs": {
                "central_pressure_hpa": round(central_pressure_hpa, 1),
                "max_sustained_wind_kmh": round(max_sustained_wind_kmh, 1),
                "sea_surface_temp_c": round(sea_surface_temp_c, 1),
                "storm_forward_speed_kmh": round(storm_forward_speed_kmh, 1),
                "coastal_distance_km": round(coastal_distance_km, 1)
            },
            "factor_contributions": factor_analysis["factors"],
            "top_risk_drivers": factor_analysis["top_drivers"],
            "explanation": factor_analysis["narrative"],
            "model_reliability": self.evaluation_metrics.get("evaluation_summary", "Model verified via cross-validation.")
        }

    @staticmethod
    def classify_cyclone_intensity(wind_kmh: float, pressure_hpa: float = 1000.0) -> Dict[str, str]:
        """
        Classifies tropical cyclone intensity under both NOAA Saffir-Simpson and IMD regional scales.
        """
        # 1. NOAA Saffir-Simpson (1-min sustained wind)
        if wind_kmh >= 252.0:
            saffir = "Category 5 Major Hurricane / Super Typhoon"
        elif wind_kmh >= 209.0:
            saffir = "Category 4 Major Hurricane"
        elif wind_kmh >= 178.0:
            saffir = "Category 3 Major Hurricane"
        elif wind_kmh >= 154.0:
            saffir = "Category 2 Hurricane"
        elif wind_kmh >= 119.0:
            saffir = "Category 1 Hurricane"
        elif wind_kmh >= 63.0:
            saffir = "Tropical Storm"
        else:
            saffir = "Tropical Depression"

        # 2. IMD (India Meteorological Department - 3-min / regional standard)
        if wind_kmh >= 222.0:
            imd = "Super Cyclonic Storm (SuCS)"
        elif wind_kmh >= 166.0:
            imd = "Extremely Severe Cyclonic Storm (ESCS)"
        elif wind_kmh >= 118.0:
            imd = "Very Severe Cyclonic Storm (VSCS)"
        elif wind_kmh >= 88.0:
            imd = "Severe Cyclonic Storm (SCS)"
        elif wind_kmh >= 62.0:
            imd = "Cyclonic Storm (CS)"
        elif wind_kmh >= 49.0:
            imd = "Deep Depression (DD)"
        elif wind_kmh >= 31.0:
            imd = "Depression (D)"
        else:
            imd = "Well-Marked Low Pressure Area"

        return {
            "saffir_simpson": saffir,
            "imd_scale": imd
        }

    def _explain_local_factors(
        self,
        pressure: float,
        wind: float,
        sst: float,
        speed: float,
        dist: float
    ) -> Dict[str, Any]:
        """
        Computes explainable local factor contributions and an atmospheric narrative.
        """
        factors = []

        # 1. Central Pressure
        if pressure <= 950.0:
            p_impact = "CRITICAL"
            p_desc = f"{pressure:.1f} hPa indicates extreme barometric vortex suction and intense storm core."
            p_score = 98.0
        elif pressure <= 980.0:
            p_impact = "HIGH RISK"
            p_desc = f"{pressure:.1f} hPa demonstrates strong cyclonic depression."
            p_score = 75.0
        elif pressure <= 1000.0:
            p_impact = "MODERATE"
            p_desc = f"{pressure:.1f} hPa reflects moderate cyclonic circulation."
            p_score = 45.0
        else:
            p_impact = "LOW RISK"
            p_desc = f"{pressure:.1f} hPa near normal ambient sea level pressure."
            p_score = 15.0

        factors.append({
            "factor": "central_pressure_hpa",
            "name": CYCLONE_FEATURE_DISPLAY_NAMES["central_pressure_hpa"],
            "value": f"{pressure:.1f} hPa",
            "impact": p_impact,
            "severity_score": p_score,
            "detail": p_desc
        })

        # 2. Maximum Sustained Wind
        if wind >= 165.0:
            w_impact = "CRITICAL"
            w_desc = f"{wind:.1f} km/h catastrophic winds capable of extensive structural damage."
            w_score = 95.0
        elif wind >= 118.0:
            w_impact = "HIGH RISK"
            w_desc = f"{wind:.1f} km/h hurricane-force winds producing severe marine & coastal hazard."
            w_score = 75.0
        elif wind >= 65.0:
            w_impact = "MODERATE"
            w_desc = f"{wind:.1f} km/h gale-force winds with turbulent sea conditions."
            w_score = 45.0
        else:
            w_impact = "LOW RISK"
            w_desc = f"{wind:.1f} km/h moderate breeze within standard maritime tolerances."
            w_score = 15.0

        factors.append({
            "factor": "max_sustained_wind_kmh",
            "name": CYCLONE_FEATURE_DISPLAY_NAMES["max_sustained_wind_kmh"],
            "value": f"{wind:.1f} km/h",
            "impact": w_impact,
            "severity_score": w_score,
            "detail": w_desc
        })

        # 3. Sea Surface Temperature
        if sst >= 29.5:
            s_impact = "HIGH RISK"
            s_desc = f"{sst:.1f}°C ocean warmth provides hyper-favorable thermodynamic fuel for rapid intensification."
            s_score = 85.0
        elif sst >= 28.0:
            s_impact = "MODERATE"
            s_desc = f"{sst:.1f}°C maintains sustained tropical cyclogenesis energy."
            s_score = 55.0
        else:
            s_impact = "LOW RISK"
            s_desc = f"{sst:.1f}°C marginally warm or below threshold for rapid strengthening."
            s_score = 20.0

        factors.append({
            "factor": "sea_surface_temp_c",
            "name": CYCLONE_FEATURE_DISPLAY_NAMES["sea_surface_temp_c"],
            "value": f"{sst:.1f}°C",
            "impact": s_impact,
            "severity_score": s_score,
            "detail": s_desc
        })

        # 4. Forward Speed
        if speed <= 12.0:
            sp_impact = "HIGH RISK"
            sp_desc = f"Slow translation ({speed:.1f} km/h) causes prolonged catastrophic rainfall dumping and sustained surge."
            sp_score = 75.0
        elif speed >= 35.0:
            sp_impact = "MODERATE"
            sp_desc = f"Fast moving ({speed:.1f} km/h) delivers sudden frontal impact across broad geography."
            sp_score = 50.0
        else:
            sp_impact = "MODERATE"
            sp_desc = f"Standard propagation velocity ({speed:.1f} km/h)."
            sp_score = 35.0

        factors.append({
            "factor": "storm_forward_speed_kmh",
            "name": CYCLONE_FEATURE_DISPLAY_NAMES["storm_forward_speed_kmh"],
            "value": f"{speed:.1f} km/h",
            "impact": sp_impact,
            "severity_score": sp_score,
            "detail": sp_desc
        })

        # 5. Coastal Proximity
        if dist <= 50.0:
            d_impact = "CRITICAL"
            d_desc = f"Immediate coastal proximity ({dist:.1f} km) exposes coastal settlements to imminent surge & peak winds."
            d_score = 95.0
        elif dist <= 150.0:
            d_impact = "HIGH RISK"
            d_desc = f"Within {dist:.1f} km of coastline; elevated coastal surge watch and maritime evacuation zone."
            d_score = 70.0
        elif dist <= 300.0:
            d_impact = "MODERATE"
            d_desc = f"{dist:.1f} km offshore; maritime warning area with approaching outer rainbands."
            d_score = 40.0
        else:
            d_impact = "LOW RISK"
            d_desc = f"{dist:.1f} km deep ocean position provides buffer for defensive preparations."
            d_score = 15.0

        factors.append({
            "factor": "coastal_distance_km",
            "name": CYCLONE_FEATURE_DISPLAY_NAMES["coastal_distance_km"],
            "value": f"{dist:.1f} km",
            "impact": d_impact,
            "severity_score": d_score,
            "detail": d_desc
        })

        factors.sort(key=lambda x: x["severity_score"], reverse=True)
        top_drivers = [f["name"] for f in factors[:2] if f["severity_score"] >= 50.0]

        high_factors = [f for f in factors if f["impact"] in ["CRITICAL", "HIGH RISK"]]
        if len(high_factors) >= 3:
            narrative = (
                f"Severe cyclonic danger driven primarily by {factors[0]['name'].lower()} "
                f"({factors[0]['value']}) and {factors[1]['name'].lower()} ({factors[1]['value']}). "
                f"Coastal communities should initiate cyclone shelter staging."
            )
        elif len(high_factors) >= 1:
            narrative = (
                f"Elevated cyclonic threat driven by {factors[0]['name'].lower()} ({factors[0]['value']}). "
                f"Ongoing surveillance recommended."
            )
        else:
            narrative = "Tropical system indicators remain within manageable thresholds with low coastal danger."

        return {
            "factors": factors,
            "top_drivers": top_drivers,
            "narrative": narrative
        }

    def save(self, model_path: Path = None) -> Path:
        target = model_path or self.model_path
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self.model,
            "evaluation_metrics": self.evaluation_metrics,
            "feature_names": self.feature_names,
            "is_trained": self.is_trained
        }
        joblib.dump(payload, target)
        return target

    def load(self, model_path: Path = None):
        target = model_path or self.model_path
        if not target.exists():
            raise FileNotFoundError(f"Cyclone model file not found at: {target}")

        payload = joblib.load(target)
        self.model = payload["model"]
        self.evaluation_metrics = payload.get("evaluation_metrics", {})
        self.feature_names = payload.get("feature_names", CYCLONE_FEATURE_NAMES)
        self.is_trained = payload.get("is_trained", True)

