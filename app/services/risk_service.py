"""
Disaster Risk Prediction Service.
Connects the machine learning models to the Flask backend and provides
API-ready risk predictions, model validation metrics, and regional risk assessments.
"""

from typing import Dict, Any, List
import pandas as pd
from app.ml.fire_risk_model import ForestFireRiskPredictor
from app.ml.flood_risk_model import FloodRiskPredictor
from app.ml.drought_risk_model import DroughtRiskPredictor
from app.ml.cyclone_risk_model import CycloneRiskPredictor

# Singleton predictor instances
_fire_predictor_instance = None
_flood_predictor_instance = None
_drought_predictor_instance = None
_cyclone_predictor_instance = None


def get_fire_risk_predictor() -> ForestFireRiskPredictor:
    """
    Returns a cached instance of the ForestFireRiskPredictor.
    Initializes and trains on the reference dataset if no saved model exists.
    """
    global _fire_predictor_instance
    if _fire_predictor_instance is None:
        _fire_predictor_instance = ForestFireRiskPredictor()

        # If not trained, train on the benchmark dataset
        if not _fire_predictor_instance.is_trained:
            from pathlib import Path
            data_path = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "forest_fire_weather_dataset.csv"
            if data_path.exists():
                df = pd.read_csv(data_path)
                _fire_predictor_instance.train_and_evaluate(df)

    return _fire_predictor_instance


def get_fire_model_metrics() -> Dict[str, Any]:
    """
    Returns model validation evaluation metrics, feature importances,
    confusion matrix, and reliability status.
    """
    predictor = get_fire_risk_predictor()
    return {
        "status": "success",
        "model_type": "Random Forest Classifier (100 Trees, Max Depth 5)",
        "features": predictor.feature_names,
        "is_trained": predictor.is_trained,
        "metrics": predictor.evaluation_metrics
    }


