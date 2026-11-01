"""
Forest Fire Monitoring Service.
Handles NASA FIRMS active fire satellite data ingestion,
geospatial DBSCAN clustering, transparent priority scoring, and uncertainty estimation.
"""

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple, Any

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

# Earth radius in kilometers for Haversine distance computations
EARTH_RADIUS_KM = 6371.0088


def load_firms_data(file_path: Path = None) -> pd.DataFrame:
    """
    Loads NASA FIRMS active fire satellite observations.
    Uses reference dataset if custom path is not specified.
    """
    target_path = file_path or (
        Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "nasa_firms_reference.csv"
    )

    if not Path(target_path).exists():
        raise FileNotFoundError(f"NASA FIRMS observation file not found at: {target_path}")

    df = pd.read_csv(target_path)

    # Standardize column types and sanitize values
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["frp"] = pd.to_numeric(df["frp"], errors="coerce").fillna(5.0)

    # Normalize confidence string (nominal, high, low) to numerical fraction
    def parse_confidence(val):
        if pd.isna(val):
            return 0.5
        v = str(val).strip().lower()
        if v == "high" or v == "h":
            return 0.95
        elif v == "nominal" or v == "n":
            return 0.75
        elif v == "low" or v == "l":
            return 0.40
        try:
            num = float(v)
            return min(1.0, max(0.0, num / 100.0 if num > 1.0 else num))
        except ValueError:
            return 0.5

    df["confidence_numeric"] = df["confidence"].apply(parse_confidence)

    # Normalize daynight ('D' -> 0.0, 'N' -> 1.0)
    df["is_night"] = df["daynight"].astype(str).str.upper().apply(lambda x: 1.0 if x == "N" else 0.0)

    # Drop invalid rows
    df = df.dropna(subset=["latitude", "longitude", "frp"])
    return df


def cluster_fire_hotspots(df: pd.DataFrame, eps_km: float = 8.0, min_samples: int = 2) -> pd.DataFrame:
    """
    Performs geospatial density-based clustering (DBSCAN) using Haversine distance.
    Groups contiguous active fire pixels into distinct wildfire incidents.
    
    :param df: DataFrame containing latitude and longitude columns.
    :param eps_km: Maximum search radius in kilometers (converted to radians).
    :param min_samples: Minimum detections to qualify as a multi-pixel fire complex.
    :return: DataFrame with 'cluster_id' column attached.
    """
    if df.empty:
        df["cluster_id"] = []
        return df

    # Convert coordinates from degrees to radians for Haversine metric
    coords_rad = np.radians(df[["latitude", "longitude"]].to_numpy())

    # eps in radians = eps_km / Earth's radius
    eps_rad = eps_km / EARTH_RADIUS_KM

    db = DBSCAN(eps=eps_rad, min_samples=min_samples, metric="haversine", algorithm="ball_tree")
    df = df.copy()
    df["cluster_id"] = db.fit_predict(coords_rad)

    return df


