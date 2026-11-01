"""
Flood Monitoring Service.
Handles Copernicus Sentinel-1 Synthetic Aperture Radar (SAR) backscatter analysis,
NASA GPM rainfall ingestion, geospatial DBSCAN inundation clustering,
and transparent priority scoring.
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


def load_flood_data(file_path: Path = None) -> pd.DataFrame:
    """
    Loads Copernicus Sentinel-1 SAR and NASA GPM precipitation observations.
    Falls back to the reference dataset if no custom path is given.
    """
    target_path = file_path or (
        Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "sentinel1_flood_reference.csv"
    )

    if not Path(target_path).exists():
        raise FileNotFoundError(f"Sentinel-1 flood observation dataset not found at: {target_path}")

    df = pd.read_csv(target_path)

    # Sanitize numeric fields
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["sar_backscatter_db"] = pd.to_numeric(df["sar_backscatter_db"], errors="coerce").fillna(-15.0)
    df["baseline_backscatter_db"] = pd.to_numeric(df["baseline_backscatter_db"], errors="coerce").fillna(-10.0)
    df["backscatter_diff_db"] = pd.to_numeric(df["backscatter_diff_db"], errors="coerce")
    
    # If difference is not pre-computed, calculate it: current - baseline
    df["backscatter_diff_db"] = df["backscatter_diff_db"].fillna(
        df["sar_backscatter_db"] - df["baseline_backscatter_db"]
    )

    df["inundation_prob"] = pd.to_numeric(df["inundation_prob"], errors="coerce").fillna(0.70)
    df["gpm_rainfall_mm_24h"] = pd.to_numeric(df["gpm_rainfall_mm_24h"], errors="coerce").fillna(50.0)

    # Invert backscatter drop to positive magnitude for intuitive weighting
    df["anomaly_magnitude"] = df["backscatter_diff_db"].abs()

    df = df.dropna(subset=["latitude", "longitude"])
    return df


def cluster_flood_zones(df: pd.DataFrame, eps_km: float = 12.0, min_samples: int = 2) -> pd.DataFrame:
    """
    Clusters flooded radar pixels into contiguous inundation complexes using DBSCAN.
    Search radius of ~12 km accommodates regional watershed floodplain bounds.
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