def predict_fire_risk_from_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates input parameters and performs an explainable fire risk prediction.
    """
    predictor = get_fire_risk_predictor()

    try:
        temp = float(params.get("temperature_c", 30.0))
        humidity = float(params.get("relative_humidity_pct", 35.0))
        wind = float(params.get("wind_speed_kmh", 18.0))
        rain = float(params.get("rainfall_mm", 0.0))
        ndvi = float(params.get("vegetation_ndvi", 0.28))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid input parameter data type: {str(exc)}")

    # Range validations
    if not (-20.0 <= temp <= 65.0):
        raise ValueError("Temperature must be between -20°C and 65°C.")
    if not (0.0 <= humidity <= 100.0):
        raise ValueError("Relative humidity must be between 0% and 100%.")
    if not (0.0 <= wind <= 200.0):
        raise ValueError("Wind speed must be between 0 km/h and 200 km/h.")
    if not (0.0 <= rain <= 500.0):
        raise ValueError("Rainfall must be between 0 mm and 500 mm.")
    if not (0.0 <= ndvi <= 1.0):
        raise ValueError("Vegetation NDVI must be between 0.0 and 1.0.")

    prediction = predictor.predict_risk(
        temperature_c=temp,
        relative_humidity_pct=humidity,
        wind_speed_kmh=wind,
        rainfall_mm=rain,
        vegetation_ndvi=ndvi
    )

    return {
        "status": "success",
        "prediction": prediction
    }


def get_monitored_fire_risk_zones() -> List[Dict[str, Any]]:
    """
    Generates environmental risk assessments across key monitored wildland zones.
    Useful for displaying real-time risk gauges on the dashboard.
    """
    predictor = get_fire_risk_predictor()

    sample_zones = [
        {
            "zone_id": "ZONE-NW-01",
            "zone_name": "Northwest Pine Ridge Corridor",
            "lat": 34.22,
            "lon": -118.15,
            "weather": {
                "temperature_c": 37.2,
                "relative_humidity_pct": 16.5,
                "wind_speed_kmh": 26.0,
                "rainfall_mm": 0.0,
                "vegetation_ndvi": 0.165
            }
        },
        {
            "zone_id": "ZONE-SR-02",
            "zone_name": "Central Chaparral Basin",
            "lat": 34.18,
            "lon": -118.08,
            "weather": {
                "temperature_c": 29.5,
                "relative_humidity_pct": 38.0,
                "wind_speed_kmh": 16.5,
                "rainfall_mm": 0.8,
                "vegetation_ndvi": 0.320
            }
        },
        {
            "zone_id": "ZONE-ET-03",
            "zone_name": "Eastern Valley Reserve",
            "lat": 34.12,
            "lon": -117.95,
            "weather": {
                "temperature_c": 22.0,
                "relative_humidity_pct": 72.0,
                "wind_speed_kmh": 9.5,
                "rainfall_mm": 14.2,
                "vegetation_ndvi": 0.610
            }
        }
    ]

    results = []
    for zone in sample_zones:
        w = zone["weather"]
        pred = predictor.predict_risk(
            temperature_c=w["temperature_c"],
            relative_humidity_pct=w["relative_humidity_pct"],
            wind_speed_kmh=w["wind_speed_kmh"],
            rainfall_mm=w["rainfall_mm"],
            vegetation_ndvi=w["vegetation_ndvi"]
        )
        results.append({
            "zone_id": zone["zone_id"],
            "zone_name": zone["zone_name"],
            "coordinates": [zone["lat"], zone["lon"]],
            "weather": w,
            "risk_category": pred["risk_category"],
            "risk_score": pred["risk_score"],
            "uncertainty_level": pred["uncertainty_level"],
            "uncertainty_pct": pred["uncertainty_pct"],
            "top_drivers": pred["top_risk_drivers"],
            "explanation": pred["explanation"]
        })

    return results


def get_cyclone_risk_predictor() -> CycloneRiskPredictor:
    """
    Returns a cached instance of the CycloneRiskPredictor.
    Initializes and trains on the reference dataset if no saved model exists.
    """
    global _cyclone_predictor_instance
    if _cyclone_predictor_instance is None:
        _cyclone_predictor_instance = CycloneRiskPredictor()

        if not _cyclone_predictor_instance.is_trained:
            from pathlib import Path
            data_path = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "cyclone_meteorological_dataset.csv"
            if data_path.exists():
                df = pd.read_csv(data_path)
                _cyclone_predictor_instance.train_and_evaluate(df)

    return _cyclone_predictor_instance


def get_cyclone_model_metrics() -> Dict[str, Any]:
    """
    Returns cyclone model validation metrics, feature importances,
    confusion matrix, and reliability status.
    """
    predictor = get_cyclone_risk_predictor()
    return {
        "status": "success",
        "model_type": "Random Forest Classifier (100 Trees, Max Depth 5)",
        "features": predictor.feature_names,
        "is_trained": predictor.is_trained,
        "metrics": predictor.evaluation_metrics
    }


def predict_cyclone_risk_from_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates input parameters and performs an explainable cyclone coastal risk prediction.
    """
    predictor = get_cyclone_risk_predictor()

    try:
        central_pressure_hpa = float(params.get("central_pressure_hpa", 995.0))
        max_sustained_wind_kmh = float(params.get("max_sustained_wind_kmh", 85.0))
        sea_surface_temp_c = float(params.get("sea_surface_temp_c", 28.5))
        storm_forward_speed_kmh = float(params.get("storm_forward_speed_kmh", 16.0))
        coastal_distance_km = float(params.get("coastal_distance_km", 120.0))
    except (ValueError, TypeError) as err:
        return {
            "status": "error",
            "message": f"Invalid numerical parameter in cyclone request: {str(err)}"
        }

    # Bounded validity checks
    if not (870.0 <= central_pressure_hpa <= 1040.0):
        return {"status": "error", "message": "Central pressure must be between 870 and 1040 hPa"}
    if not (20.0 <= max_sustained_wind_kmh <= 350.0):
        return {"status": "error", "message": "Max sustained wind must be between 20 and 350 km/h"}
    if not (18.0 <= sea_surface_temp_c <= 36.0):
        return {"status": "error", "message": "Sea surface temperature must be between 18.0 and 36.0 °C"}
    if not (0.0 <= storm_forward_speed_kmh <= 100.0):
        return {"status": "error", "message": "Storm forward speed must be between 0.0 and 100.0 km/h"}
    if not (0.0 <= coastal_distance_km <= 1500.0):
        return {"status": "error", "message": "Coastal distance must be between 0.0 and 1500.0 km"}

    result = predictor.predict_risk(
        central_pressure_hpa=central_pressure_hpa,
        max_sustained_wind_kmh=max_sustained_wind_kmh,
        sea_surface_temp_c=sea_surface_temp_c,
        storm_forward_speed_kmh=storm_forward_speed_kmh,
        coastal_distance_km=coastal_distance_km
    )

    return {
        "status": "success",
        "data": result
    }


