"""
Drought Monitoring Service.
Handles Copernicus Sentinel-2 MSI multispectral vegetation indices (NDVI, NDWI, VCI),
DBSCAN agricultural drought corridor clustering, and transparent priority scoring.
"""

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

# Earth radius in kilometers for Haversine spherical computations
EARTH_RADIUS_KM = 6371.0088


def load_drought_data(file_path: Path = None) -> pd.DataFrame:
    """
    Loads Copernicus Sentinel-2 MSI multispectral vegetation observations.
    Falls back to the reference dataset if no custom path is given.
    """
    target_path = file_path or (
        Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "sentinel2_drought_reference.csv"
    )

    if not Path(target_path).exists():
        raise FileNotFoundError(f"Sentinel-2 drought observation dataset not found at: {target_path}")

    df = pd.read_csv(target_path)

    # Sanitize numeric fields
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["ndvi_current"] = pd.to_numeric(df["ndvi_current"], errors="coerce").fillna(0.30)
    df["ndvi_baseline"] = pd.to_numeric(df["ndvi_baseline"], errors="coerce").fillna(0.55)
    df["ndvi_anomaly"] = pd.to_numeric(df["ndvi_anomaly"], errors="coerce")

    # If anomaly not pre-computed, calculate difference: current - baseline
    df["ndvi_anomaly"] = df["ndvi_anomaly"].fillna(df["ndvi_current"] - df["ndvi_baseline"])

    df["ndwi_moisture"] = pd.to_numeric(df["ndwi_moisture"], errors="coerce").fillna(-0.15)
    df["vci_percent"] = pd.to_numeric(df["vci_percent"], errors="coerce").fillna(30.0)
    df["cloud_cover_percent"] = pd.to_numeric(df["cloud_cover_percent"], errors="coerce").fillna(2.0)

    # Absolute magnitude of negative NDVI drop for intuitive weighting
    df["anomaly_magnitude"] = df["ndvi_anomaly"].apply(lambda x: abs(min(0.0, x)))

    df = df.dropna(subset=["latitude", "longitude"])
    return df


def cluster_drought_zones(df: pd.DataFrame, eps_km: float = 25.0, min_samples: int = 2) -> pd.DataFrame:
    """
    Clusters stressed agricultural pixels into contiguous drought corridors using DBSCAN.
    Search radius of ~25 km accommodates regional farming districts and agro-ecological zones.
    """
    if df.empty:
        df["cluster_id"] = []
        return df

    coords_rad = np.radians(df[["latitude", "longitude"]].to_numpy())
    eps_rad = eps_km / EARTH_RADIUS_KM

    db = DBSCAN(eps=eps_rad, min_samples=min_samples, metric="haversine", algorithm="ball_tree")
    df = df.copy()
    df["cluster_id"] = db.fit_predict(coords_rad)

    return df