def calculate_transparent_fire_priority(cluster_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculates an explainable, deterministic multi-factor priority score (0 - 100).
    
    Formula components:
    1. Intensity (FRP Factor, 40% weight): Thermal energy output in Megawatts (MW).
    2. Detection Confidence (25% weight): Satellite sensor reliability.
    3. Cluster Extent & Density (20% weight): Number of active thermal pixels.
    4. Nighttime Persistence (15% weight): Continued combustion without solar heating.
    """
    pixel_count = len(cluster_df)
    mean_frp = float(cluster_df["frp"].mean())
    max_frp = float(cluster_df["frp"].max())
    total_frp = float(cluster_df["frp"].sum())

    # 1. FRP Intensity Sub-score (0 - 100)
    # 100 MW or above represents an exceptionally vigorous wildfire front
    frp_metric = (mean_frp * 0.5) + (max_frp * 0.5)
    score_frp = min(100.0, (frp_metric / 80.0) * 100.0)

    # 2. Confidence Sub-score (0 - 100)
    mean_conf = float(cluster_df["confidence_numeric"].mean())
    score_conf = mean_conf * 100.0

    # 3. Cluster Density Sub-score (0 - 100)
    # 5+ VIIRS detections in a single cluster signifies a significant incident
    score_cluster = min(100.0, (pixel_count / 5.0) * 100.0)

    # 4. Nighttime Persistence Sub-score (0 - 100)
    night_ratio = float(cluster_df["is_night"].mean())
    score_night = night_ratio * 100.0

    # Weighted Sum
    priority_score = (
        (score_frp * 0.40) +
        (score_conf * 0.25) +
        (score_cluster * 0.20) +
        (score_night * 0.15)
    )
    priority_score = round(max(5.0, min(99.0, priority_score)), 1)

    # Priority Level Categorization
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
            "frp_factor": round(score_frp, 1),
            "confidence_factor": round(score_conf, 1),
            "cluster_density_factor": round(score_cluster, 1),
            "night_persistence_factor": round(score_night, 1)
        },
        "stats": {
            "pixel_count": pixel_count,
            "mean_frp_mw": round(mean_frp, 2),
            "max_frp_mw": round(max_frp, 2),
            "total_frp_mw": round(total_frp, 2),
            "mean_confidence": round(mean_conf, 2),
            "night_ratio": round(night_ratio, 2)
        }
    }


def compute_incident_geometry_and_evidence(cluster_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Computes FRP-weighted centroid, estimated spatial footprint (sq km), and uncertainty metric.
    """
    # Weighted centroid by FRP so highest heat core guides map center
    total_weight = cluster_df["frp"].sum()
    if total_weight > 0:
        centroid_lat = float((cluster_df["latitude"] * cluster_df["frp"]).sum() / total_weight)
        centroid_lon = float((cluster_df["longitude"] * cluster_df["frp"]).sum() / total_weight)
    else:
        centroid_lat = float(cluster_df["latitude"].mean())
        centroid_lon = float(cluster_df["longitude"].mean())

    # Approximate footprint area: bounding extent + pixel resolution buffer (0.375 km for VIIRS)
    lat_min, lat_max = cluster_df["latitude"].min(), cluster_df["latitude"].max()
    lon_min, lon_max = cluster_df["longitude"].min(), cluster_df["longitude"].max()

    delta_lat_km = max(0.375, (lat_max - lat_min) * 111.0)
    delta_lon_km = max(0.375, (lon_max - lon_min) * 111.0 * math.cos(math.radians(centroid_lat)))
    
    # Area approximation in sq km (with elliptical correction)
    affected_area_sqkm = round(max(0.2, (delta_lat_km * delta_lon_km) * (math.pi / 4.0)), 2)

    # Uncertainty metric: higher dispersion + lower pixel count = higher uncertainty
    dispersion = math.sqrt(delta_lat_km**2 + delta_lon_km**2)
    pixel_count = len(cluster_df)
    uncertainty_score = round(min(1.0, max(0.05, (dispersion / 15.0) / math.sqrt(pixel_count))), 2)

    return {
        "centroid_lat": round(centroid_lat, 5),
        "centroid_lon": round(centroid_lon, 5),
        "affected_area_sqkm": affected_area_sqkm,
        "uncertainty_score": uncertainty_score,
        "bbox": [round(lat_min, 4), round(lon_min, 4), round(lat_max, 4), round(lon_max, 4)]
    }


def process_fire_incidents(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Executes the full pipeline: clustering, priority scoring, geometry estimation,
    and incident summary compilation.
    """
    clustered_df = cluster_fire_hotspots(df)
    incidents = []

    # Process multi-point clusters
    grouped = clustered_df.groupby("cluster_id")

    for cluster_id, group in grouped:
        is_isolated = (cluster_id == -1)
        
        # If noise (-1), we treat each high-FRP observation individually
        if is_isolated:
            for idx, row in group.iterrows():
                single_df = pd.DataFrame([row])
                score_data = calculate_transparent_fire_priority(single_df)
                geom_data = compute_incident_geometry_and_evidence(single_df)
                
                uid = f"INC-FIRE-ISO-{abs(hash(str(row['latitude']) + str(row['longitude']))) % 10000:04d}"
                incidents.append({
                    "incident_uid": uid,
                    "title": f"Isolated Active Thermal Anomaly (FRP: {row['frp']:.1f} MW)",
                    "hazard_type": "FIRE",
                    "status": "ACTIVE",
                    "priority_level": score_data["priority_level"],
                    "priority_score": score_data["priority_score"],
                    "confidence_score": score_data["stats"]["mean_confidence"],
                    "centroid_lat": geom_data["centroid_lat"],
                    "centroid_lon": geom_data["centroid_lon"],
                    "affected_area_sqkm": geom_data["affected_area_sqkm"],
                    "summary": (
                        f"Isolated VIIRS thermal detection with {row['frp']:.1f} MW radiative power. "
                        f"Confidence: {row['confidence']}. Uncertainty: {geom_data['uncertainty_score']}."
                    ),
                    "evidence_json": json.dumps({
                        "scores": score_data,
                        "geometry": geom_data,
                        "detections_count": 1
                    }),
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
        else:
            score_data = calculate_transparent_fire_priority(group)
            geom_data = compute_incident_geometry_and_evidence(group)
            
            uid = f"INC-FIRE-CLS-{cluster_id + 101:03d}"
            stats = score_data["stats"]
            title = f"Wildfire Complex ({stats['pixel_count']} Hotspot Pixels, {stats['total_frp_mw']:.1f} MW Total FRP)"
            
            summary = (
                f"Clustered wildfire incident spanning ~{geom_data['affected_area_sqkm']} sq km. "
                f"Peak FRP reached {stats['max_frp_mw']:.1f} MW across {stats['pixel_count']} contiguous sensor observations. "
                f"Priority rated {score_data['priority_level']} ({score_data['priority_score']}/100)."
            )

            incidents.append({
                "incident_uid": uid,
                "title": title,
                "hazard_type": "FIRE",
                "status": "ACTIVE",
                "priority_level": score_data["priority_level"],
                "priority_score": score_data["priority_score"],
                "confidence_score": stats["mean_confidence"],
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

    # Sort incidents descending by priority score
    incidents.sort(key=lambda x: x["priority_score"], reverse=True)
    return incidents


def ingest_fire_data_to_db(db_conn) -> Dict[str, Any]:
    """
    Ingests NASA FIRMS observations and clustered incidents directly into SQLite.
    """
    df = load_firms_data()
    incidents = process_fire_incidents(df)

    cursor = db_conn.cursor()

    # Clear prior fire hazards & incidents to prevent duplicates during sync
    cursor.execute("DELETE FROM hazards WHERE source = 'NASA_FIRMS'")
    cursor.execute("DELETE FROM incidents WHERE hazard_type = 'FIRE'")

    # Insert individual hazard observations
    hazard_rows = []
    for _, row in df.iterrows():
        hazard_rows.append((
            "NASA_FIRMS",
            "FIRE",
            float(row["latitude"]),
            float(row["longitude"]),
            float(row["frp"]),
            float(row["confidence_numeric"]),
            f"{row.get('acq_date', '2026-10-30')}T{str(row.get('acq_time', '0000')).zfill(4)}:00Z",
            json.dumps({
                "satellite": str(row.get("satellite", "N")),
                "instrument": str(row.get("instrument", "VIIRS")),
                "bright_ti4": float(row.get("bright_ti4", 0.0)),
                "daynight": str(row.get("daynight", "D"))
            })
        ))

    cursor.executemany(
        """
        INSERT INTO hazards (source, hazard_type, latitude, longitude, intensity_value, confidence, observation_timestamp, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        hazard_rows
    )

    # Insert synthesized prioritized incidents
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

    # Update source sync table
    cursor.execute(
        """
        UPDATE source_sync_status
        SET last_sync_timestamp = ?, status = 'READY', records_count = ?, message = ?
        WHERE source_name = 'NASA_FIRMS'
        """,
        (
            datetime.now(timezone.utc).isoformat(),
            len(df),
            f"Successfully synced {len(df)} fire observations and formed {len(incidents)} prioritized incidents."
        )
    )

    # Log action to audit log
    cursor.execute(
        """
        INSERT INTO audit_logs (action, details)
        VALUES (?, ?)
        """,
        ("NASA_FIRMS_SYNC", f"Processed {len(df)} active thermal pixels -> {len(incidents)} clusters")
    )

    db_conn.commit()

    return {
        "status": "success",
        "hotspots_ingested": len(df),
        "incidents_formed": len(incidents)
    }