def get_monitored_cyclone_risk_zones() -> List[Dict[str, Any]]:
    """
    Returns active risk assessments for monitored maritime and coastal basins.
    """
    predictor = get_cyclone_risk_predictor()

    sample_zones = [
        {
            "zone_id": "CYC-ARB-01",
            "zone_name": "Saurashtra & Kutch Littoral (Gujarat)",
            "lat": 22.80,
            "lon": 68.50,
            "basin": "North Indian (Arabian Sea)",
            "conditions": {
                "central_pressure_hpa": 972.0,
                "max_sustained_wind_kmh": 145.0,
                "sea_surface_temp_c": 30.1,
                "storm_forward_speed_kmh": 13.0,
                "coastal_distance_km": 65.0
            }
        },
        {
            "zone_id": "CYC-BOB-02",
            "zone_name": "Sundarbans Estuary & Digha (West Bengal)",
            "lat": 21.65,
            "lon": 87.85,
            "basin": "North Indian (Bay of Bengal)",
            "conditions": {
                "central_pressure_hpa": 955.0,
                "max_sustained_wind_kmh": 185.0,
                "sea_surface_temp_c": 30.8,
                "storm_forward_speed_kmh": 15.0,
                "coastal_distance_km": 40.0
            }
        },
        {
            "zone_id": "CYC-BOB-03",
            "zone_name": "Odisha Coastal Plain (Puri - Paradip)",
            "lat": 19.80,
            "lon": 85.80,
            "basin": "North Indian (Bay of Bengal)",
            "conditions": {
                "central_pressure_hpa": 992.0,
                "max_sustained_wind_kmh": 85.0,
                "sea_surface_temp_c": 28.9,
                "storm_forward_speed_kmh": 22.0,
                "coastal_distance_km": 210.0
            }
        },
        {
            "zone_id": "CYC-CORO-04",
            "zone_name": "Coromandel Coast (Chennai - Nagapattinam)",
            "lat": 13.08,
            "lon": 80.27,
            "basin": "South-West Bay of Bengal",
            "conditions": {
                "central_pressure_hpa": 1006.0,
                "max_sustained_wind_kmh": 48.0,
                "sea_surface_temp_c": 27.2,
                "storm_forward_speed_kmh": 20.0,
                "coastal_distance_km": 420.0
            }
        }
    ]

    results = []
    for z in sample_zones:
        c = z["conditions"]
        pred = predictor.predict_risk(
            central_pressure_hpa=c["central_pressure_hpa"],
            max_sustained_wind_kmh=c["max_sustained_wind_kmh"],
            sea_surface_temp_c=c["sea_surface_temp_c"],
            storm_forward_speed_kmh=c["storm_forward_speed_kmh"],
            coastal_distance_km=c["coastal_distance_km"]
        )
        results.append({
            "zone_id": z["zone_id"],
            "zone_name": z["zone_name"],
            "basin": z["basin"],
            "coordinates": [z["lat"], z["lon"]],
            "conditions": c,
            "classifications": pred["classifications"],
            "risk_category": pred["risk_category"],
            "risk_score": pred["risk_score"],
            "uncertainty_level": pred["uncertainty_level"],
            "uncertainty_pct": pred["uncertainty_pct"],
            "top_drivers": pred["top_risk_drivers"],
            "explanation": pred["explanation"]
        })

    return results



# ==============================================================================
# FLOOD INUNDATION RISK ML SERVICE
# ==============================================================================

def get_flood_risk_predictor() -> FloodRiskPredictor:
    """
    Returns a cached instance of FloodRiskPredictor.
    Initializes and trains on benchmark flood dataset if no saved model exists.
    """
    global _flood_predictor_instance
    if _flood_predictor_instance is None:
        _flood_predictor_instance = FloodRiskPredictor()

        if not _flood_predictor_instance.is_trained:
            from pathlib import Path
            data_path = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "flood_hydrological_dataset.csv"
            if data_path.exists():
                df = pd.read_csv(data_path)
                _flood_predictor_instance.train_and_evaluate(df)

    return _flood_predictor_instance


def get_flood_model_metrics() -> Dict[str, Any]:
    """Returns evaluation metrics, cross-validation scores, and feature importances for Flood ML."""
    predictor = get_flood_risk_predictor()
    return {
        "status": "success",
        "model_type": "Random Forest Classifier (100 Trees, Max Depth 5)",
        "features": predictor.feature_names,
        "is_trained": predictor.is_trained,
        "metrics": predictor.evaluation_metrics
    }