def calculate_transparent_drought_priority(cluster_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculates an explainable, deterministic multi-factor drought priority score (0 - 100).
    
    Formula components:
    1. NDVI Anomaly Severity (35% weight): Chlorophyll degradation and canopy desiccation.
    2. NDWI Moisture Deficit (30% weight): Liquid water absorption in shortwave infrared (SWIR).
    3. Vegetation Condition Index Severity (20% weight): Relative historical percentile (100 - VCI).
    4. Arable Spatial Extent (15% weight): Contiguous stressed agricultural footprint.
    """
    pixel_count = len(cluster_df)
    mean_anomaly = float(cluster_df["ndvi_anomaly"].mean())
    mean_ndvi = float(cluster_df["ndvi_current"].mean())
    mean_ndwi = float(cluster_df["ndwi_moisture"].mean())
    mean_vci = float(cluster_df["vci_percent"].mean())

    # 1. NDVI Anomaly Factor (0 - 100)
    # A negative anomaly of -0.35 represents severe crop failure / biomass collapse
    drop_magnitude = abs(min(0.0, mean_anomaly))
    score_anomaly = min(100.0, (drop_magnitude / 0.35) * 100.0)

    # 2. NDWI Canopy Moisture Deficit Factor (0 - 100)
    # Values dropping below -0.30 indicate extreme moisture depletion in leaves and soil
    moisture_deficit = abs(min(0.0, mean_ndwi))
    score_moisture = min(100.0, (moisture_deficit / 0.32) * 100.0)

    # 3. VCI Severity Factor (0 - 100)
    # VCI < 20% signifies extreme agricultural drought relative to historical maximums
    score_vci = max(0.0, min(100.0, 100.0 - mean_vci))

    # 4. Spatial Extent Factor (0 - 100)
    # 5+ contiguous observations indicates widespread district-scale agricultural drought
    score_extent = min(100.0, (pixel_count / 5.0) * 100.0)

    # Weighted Sum
    priority_score = (
        (score_anomaly * 0.35) +
        (score_moisture * 0.30) +
        (score_vci * 0.20) +
        (score_extent * 0.15)
    )
    priority_score = round(max(5.0, min(99.0, priority_score)), 1)

    # Categorization
    if priority_score >= 80.0:
        level = "CRITICAL"
    elif priority_score >= 60.0:
        level = "HIGH"
    elif priority_score >= 40.0:
        level = "MEDIUM"
    else:
        level = "LOW"

    # Confidence proxy based on cloud clearance (low cloud cover = high confidence)
    mean_cloud = float(cluster_df["cloud_cover_percent"].mean())
    confidence_score = round(max(0.5, 1.0 - (mean_cloud / 100.0)), 2)

    return {
        "priority_score": priority_score,
        "priority_level": level,
        "factors": {
            "ndvi_anomaly_factor": round(score_anomaly, 1),
            "moisture_deficit_factor": round(score_moisture, 1),
            "vci_severity_factor": round(score_vci, 1),
            "spatial_extent_factor": round(score_extent, 1)
        },
        "stats": {
            "pixel_count": pixel_count,
            "mean_ndvi": round(mean_ndvi, 3),
            "mean_ndvi_anomaly": round(mean_anomaly, 3),
            "mean_ndwi_moisture": round(mean_ndwi, 3),
            "mean_vci_percent": round(mean_vci, 1),
            "confidence_score": confidence_score
        }
    }


def compute_drought_geometry_and_evidence(cluster_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Computes anomaly-weighted centroid, estimated affected arable area (sq km),
    and atmospheric cloud uncertainty metric.
    """
    weights = cluster_df["anomaly_magnitude"]
    total_weight = weights.sum()

    if total_weight > 0:
        centroid_lat = float((cluster_df["latitude"] * weights).sum() / total_weight)
        centroid_lon = float((cluster_df["longitude"] * weights).sum() / total_weight)
    else:
        centroid_lat = float(cluster_df["latitude"].mean())
        centroid_lon = float(cluster_df["longitude"].mean())

    lat_min, lat_max = cluster_df["latitude"].min(), cluster_df["latitude"].max()
    lon_min, lon_max = cluster_df["longitude"].min(), cluster_df["longitude"].max()

    delta_lat_km = max(2.0, (lat_max - lat_min) * 111.0)
    delta_lon_km = max(2.0, (lon_max - lon_min) * 111.0 * math.cos(math.radians(centroid_lat)))

    # Drought footprint area in sq km
    affected_area_sqkm = round(max(2.5, (delta_lat_km * delta_lon_km) * (math.pi / 4.0)), 2)

    # Uncertainty metric: cloud cover + spatial dispersion
    pixel_count = len(cluster_df)
    mean_cloud = float(cluster_df["cloud_cover_percent"].mean())
    dispersion = math.sqrt(delta_lat_km**2 + delta_lon_km**2)
    uncertainty_score = round(min(1.0, max(0.05, (mean_cloud / 50.0) + (dispersion / 60.0) / math.sqrt(pixel_count))), 2)

    return {
        "centroid_lat": round(centroid_lat, 5),
        "centroid_lon": round(centroid_lon, 5),
        "affected_area_sqkm": affected_area_sqkm,
        "uncertainty_score": uncertainty_score,
        "bbox": [round(lat_min, 4), round(lon_min, 4), round(lat_max, 4), round(lon_max, 4)]
    }


def process_drought_incidents(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Processes Sentinel-2 observations into prioritized drought incidents.
    """
    clustered_df = cluster_drought_zones(df)
    incidents = []

    grouped = clustered_df.groupby("cluster_id")

    for cluster_id, group in grouped:
        is_isolated = (cluster_id == -1)

        if is_isolated:
            for idx, row in group.iterrows():
                single_df = pd.DataFrame([row])
                score_data = calculate_transparent_drought_priority(single_df)
                geom_data = compute_drought_geometry_and_evidence(single_df)

                zone = str(row.get("agricultural_zone", "Arable Plain"))
                uid = f"INC-DROUGHT-ISO-{abs(hash(str(row['latitude']) + str(row['longitude']))) % 10000:04d}"
                incidents.append({
                    "incident_uid": uid,
                    "title": f"Local Crop Stress: {zone}",
                    "hazard_type": "DROUGHT",
                    "status": "MONITORING",
                    "priority_level": score_data["priority_level"],
                    "priority_score": score_data["priority_score"],
                    "confidence_score": score_data["stats"]["confidence_score"],
                    "centroid_lat": geom_data["centroid_lat"],
                    "centroid_lon": geom_data["centroid_lon"],
                    "affected_area_sqkm": geom_data["affected_area_sqkm"],
                    "summary": (
                        f"Isolated vegetation moisture deficit in {zone}. "
                        f"NDVI Anomaly: {row['ndvi_anomaly']:.2f}. "
                        f"NDWI: {row['ndwi_moisture']:.2f}. "
                        f"VCI: {row['vci_percent']:.1f}%. "
                        f"Uncertainty: {geom_data['uncertainty_score']}."
                    ),
                    "evidence_json": json.dumps({
                        "scores": score_data,
                        "geometry": geom_data,
                        "detections_count": 1
                    }),
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
        else:
            score_data = calculate_transparent_drought_priority(group)
            geom_data = compute_drought_geometry_and_evidence(group)

            first_row = group.iloc[0]
            zone = str(first_row.get("agricultural_zone", "Agricultural Corridor"))
            uid = f"INC-DROUGHT-CLS-{cluster_id + 301:03d}"
            stats = score_data["stats"]

            title = f"Agricultural Drought Complex: {zone} ({geom_data['affected_area_sqkm']} km²)"
            summary = (
                f"Severe vegetation desiccation across {zone} spanning ~{geom_data['affected_area_sqkm']} sq km. "
                f"Sentinel-2 MSI observed mean NDVI drop of {stats['mean_ndvi_anomaly']} (VCI: {stats['mean_vci_percent']}%). "
                f"Canopy moisture index (NDWI) at {stats['mean_ndwi_moisture']}. "
                f"Priority rated {score_data['priority_level']} ({score_data['priority_score']}/100)."
            )

            incidents.append({
                "incident_uid": uid,
                "title": title,
                "hazard_type": "DROUGHT",
                "status": "ACTIVE" if score_data["priority_level"] in ("CRITICAL", "HIGH") else "MONITORING",
                "priority_level": score_data["priority_level"],
                "priority_score": score_data["priority_score"],
                "confidence_score": stats["confidence_score"],
                "centroid_lat": geom_data["centroid_lat"],
                "centroid_lon": geom_data["centroid_lon"],
                "affected_area_sqkm": geom_data["affected_area_sqkm"],
                "summary": summary,
                "evidence_json": json.dumps({
                    "scores": score_data,
                    "geometry": geom_data,
                    "detections_count": stats["pixel_count"]
                }),
                "created_at": datetime.now(timezone.utc).isoformat()
            })

    incidents.sort(key=lambda x: x["priority_score"], reverse=True)
    return incidents


def ingest_drought_data_to_db(db_conn) -> Dict[str, Any]:
    """
    Ingests Sentinel-2 MSI multispectral drought observations into SQLite database.
    """
    df = load_drought_data()
    incidents = process_drought_incidents(df)

    cursor = db_conn.cursor()

    # Clear prior drought records to prevent duplicates during sync
    cursor.execute("DELETE FROM hazards WHERE source = 'SENTINEL_2'")
    cursor.execute("DELETE FROM incidents WHERE hazard_type = 'DROUGHT'")

    # Insert individual vegetation hazard observations
    hazard_rows = []
    for _, row in df.iterrows():
        hazard_rows.append((
            "SENTINEL_2",
            "DROUGHT",
            float(row["latitude"]),
            float(row["longitude"]),
            float(abs(row["ndvi_anomaly"])),  # Intensity = magnitude of NDVI anomaly drop
            float(max(0.5, 1.0 - (row["cloud_cover_percent"] / 100.0))),
            f"{row.get('observation_date', '2026-10-30')}T10:30:00Z",
            json.dumps({
                "ndvi_current": float(row["ndvi_current"]),
                "ndvi_baseline": float(row["ndvi_baseline"]),
                "ndvi_anomaly": float(row["ndvi_anomaly"]),
                "ndwi_moisture": float(row["ndwi_moisture"]),
                "vci_percent": float(row["vci_percent"]),
                "cloud_cover_percent": float(row.get("cloud_cover_percent", 0.0)),
                "agricultural_zone": str(row.get("agricultural_zone", "Arable Plain"))
            })
        ))

    cursor.executemany(
        """
        INSERT INTO hazards (source, hazard_type, latitude, longitude, intensity_value, confidence, observation_timestamp, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        hazard_rows
    )

    # Insert prioritized drought incidents
    for inc in incidents:
        cursor.execute(
            """
            INSERT INTO incidents (incident_uid, title, hazard_type, status, priority_level,
                                   priority_score, confidence_score, centroid_lat, centroid_lon,
                                   affected_area_sqkm, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                inc["incident_uid"],
                inc["title"],
                inc["hazard_type"],
                inc["status"],
                inc["priority_level"],
                inc["priority_score"],
                inc["confidence_score"],
                inc["centroid_lat"],
                inc["centroid_lon"],
                inc["affected_area_sqkm"],
                inc["summary"],
                inc["created_at"],
                inc["created_at"]
            )
        )

    # Update source sync status for Sentinel-2
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        """
        UPDATE source_sync_status
        SET last_sync_timestamp = ?, status = 'READY', records_count = ?, message = ?
        WHERE source_name = 'SENTINEL_2'
        """,
        (now_iso, len(df), f"Ingested {len(df)} multispectral MSI observations and formed {len(incidents)} drought complexes.")
    )

    # Log action to audit log
    cursor.execute(
        """
        INSERT INTO audit_logs (action, details)
        VALUES (?, ?)
        """,
        ("SENTINEL2_DROUGHT_SYNC", f"Processed {len(df)} vegetation anomaly pixels -> {len(incidents)} drought incidents")
    )

    db_conn.commit()

    return {
        "status": "success",
        "observations_ingested": len(df),
        "drought_incidents_formed": len(incidents)
    }