def calculate_transparent_flood_priority(cluster_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculates an explainable, deterministic multi-factor priority score (0 - 100).
    
    Formula components:
    1. SAR Backscatter Drop / Inundation Index (35% weight):
       Deep negative SAR backscatter indicates smooth specular open water surface.
    2. NASA GPM Rainfall Driver (30% weight):
       24-hour accumulated precipitation in mm.
    3. Floodplain Extent & Spatial Density (20% weight):
       Count of contiguous flooded radar pixels and approximate area.
    4. Detection Confidence & Water Classification (15% weight):
       Copernicus SAR dual-polarization water classification probability.
    """
    pixel_count = len(cluster_df)
    mean_diff = float(cluster_df["backscatter_diff_db"].mean())
    mean_sar = float(cluster_df["sar_backscatter_db"].mean())
    max_rainfall = float(cluster_df["gpm_rainfall_mm_24h"].max())
    mean_rainfall = float(cluster_df["gpm_rainfall_mm_24h"].mean())
    mean_prob = float(cluster_df["inundation_prob"].mean())

    # 1. Inundation Anomaly Factor (0 - 100)
    # A backscatter drop of -12 dB or deeper represents clear standing surface water
    drop_magnitude = abs(mean_diff)
    score_inundation = min(100.0, (drop_magnitude / 12.0) * 100.0)

    # 2. Rainfall Driver Factor (0 - 100)
    # 180mm+ in 24 hours triggers severe flash / riverine flooding
    score_rainfall = min(100.0, (max_rainfall / 180.0) * 100.0)

    # 3. Floodplain Spatial Extent Factor (0 - 100)
    # 5+ contiguous radar pixels in a sub-basin denotes a large-scale inundation plain
    score_extent = min(100.0, (pixel_count / 5.0) * 100.0)

    # 4. Confidence Factor (0 - 100)
    score_confidence = mean_prob * 100.0

    # Weighted Sum
    priority_score = (
        (score_inundation * 0.35) +
        (score_rainfall * 0.30) +
        (score_extent * 0.20) +
        (score_confidence * 0.15)
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

    return {
        "priority_score": priority_score,
        "priority_level": level,
        "factors": {
            "inundation_factor": round(score_inundation, 1),
            "rainfall_factor": round(score_rainfall, 1),
            "extent_factor": round(score_extent, 1),
            "confidence_factor": round(score_confidence, 1)
        },
        "stats": {
            "pixel_count": pixel_count,
            "mean_backscatter_db": round(mean_sar, 1),
            "mean_backscatter_diff_db": round(mean_diff, 1),
            "max_rainfall_mm": round(max_rainfall, 1),
            "mean_rainfall_mm": round(mean_rainfall, 1),
            "mean_confidence": round(mean_prob, 2)
        }
    }


def compute_flood_geometry_and_evidence(cluster_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Computes anomaly-weighted centroid, estimated inundated surface area (sq km),
    and radar speckle uncertainty metric.
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

    delta_lat_km = max(1.0, (lat_max - lat_min) * 111.0)
    delta_lon_km = max(1.0, (lon_max - lon_min) * 111.0 * math.cos(math.radians(centroid_lat)))

    # Inundation footprint area in sq km
    inundated_area_sqkm = round(max(0.8, (delta_lat_km * delta_lon_km) * (math.pi / 4.0)), 2)

    # Uncertainty metric: radar speckle variance + dispersion
    pixel_count = len(cluster_df)
    dispersion = math.sqrt(delta_lat_km**2 + delta_lon_km**2)
    uncertainty_score = round(min(1.0, max(0.04, (dispersion / 25.0) / math.sqrt(pixel_count))), 2)

    return {
        "centroid_lat": round(centroid_lat, 5),
        "centroid_lon": round(centroid_lon, 5),
        "inundated_area_sqkm": inundated_area_sqkm,
        "uncertainty_score": uncertainty_score,
        "bbox": [round(lat_min, 4), round(lon_min, 4), round(lat_max, 4), round(lon_max, 4)]
    }


def process_flood_incidents(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Processes Sentinel-1 SAR and GPM data into prioritized flood incidents.
    """
    clustered_df = cluster_flood_zones(df)
    incidents = []

    grouped = clustered_df.groupby("cluster_id")

    for cluster_id, group in grouped:
        is_isolated = (cluster_id == -1)

        if is_isolated:
            for idx, row in group.iterrows():
                single_df = pd.DataFrame([row])
                score_data = calculate_transparent_flood_priority(single_df)
                geom_data = compute_flood_geometry_and_evidence(single_df)

                region = str(row.get("region_name", "Hydrological Basin"))
                uid = f"INC-FLOOD-ISO-{abs(hash(str(row['latitude']) + str(row['longitude']))) % 10000:04d}"
                incidents.append({
                    "incident_uid": uid,
                    "title": f"Local Inundation Alert: {region}",
                    "hazard_type": "FLOOD",
                    "status": "ACTIVE",
                    "priority_level": score_data["priority_level"],
                    "priority_score": score_data["priority_score"],
                    "confidence_score": score_data["stats"]["mean_confidence"],
                    "centroid_lat": geom_data["centroid_lat"],
                    "centroid_lon": geom_data["centroid_lon"],
                    "affected_area_sqkm": geom_data["inundated_area_sqkm"],
                    "summary": (
                        f"Isolated SAR surface inundation detection in {region}. "
                        f"Backscatter drop: {row['backscatter_diff_db']:.1f} dB. "
                        f"24h Rainfall: {row['gpm_rainfall_mm_24h']:.1f} mm. "
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
            score_data = calculate_transparent_flood_priority(group)
            geom_data = compute_flood_geometry_and_evidence(group)

            first_row = group.iloc[0]
            region = str(first_row.get("region_name", "River Basin"))
            uid = f"INC-FLOOD-CLS-{cluster_id + 201:03d}"
            stats = score_data["stats"]

            title = f"Major Flood Inundation Complex: {region} ({geom_data['inundated_area_sqkm']} km²)"
            summary = (
                f"Severe inundation across {region} spanning ~{geom_data['inundated_area_sqkm']} sq km. "
                f"Sentinel-1 C-Band SAR observed mean backscatter drop of {stats['mean_backscatter_diff_db']} dB. "
                f"NASA GPM registered peak 24h precipitation of {stats['max_rainfall_mm']} mm. "
                f"Priority rated {score_data['priority_level']} ({score_data['priority_score']}/100)."
            )

            incidents.append({
                "incident_uid": uid,
                "title": title,
                "hazard_type": "FLOOD",
                "status": "ACTIVE",
                "priority_level": score_data["priority_level"],
                "priority_score": score_data["priority_score"],
                "confidence_score": stats["mean_confidence"],
                "centroid_lat": geom_data["centroid_lat"],
                "centroid_lon": geom_data["centroid_lon"],
                "affected_area_sqkm": geom_data["inundated_area_sqkm"],
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


def ingest_flood_data_to_db(db_conn) -> Dict[str, Any]:
    """
    Ingests Sentinel-1 SAR and NASA GPM data into SQLite database.
    """
    df = load_flood_data()
    incidents = process_flood_incidents(df)

    cursor = db_conn.cursor()

    # Clear prior flood observations and incidents to prevent duplicates during sync
    cursor.execute("DELETE FROM hazards WHERE source IN ('SENTINEL_1', 'NASA_GPM')")
    cursor.execute("DELETE FROM incidents WHERE hazard_type = 'FLOOD'")

    # Insert individual SAR hazard detections
    hazard_rows = []
    for _, row in df.iterrows():
        hazard_rows.append((
            "SENTINEL_1",
            "FLOOD",
            float(row["latitude"]),
            float(row["longitude"]),
            float(abs(row["backscatter_diff_db"])),  # Intensity = backscatter drop magnitude
            float(row["inundation_prob"]),
            f"{row.get('observation_date', '2026-10-30')}T12:00:00Z",
            json.dumps({
                "sar_backscatter_db": float(row["sar_backscatter_db"]),
                "baseline_backscatter_db": float(row["baseline_backscatter_db"]),
                "backscatter_diff_db": float(row["backscatter_diff_db"]),
                "polarization": str(row.get("polarization", "VH")),
                "gpm_rainfall_mm_24h": float(row.get("gpm_rainfall_mm_24h", 0.0)),
                "orbit_pass": str(row.get("orbit_pass", "DESCENDING")),
                "region_name": str(row.get("region_name", "River Basin"))
            })
        ))

    cursor.executemany(
        """
        INSERT INTO hazards (source, hazard_type, latitude, longitude, intensity_value, confidence, observation_timestamp, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        hazard_rows
    )

    # Insert prioritized flood incidents
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

    # Update source sync status for both Sentinel-1 and NASA GPM
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        """
        UPDATE source_sync_status
        SET last_sync_timestamp = ?, status = 'READY', records_count = ?, message = ?
        WHERE source_name = 'SENTINEL_1'
        """,
        (now_iso, len(df), f"Ingested {len(df)} SAR inundation observations and formed {len(incidents)} flood zones.")
    )

    cursor.execute(
        """
        UPDATE source_sync_status
        SET last_sync_timestamp = ?, status = 'READY', records_count = ?, message = ?
        WHERE source_name = 'NASA_GPM'
        """,
        (now_iso, len(df), f"Correlated {len(df)} IMERG 24h precipitation cells with SAR backscatter anomalies.")
    )

    # Log action to audit log
    cursor.execute(
        """
        INSERT INTO audit_logs (action, details)
        VALUES (?, ?)
        """,
        ("SENTINEL1_GPM_SYNC", f"Processed {len(df)} SAR flood pixels -> {len(incidents)} flood incidents")
    )

    db_conn.commit()

    return {
        "status": "success",
        "inundation_pixels_ingested": len(df),
        "flood_incidents_formed": len(incidents)
    }