def predict_flood_risk_from_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Validates hydrological parameters and executes flood risk prediction."""
    predictor = get_flood_risk_predictor()

    try:
        rain = float(params.get("precipitation_24h_mm", 60.0))
        soil = float(params.get("soil_moisture_pct", 55.0))
        sar = float(params.get("radar_backscatter_drop_db", 6.0))
        elev = float(params.get("elevation_m", 45.0))
        dist = float(params.get("river_proximity_km", 2.5))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid input parameter data type: {str(exc)}")

    if not (0.0 <= rain <= 600.0):
        raise ValueError("Precipitation must be between 0 mm and 600 mm.")
    if not (0.0 <= soil <= 100.0):
        raise ValueError("Soil moisture must be between 0% and 100%.")
    if not (0.0 <= sar <= 30.0):
        raise ValueError("Radar backscatter drop must be between 0 dB and 30 dB.")
    if not (-50.0 <= elev <= 9000.0):
        raise ValueError("Elevation must be between -50 m and 9000 m.")
    if not (0.0 <= dist <= 100.0):
        raise ValueError("River proximity must be between 0 km and 100 km.")

    prediction = predictor.predict_risk(
        precipitation_24h_mm=rain,
        soil_moisture_pct=soil,
        radar_backscatter_drop_db=sar,
        elevation_m=elev,
        river_proximity_km=dist
    )

    return {
        "status": "success",
        "prediction": prediction
    }


def get_monitored_flood_risk_zones() -> List[Dict[str, Any]]:
    """Generates proactive flood inundation assessments across monitored river basin corridors."""
    predictor = get_flood_risk_predictor()

    sample_basins = [
        {
            "basin_id": "BASIN-BP-01",
            "basin_name": "Lower Brahmaputra Floodplain",
            "lat": 26.18,
            "lon": 91.74,
            "hydrology": {
                "precipitation_24h_mm": 175.0,
                "soil_moisture_pct": 89.5,
                "radar_backscatter_drop_db": 11.8,
                "elevation_m": 28.0,
                "river_proximity_km": 0.6
            }
        },
        {
            "basin_id": "BASIN-GD-02",
            "basin_name": "Central Godavari Tributary Basin",
            "lat": 18.95,
            "lon": 79.52,
            "hydrology": {
                "precipitation_24h_mm": 68.0,
                "soil_moisture_pct": 62.0,
                "radar_backscatter_drop_db": 6.2,
                "elevation_m": 85.0,
                "river_proximity_km": 3.8
            }
        },
        {
            "basin_id": "BASIN-KV-03",
            "basin_name": "Kaveri Upland Catchment",
            "lat": 12.42,
            "lon": 75.73,
            "hydrology": {
                "precipitation_24h_mm": 15.0,
                "soil_moisture_pct": 36.0,
                "radar_backscatter_drop_db": 1.8,
                "elevation_m": 310.0,
                "river_proximity_km": 14.5
            }
        }
    ]

    results = []
    for b in sample_basins:
        h = b["hydrology"]
        pred = predictor.predict_risk(
            precipitation_24h_mm=h["precipitation_24h_mm"],
            soil_moisture_pct=h["soil_moisture_pct"],
            radar_backscatter_drop_db=h["radar_backscatter_drop_db"],
            elevation_m=h["elevation_m"],
            river_proximity_km=h["river_proximity_km"]
        )
        results.append({
            "basin_id": b["basin_id"],
            "basin_name": b["basin_name"],
            "coordinates": [b["lat"], b["lon"]],
            "hydrology": h,
            "risk_category": pred["risk_category"],
            "risk_score": pred["risk_score"],
            "uncertainty_level": pred["uncertainty_level"],
            "uncertainty_pct": pred["uncertainty_pct"],
            "top_drivers": pred["top_risk_drivers"],
            "explanation": pred["explanation"]
        })

    return results


def get_cyclone_risk_predictor() -> CycloneRiskPredictor:
    """
    Returns a cached instance of the CycloneRiskPredictor.
    Initializes and trains on the reference dataset if no saved model exists.
    """
    global _cyclone_predictor_instance
    if _cyclone_predictor_instance is None:
        _cyclone_predictor_instance = CycloneRiskPredictor()

        if not _cyclone_predictor_instance.is_trained:
            from pathlib import Path
            data_path = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "cyclone_meteorological_dataset.csv"
            if data_path.exists():
                df = pd.read_csv(data_path)
                _cyclone_predictor_instance.train_and_evaluate(df)

    return _cyclone_predictor_instance


def get_cyclone_model_metrics() -> Dict[str, Any]:
    """
    Returns cyclone model validation metrics, feature importances,
    confusion matrix, and reliability status.
    """
    predictor = get_cyclone_risk_predictor()
    return {
        "status": "success",
        "model_type": "Random Forest Classifier (100 Trees, Max Depth 5)",
        "features": predictor.feature_names,
        "is_trained": predictor.is_trained,
        "metrics": predictor.evaluation_metrics
    }


def predict_cyclone_risk_from_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates input parameters and performs an explainable cyclone coastal risk prediction.
    """
    predictor = get_cyclone_risk_predictor()

    try:
        central_pressure_hpa = float(params.get("central_pressure_hpa", 995.0))
        max_sustained_wind_kmh = float(params.get("max_sustained_wind_kmh", 85.0))
        sea_surface_temp_c = float(params.get("sea_surface_temp_c", 28.5))
        storm_forward_speed_kmh = float(params.get("storm_forward_speed_kmh", 16.0))
        coastal_distance_km = float(params.get("coastal_distance_km", 120.0))
    except (ValueError, TypeError) as err:
        return {
            "status": "error",
            "message": f"Invalid numerical parameter in cyclone request: {str(err)}"
        }

    # Bounded validity checks
    if not (870.0 <= central_pressure_hpa <= 1040.0):
        return {"status": "error", "message": "Central pressure must be between 870 and 1040 hPa"}
    if not (20.0 <= max_sustained_wind_kmh <= 350.0):
        return {"status": "error", "message": "Max sustained wind must be between 20 and 350 km/h"}
    if not (18.0 <= sea_surface_temp_c <= 36.0):
        return {"status": "error", "message": "Sea surface temperature must be between 18.0 and 36.0 °C"}
    if not (0.0 <= storm_forward_speed_kmh <= 100.0):
        return {"status": "error", "message": "Storm forward speed must be between 0.0 and 100.0 km/h"}
    if not (0.0 <= coastal_distance_km <= 1500.0):
        return {"status": "error", "message": "Coastal distance must be between 0.0 and 1500.0 km"}

    result = predictor.predict_risk(
        central_pressure_hpa=central_pressure_hpa,
        max_sustained_wind_kmh=max_sustained_wind_kmh,
        sea_surface_temp_c=sea_surface_temp_c,
        storm_forward_speed_kmh=storm_forward_speed_kmh,
        coastal_distance_km=coastal_distance_km
    )

    return {
        "status": "success",
        "data": result
    }


