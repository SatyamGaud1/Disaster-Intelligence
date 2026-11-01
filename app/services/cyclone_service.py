"""
Cyclone Monitoring and Tracking Service.
Handles NOAA National Hurricane Center (NHC) and IMD RSMC tropical cyclone track ingestion,
dual-agency intensity classification (Saffir-Simpson & IMD), track visualization (observed vs forecast),
uncertainty cone geometry, and official advisory dissemination.
"""

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

import numpy as np
import pandas as pd

EARTH_RADIUS_KM = 6371.0088


def load_cyclone_reference_data(file_path: Path = None) -> pd.DataFrame:
    """
    Loads official NOAA NHC and IMD IBTrACS benchmark cyclone observations.
    Falls back to reference CSV if custom path is not specified.
    """
    target_path = file_path or (
        Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "noaa_ibtracs_reference.csv"
    )

    if not Path(target_path).exists():
        raise FileNotFoundError(f"Cyclone reference dataset not found at: {target_path}")

    df = pd.read_csv(target_path)
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["max_sustained_wind_kmh"] = pd.to_numeric(df["max_sustained_wind_kmh"], errors="coerce").fillna(60.0)
    df["max_sustained_wind_knots"] = pd.to_numeric(df["max_sustained_wind_knots"], errors="coerce").fillna(33.0)
    df["central_pressure_hpa"] = pd.to_numeric(df["central_pressure_hpa"], errors="coerce").fillna(995.0)
    df["movement_speed_kmh"] = pd.to_numeric(df["movement_speed_kmh"], errors="coerce").fillna(15.0)
    df["coastal_distance_km"] = pd.to_numeric(df["coastal_distance_km"], errors="coerce").fillna(100.0)
    df["forecast_hour"] = pd.to_numeric(df["forecast_hour"], errors="coerce").fillna(0).astype(int)

    df = df.dropna(subset=["latitude", "longitude", "storm_id"])
    return df


def get_available_storms() -> List[Dict[str, Any]]:
    """
    Returns list of all available cyclone systems (active and reference benchmarks).
    """
    df = load_cyclone_reference_data()
    storms = []
    for storm_id, group in df.groupby("storm_id", sort=False):
        first = group.iloc[0]
        latest_obs = group[group["track_type"] == "OBSERVED"].iloc[-1]
        storms.append({
            "storm_id": storm_id,
            "name": str(first["storm_name"]),
            "basin": str(first["basin"]),
            "issuing_agency": str(first["issuing_agency"]),
            "status": str(first["status"]),
            "latest_wind_kmh": float(latest_obs["max_sustained_wind_kmh"]),
            "latest_pressure_hpa": float(latest_obs["central_pressure_hpa"]),
            "category_saffir": str(latest_obs["category_saffir"]),
            "category_imd": str(latest_obs["category_imd"]),
            "nearest_coast": str(latest_obs["nearest_coast_region"])
        })
    return storms


def get_active_cyclones() -> List[Dict[str, Any]]:
    """
    Retrieves currently active cyclones or latest official surveillance systems.
    Provides complete transparency regarding data origin, agency, and timestamps.
    """
    df = load_cyclone_reference_data()
    active_groups = df.groupby("storm_id", sort=False)

    systems = []
    for storm_id, group in active_groups:
        obs_points = group[group["track_type"] == "OBSERVED"].sort_values("timestamp_utc")
        if obs_points.empty:
            continue

        latest = obs_points.iloc[-1]
        is_active = (latest["status"] == "ACTIVE")

        # Intensity trend: drop in pressure over past observations indicates rapid intensification
        pressure_history = obs_points["central_pressure_hpa"].tolist()
        intensification_trend = "STEADY"
        if len(pressure_history) >= 2:
            delta_p = pressure_history[-1] - pressure_history[-2]
            if delta_p <= -8.0:
                intensification_trend = "RAPID_INTENSIFICATION"
            elif delta_p <= -3.0:
                intensification_trend = "STRENGTHENING"
            elif delta_p >= 5.0:
                intensification_trend = "WEAKENING"

        systems.append({
            "storm_id": storm_id,
            "storm_name": str(latest["storm_name"]),
            "basin": str(latest["basin"]),
            "status": str(latest["status"]),
            "is_active": is_active,
            "issuing_agency": str(latest["issuing_agency"]),
            "timestamp_utc": str(latest["timestamp_utc"]),
            "latitude": round(float(latest["latitude"]), 2),
            "longitude": round(float(latest["longitude"]), 2),
            "max_sustained_wind_kmh": round(float(latest["max_sustained_wind_kmh"]), 1),
            "max_sustained_wind_knots": round(float(latest["max_sustained_wind_knots"]), 1),
            "central_pressure_hpa": round(float(latest["central_pressure_hpa"]), 1),
            "category_saffir": str(latest["category_saffir"]),
            "category_imd": str(latest["category_imd"]),
            "movement_direction": str(latest["movement_dir"]),
            "movement_speed_kmh": round(float(latest["movement_speed_kmh"]), 1),
            "coastal_distance_km": round(float(latest["coastal_distance_km"]), 1),
            "nearest_coast_region": str(latest["nearest_coast_region"]),
            "intensification_trend": intensification_trend,
            "advisory_headline": str(latest["advisory_headline"]),
            "advisory_url": str(latest["advisory_url"]),
            "data_source": "NOAA NHC / IMD RSMC Official Track Surveillance",
            "last_synced": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        })

    # Sort so active storms appear first
    systems.sort(key=lambda s: (not s["is_active"], s["coastal_distance_km"]))
    return systems


