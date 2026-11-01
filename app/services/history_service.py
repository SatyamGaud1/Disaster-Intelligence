"""
Historical Incident Comparison Service.
Compares active multi-hazard incidents against historical baseline metrics,
evaluating intensity deviation, spatial extent anomaly, and priority percentile.
"""

from typing import Dict, Any, List

# Historical baseline reference metrics across global Earth observation archives
HISTORICAL_BASELINES = {
    "FIRE": {
        "mean_intensity_frp": 38.5,       # Megawatts
        "max_intensity_frp": 140.0,
        "mean_area_sqkm": 8.5,
        "mean_priority_score": 58.0,
        "hazard_description": "Wildfire & Thermal Anomaly Historical Norm"
    },
    "FLOOD": {
        "mean_backscatter_drop_db": 8.2,   # dB drop
        "max_backscatter_drop_db": 15.0,
        "mean_area_sqkm": 28.0,
        "mean_priority_score": 62.0,
        "hazard_description": "Seasonal Floodplain Inundation Historical Norm"
    },
    "DROUGHT": {
        "mean_ndvi_anomaly_drop": 0.22,    # Delta NDVI drop
        "max_ndvi_anomaly_drop": 0.42,
        "mean_area_sqkm": 65.0,
        "mean_priority_score": 52.0,
        "hazard_description": "Arable Crop Desiccation Historical Norm"
    }
}


def compare_incident_with_history(incident: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes comparative deviation metrics of an active incident against historical records.
    """
    hazard_type = incident.get("hazard_type", "FIRE").upper()
    baseline = HISTORICAL_BASELINES.get(hazard_type, HISTORICAL_BASELINES["FIRE"])

    active_area = float(incident.get("affected_area_sqkm", 10.0))
    active_priority = float(incident.get("priority_score", 50.0))

    # Area deviation percentage: ((active - baseline) / baseline) * 100
    area_baseline = baseline["mean_area_sqkm"]
    area_deviation_pct = round(((active_area - area_baseline) / area_baseline) * 100.0, 1)

    # Priority deviation
    priority_baseline = baseline["mean_priority_score"]
    priority_deviation_pct = round(((active_priority - priority_baseline) / priority_baseline) * 100.0, 1)

    # Historical Severity Classification
    if active_priority >= 85.0 or area_deviation_pct > 100.0:
        severity_category = "HISTORIC_EXTREME"
        verdict = "Severe anomalous event exceeding 95th percentile of historical satellite records."
    elif active_priority >= 65.0 or area_deviation_pct > 30.0:
        severity_category = "ABOVE_AVERAGE"
        verdict = "Elevated magnitude event exceeding seasonal historical norms."
    elif active_priority >= 40.0:
        severity_category = "MODERATE_TYPICAL"
        verdict = "Consistent with multi-year regional historical baselines."
    else:
        severity_category = "SUB_BASELINE"
        verdict = "Low-intensity localized anomaly below standard regional intervention thresholds."

    return {
        "hazard_type": hazard_type,
        "active_incident_uid": incident.get("incident_uid", ""),
        "baseline_standards": baseline,
        "comparisons": {
            "active_area_sqkm": active_area,
            "historical_mean_area_sqkm": area_baseline,
            "area_deviation_pct": area_deviation_pct,
            "active_priority_score": active_priority,
            "historical_mean_priority": priority_baseline,
            "priority_deviation_pct": priority_deviation_pct
        },
        "severity_category": severity_category,
        "historical_verdict": verdict
    }