def get_monitored_cyclone_risk_zones() -> List[Dict[str, Any]]:
    """
    Returns active risk assessments for monitored maritime and coastal basins.
    """
    predictor = get_cyclone_risk_predictor()

    sample_zones = [
        {
            "zone_id": "CYC-ARB-01",
            "zone_name": "Saurashtra & Kutch Littoral (Gujarat)",
            "lat": 22.80,
            "lon": 68.50,
            "basin": "North Indian (Arabian Sea)",
            "conditions": {
                "central_pressure_hpa": 972.0,
                "max_sustained_wind_kmh": 145.0,
                "sea_surface_temp_c": 30.1,
                "storm_forward_speed_kmh": 13.0,
                "coastal_distance_km": 65.0
            }
        },
        {
            "zone_id": "CYC-BOB-02",
            "zone_name": "Sundarbans Estuary & Digha (West Bengal)",
            "lat": 21.65,
            "lon": 87.85,
            "basin": "North Indian (Bay of Bengal)",
            "conditions": {
                "central_pressure_hpa": 955.0,
                "max_sustained_wind_kmh": 185.0,
                "sea_surface_temp_c": 30.8,
                "storm_forward_speed_kmh": 15.0,
                "coastal_distance_km": 40.0
            }
        },
        {
            "zone_id": "CYC-BOB-03",
            "zone_name": "Odisha Coastal Plain (Puri - Paradip)",
            "lat": 19.80,
            "lon": 85.80,
            "basin": "North Indian (Bay of Bengal)",
            "conditions": {
                "central_pressure_hpa": 992.0,
                "max_sustained_wind_kmh": 85.0,
                "sea_surface_temp_c": 28.9,
                "storm_forward_speed_kmh": 22.0,
                "coastal_distance_km": 210.0
            }
        },
        {
            "zone_id": "CYC-CORO-04",
            "zone_name": "Coromandel Coast (Chennai - Nagapattinam)",
            "lat": 13.08,
            "lon": 80.27,
            "basin": "South-West Bay of Bengal",
            "conditions": {
                "central_pressure_hpa": 1006.0,
                "max_sustained_wind_kmh": 48.0,
                "sea_surface_temp_c": 27.2,
                "storm_forward_speed_kmh": 20.0,
                "coastal_distance_km": 420.0
            }
        }
    ]

    results = []
    for z in sample_zones:
        c = z["conditions"]
        pred = predictor.predict_risk(
            central_pressure_hpa=c["central_pressure_hpa"],
            max_sustained_wind_kmh=c["max_sustained_wind_kmh"],
            sea_surface_temp_c=c["sea_surface_temp_c"],
            storm_forward_speed_kmh=c["storm_forward_speed_kmh"],
            coastal_distance_km=c["coastal_distance_km"]
        )
        results.append({
            "zone_id": z["zone_id"],
            "zone_name": z["zone_name"],
            "basin": z["basin"],
            "coordinates": [z["lat"], z["lon"]],
            "conditions": c,
            "classifications": pred["classifications"],
            "risk_category": pred["risk_category"],
            "risk_score": pred["risk_score"],
            "uncertainty_level": pred["uncertainty_level"],
            "uncertainty_pct": pred["uncertainty_pct"],
            "top_drivers": pred["top_risk_drivers"],
            "explanation": pred["explanation"]
        })

    return results