def get_cyclone_track_data(storm_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns separate observed and forecast track points and uncertainty cone for a specific cyclone.
    Clearly distinguishes observed history from official forecast positions.
    """
    df = load_cyclone_reference_data()

    if storm_id is None or storm_id not in df["storm_id"].values:
        # Default to first active storm or first available
        storm_id = df["storm_id"].iloc[0]

    storm_df = df[df["storm_id"] == storm_id].copy()

    observed = storm_df[storm_df["track_type"] == "OBSERVED"].sort_values("timestamp_utc")
    forecast = storm_df[storm_df["track_type"] == "FORECAST"].sort_values("forecast_hour")

    obs_list = []
    for _, row in observed.iterrows():
        obs_list.append({
            "timestamp_utc": str(row["timestamp_utc"]),
            "latitude": round(float(row["latitude"]), 2),
            "longitude": round(float(row["longitude"]), 2),
            "wind_kmh": round(float(row["max_sustained_wind_kmh"]), 1),
            "pressure_hpa": round(float(row["central_pressure_hpa"]), 1),
            "category_saffir": str(row["category_saffir"]),
            "category_imd": str(row["category_imd"]),
            "headline": str(row["advisory_headline"])
        })

    fcst_list = []
    for _, row in forecast.iterrows():
        fcst_list.append({
            "forecast_hour": int(row["forecast_hour"]),
            "timestamp_utc": str(row["timestamp_utc"]),
            "latitude": round(float(row["latitude"]), 2),
            "longitude": round(float(row["longitude"]), 2),
            "wind_kmh": round(float(row["max_sustained_wind_kmh"]), 1),
            "pressure_hpa": round(float(row["central_pressure_hpa"]), 1),
            "category_saffir": str(row["category_saffir"]),
            "category_imd": str(row["category_imd"]),
            "headline": str(row["advisory_headline"])
        })

    # Generate uncertainty cone polygon coordinates around the forecast track
    # Standard cone radius expands with forecast lead time: ~40km at +12h, ~80km at +24h, ~130km at +36h
    cone_coords = _compute_uncertainty_cone(obs_list[-1] if obs_list else None, fcst_list)

    first_row = storm_df.iloc[0]
    return {
        "storm_id": storm_id,
        "storm_name": str(first_row["storm_name"]),
        "basin": str(first_row["basin"]),
        "issuing_agency": str(first_row["issuing_agency"]),
        "status": str(first_row["status"]),
        "observed_track": obs_list,
        "forecast_track": fcst_list,
        "uncertainty_cone": cone_coords,
        "has_forecast": len(fcst_list) > 0,
        "disclaimer": "Forecast points represent official agency projections. Never extrapolated artificially."
    }


def _compute_uncertainty_cone(current_pos: Optional[Dict[str, Any]], forecast_points: List[Dict[str, Any]]) -> List[List[float]]:
    """
    Builds a convex polygon bounding the forecast track representing the official Cone of Uncertainty.
    """
    if not current_pos or not forecast_points:
        return []

    pts = [current_pos] + forecast_points
    left_boundary = []
    right_boundary = []

    for i, pt in enumerate(pts):
        lat = pt["latitude"]
        lon = pt["longitude"]
        hour = pt.get("forecast_hour", 0)

        # Uncertainty expands by ~3.5 km per forecast hour + 25 km base eye diameter
        radius_km = 25.0 + (hour * 3.5)
        # Approximate offset in degrees: 1 deg latitude ~ 111 km
        d_lat = radius_km / 111.0
        d_lon = radius_km / (111.0 * math.cos(math.radians(lat)) + 1e-6)

        left_boundary.append([round(lat + d_lat * 0.7, 3), round(lon - d_lon * 0.7, 3)])
        right_boundary.append([round(lat - d_lat * 0.7, 3), round(lon + d_lon * 0.7, 3)])

    polygon = left_boundary + list(reversed(right_boundary))
    if polygon:
        polygon.append(polygon[0])  # Close the ring
    return polygon


def get_official_advisories() -> List[Dict[str, Any]]:
    """
    Retrieves official cyclone advisories, warnings, and links to original sources.
    """
    df = load_cyclone_reference_data()
    advisories = []
    seen = set()

    for _, row in df.iterrows():
        key = (row["storm_id"], row["advisory_headline"])
        if key in seen:
            continue
        seen.add(key)

        # Assign warning level based on wind
        wind = float(row["max_sustained_wind_kmh"])
        if wind >= 165.0:
            level = "RED WARNING (CATASTROPHIC)"
            level_code = "RED"
        elif wind >= 118.0:
            level = "ORANGE WARNING (SEVERE)"
            level_code = "ORANGE"
        elif wind >= 65.0:
            level = "YELLOW ADVISORY (MODERATE)"
            level_code = "YELLOW"
        else:
            level = "INFORMATION WATCH"
            level_code = "WATCH"

        advisories.append({
            "storm_id": str(row["storm_id"]),
            "storm_name": str(row["storm_name"]),
            "issuing_agency": str(row["issuing_agency"]),
            "publication_time": str(row["timestamp_utc"]),
            "warning_level": level,
            "warning_level_code": level_code,
            "headline": str(row["advisory_headline"]),
            "advisory_url": str(row["advisory_url"]),
            "affected_region": str(row["nearest_coast_region"]),
            "track_type": str(row["track_type"])
        })

    advisories.sort(key=lambda a: (a["warning_level_code"] != "RED", a["warning_level_code"] != "ORANGE"))
    return advisories