# ==============================================================================
# AGRICULTURAL DROUGHT RISK ML SERVICE
# ==============================================================================

def get_drought_risk_predictor() -> DroughtRiskPredictor:
    """
    Returns a cached instance of DroughtRiskPredictor.
    Initializes and trains on benchmark drought dataset if no saved model exists.
    """
    global _drought_predictor_instance
    if _drought_predictor_instance is None:
        _drought_predictor_instance = DroughtRiskPredictor()

        if not _drought_predictor_instance.is_trained:
            from pathlib import Path
            data_path = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "drought_agricultural_dataset.csv"
            if data_path.exists():
                df = pd.read_csv(data_path)
                _drought_predictor_instance.train_and_evaluate(df)

    return _drought_predictor_instance


def get_drought_model_metrics() -> Dict[str, Any]:
    """Returns evaluation metrics, cross-validation scores, and feature importances for Drought ML."""
    predictor = get_drought_risk_predictor()
    return {
        "status": "success",
        "model_type": "Random Forest Classifier (100 Trees, Max Depth 5)",
        "features": predictor.feature_names,
        "is_trained": predictor.is_trained,
        "metrics": predictor.evaluation_metrics
    }


def predict_drought_risk_from_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Validates agro-climatic parameters and executes agricultural drought risk prediction."""
    predictor = get_drought_risk_predictor()

    try:
        ndvi_anom = float(params.get("ndvi_anomaly", -0.20))
        ndwi = float(params.get("ndwi_moisture", -0.15))
        vci = float(params.get("vci_percent", 25.0))
        deficit = float(params.get("precipitation_deficit_pct", 55.0))
        soil_temp = float(params.get("soil_temperature_c", 35.0))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid input parameter data type: {str(exc)}")

    if not (-1.0 <= ndvi_anom <= 1.0):
        raise ValueError("NDVI anomaly must be between -1.0 and +1.0.")
    if not (-1.0 <= ndwi <= 1.0):
        raise ValueError("NDWI moisture must be between -1.0 and +1.0.")
    if not (0.0 <= vci <= 100.0):
        raise ValueError("VCI percentile must be between 0% and 100%.")
    if not (0.0 <= deficit <= 100.0):
        raise ValueError("Precipitation deficit must be between 0% and 100%.")
    if not (-20.0 <= soil_temp <= 70.0):
        raise ValueError("Soil temperature must be between -20°C and 70°C.")

    prediction = predictor.predict_risk(
        ndvi_anomaly=ndvi_anom,
        ndwi_moisture=ndwi,
        vci_percent=vci,
        precipitation_deficit_pct=deficit,
        soil_temperature_c=soil_temp
    )

    return {
        "status": "success",
        "prediction": prediction
    }


def get_monitored_drought_risk_zones() -> List[Dict[str, Any]]:
    """Generates proactive drought assessments across monitored agricultural belts."""
    predictor = get_drought_risk_predictor()

    sample_zones = [
        {
            "zone_id": "AGRO-MW-01",
            "zone_name": "Marathwada Agricultural Basin",
            "lat": 19.87,
            "lon": 75.34,
            "vegetation": {
                "ndvi_anomaly": -0.36,
                "ndwi_moisture": -0.28,
                "vci_percent": 14.5,
                "precipitation_deficit_pct": 74.0,
                "soil_temperature_c": 39.5
            }
        },
        {
            "zone_id": "AGRO-VD-02",
            "zone_name": "Vidarbha Cotton Belt",
            "lat": 20.93,
            "lon": 77.75,
            "vegetation": {
                "ndvi_anomaly": -0.18,
                "ndwi_moisture": -0.08,
                "vci_percent": 34.0,
                "precipitation_deficit_pct": 46.0,
                "soil_temperature_c": 33.0
            }
        },
        {
            "zone_id": "AGRO-PJ-03",
            "zone_name": "Punjab Irrigated Alluvial Plains",
            "lat": 30.90,
            "lon": 75.85,
            "vegetation": {
                "ndvi_anomaly": 0.05,
                "ndwi_moisture": 0.18,
                "vci_percent": 76.0,
                "precipitation_deficit_pct": 12.0,
                "soil_temperature_c": 26.5
            }
        }
    ]

    results = []
    for z in sample_zones:
        v = z["vegetation"]
        pred = predictor.predict_risk(
            ndvi_anomaly=v["ndvi_anomaly"],
            ndwi_moisture=v["ndwi_moisture"],
            vci_percent=v["vci_percent"],
            precipitation_deficit_pct=v["precipitation_deficit_pct"],
            soil_temperature_c=v["soil_temperature_c"]
        )
        results.append({
            "zone_id": z["zone_id"],
            "zone_name": z["zone_name"],
            "coordinates": [z["lat"], z["lon"]],
            "vegetation": v,
            "risk_category": pred["risk_category"],
            "risk_score": pred["risk_score"],
            "uncertainty_level": pred["uncertainty_level"],
            "uncertainty_pct": pred["uncertainty_pct"],
            "top_drivers": pred["top_risk_drivers"],
            "explanation": pred["explanation"]
        })

    return results


def get_cyclone_risk_predictor() -> CycloneRiskPredictor:
    """
    Returns a cached instance of the CycloneRiskPredictor.
    Initializes and trains on the reference dataset if no saved model exists.
    """
    global _cyclone_predictor_instance
    if _cyclone_predictor_instance is None:
        _cyclone_predictor_instance = CycloneRiskPredictor()

        if not _cyclone_predictor_instance.is_trained:
            from pathlib import Path
            data_path = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "cyclone_meteorological_dataset.csv"
            if data_path.exists():
                df = pd.read_csv(data_path)
                _cyclone_predictor_instance.train_and_evaluate(df)

    return _cyclone_predictor_instance


def get_cyclone_model_metrics() -> Dict[str, Any]:
    """
    Returns cyclone model validation metrics, feature importances,
    confusion matrix, and reliability status.
    """
    predictor = get_cyclone_risk_predictor()
    return {
        "status": "success",
        "model_type": "Random Forest Classifier (100 Trees, Max Depth 5)",
        "features": predictor.feature_names,
        "is_trained": predictor.is_trained,
        "metrics": predictor.evaluation_metrics
    }


def predict_cyclone_risk_from_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates input parameters and performs an explainable cyclone coastal risk prediction.
    """
    predictor = get_cyclone_risk_predictor()

    try:
        central_pressure_hpa = float(params.get("central_pressure_hpa", 995.0))
        max_sustained_wind_kmh = float(params.get("max_sustained_wind_kmh", 85.0))
        sea_surface_temp_c = float(params.get("sea_surface_temp_c", 28.5))
        storm_forward_speed_kmh = float(params.get("storm_forward_speed_kmh", 16.0))
        coastal_distance_km = float(params.get("coastal_distance_km", 120.0))
    except (ValueError, TypeError) as err:
        return {
            "status": "error",
            "message": f"Invalid numerical parameter in cyclone request: {str(err)}"
        }

    # Bounded validity checks
    if not (870.0 <= central_pressure_hpa <= 1040.0):
        return {"status": "error", "message": "Central pressure must be between 870 and 1040 hPa"}
    if not (20.0 <= max_sustained_wind_kmh <= 350.0):
        return {"status": "error", "message": "Max sustained wind must be between 20 and 350 km/h"}
    if not (18.0 <= sea_surface_temp_c <= 36.0):
        return {"status": "error", "message": "Sea surface temperature must be between 18.0 and 36.0 °C"}
    if not (0.0 <= storm_forward_speed_kmh <= 100.0):
        return {"status": "error", "message": "Storm forward speed must be between 0.0 and 100.0 km/h"}
    if not (0.0 <= coastal_distance_km <= 1500.0):
        return {"status": "error", "message": "Coastal distance must be between 0.0 and 1500.0 km"}

    result = predictor.predict_risk(
        central_pressure_hpa=central_pressure_hpa,
        max_sustained_wind_kmh=max_sustained_wind_kmh,
        sea_surface_temp_c=sea_surface_temp_c,
        storm_forward_speed_kmh=storm_forward_speed_kmh,
        coastal_distance_km=coastal_distance_km
    )

    return {
        "status": "success",
        "data": result
    }


def get_monitored_cyclone_risk_zones() -> List[Dict[str, Any]]:
    """
    Returns active risk assessments for monitored maritime and coastal basins.
    """
    predictor = get_cyclone_risk_predictor()

    sample_zones = [
        {
            "zone_id": "CYC-ARB-01",
            "zone_name": "Saurashtra & Kutch Littoral (Gujarat)",
            "lat": 22.80,
            "lon": 68.50,
            "basin": "North Indian (Arabian Sea)",
            "conditions": {
                "central_pressure_hpa": 972.0,
                "max_sustained_wind_kmh": 145.0,
                "sea_surface_temp_c": 30.1,
                "storm_forward_speed_kmh": 13.0,
                "coastal_distance_km": 65.0
            }
        },
        {
            "zone_id": "CYC-BOB-02",
            "zone_name": "Sundarbans Estuary & Digha (West Bengal)",
            "lat": 21.65,
            "lon": 87.85,
            "basin": "North Indian (Bay of Bengal)",
            "conditions": {
                "central_pressure_hpa": 955.0,
                "max_sustained_wind_kmh": 185.0,
                "sea_surface_temp_c": 30.8,
                "storm_forward_speed_kmh": 15.0,
                "coastal_distance_km": 40.0
            }
        },
        {
            "zone_id": "CYC-BOB-03",
            "zone_name": "Odisha Coastal Plain (Puri - Paradip)",
            "lat": 19.80,
            "lon": 85.80,
            "basin": "North Indian (Bay of Bengal)",
            "conditions": {
                "central_pressure_hpa": 992.0,
                "max_sustained_wind_kmh": 85.0,
                "sea_surface_temp_c": 28.9,
                "storm_forward_speed_kmh": 22.0,
                "coastal_distance_km": 210.0
            }
        },
        {
            "zone_id": "CYC-CORO-04",
            "zone_name": "Coromandel Coast (Chennai - Nagapattinam)",
            "lat": 13.08,
            "lon": 80.27,
            "basin": "South-West Bay of Bengal",
            "conditions": {
                "central_pressure_hpa": 1006.0,
                "max_sustained_wind_kmh": 48.0,
                "sea_surface_temp_c": 27.2,
                "storm_forward_speed_kmh": 20.0,
                "coastal_distance_km": 420.0
            }
        }
    ]

    results = []
    for z in sample_zones:
        c = z["conditions"]
        pred = predictor.predict_risk(
            central_pressure_hpa=c["central_pressure_hpa"],
            max_sustained_wind_kmh=c["max_sustained_wind_kmh"],
            sea_surface_temp_c=c["sea_surface_temp_c"],
            storm_forward_speed_kmh=c["storm_forward_speed_kmh"],
            coastal_distance_km=c["coastal_distance_km"]
        )
        results.append({
            "zone_id": z["zone_id"],
            "zone_name": z["zone_name"],
            "basin": z["basin"],
            "coordinates": [z["lat"], z["lon"]],
            "conditions": c,
            "classifications": pred["classifications"],
            "risk_category": pred["risk_category"],
            "risk_score": pred["risk_score"],
            "uncertainty_level": pred["uncertainty_level"],
            "uncertainty_pct": pred["uncertainty_pct"],
            "top_drivers": pred["top_risk_drivers"],
            "explanation": pred["explanation"]
        })

    return results




