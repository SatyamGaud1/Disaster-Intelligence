"""
API Blueprint: Provides RESTful endpoints for health checks, system telemetry,
incident data, and hazard domain pipelines.
"""

from datetime import datetime, timezone
import io
from flask import Blueprint, jsonify, current_app, request, Response, session
from app.database import get_db
from app.services.fire_service import ingest_fire_data_to_db
from app.services.flood_service import ingest_flood_data_to_db
from app.services.drought_service import ingest_drought_data_to_db
from app.services.exposure_service import calculate_nearby_exposure, compute_composite_incident_priority
from app.services.summary_service import generate_incident_summary
from app.services.report_service import generate_incident_pdf_report
from app.services.history_service import compare_incident_with_history
from app.services.risk_service import (
    get_fire_model_metrics,
    predict_fire_risk_from_params,
    get_monitored_fire_risk_zones,
    get_flood_model_metrics,
    predict_flood_risk_from_params,
    get_monitored_flood_risk_zones,
    get_drought_model_metrics,
    predict_drought_risk_from_params,
    get_monitored_drought_risk_zones,
    get_cyclone_model_metrics,
    predict_cyclone_risk_from_params,
    get_monitored_cyclone_risk_zones
)
from app.services.cyclone_service import (
    get_available_storms,
    get_active_cyclones,
    get_cyclone_track_data,
    get_official_advisories
)
from app.services.weather_service import (
    get_weather_presets,
    get_live_weather
)
from app.services.response_service import (
    get_organizations,
    get_organization_by_id,
    find_nearby_organizations,
    create_emergency_request,
    update_request_status,
    get_emergency_requests,
    get_request_history,
    get_response_dashboard_stats,
    authenticate_org_user,
    get_user_by_token,
    record_team_location,
    get_latest_team_location,
    ORGANIZATION_CATEGORIES,
    RESPONSE_STATUSES
)
from app.services.evacuation_service import (
    find_nearby_shelters,
    find_nearby_hospitals,
    get_shelter_by_id,
    update_shelter_occupancy,
    calculate_evacuation_routes,
    assess_route_risk,
    get_evacuation_hazards_geojson,
    get_evacuation_dashboard_stats
)

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/health", methods=["GET"])
def health_check():
    """
    System health check endpoint.
    Verifies API availability and SQLite database responsiveness.
    """
    db_status = "unhealthy"
    db_path = str(current_app.config.get("DATABASE_PATH", ""))

    try:
        db = get_db()
        cursor = db.execute("SELECT 1;")
        if cursor.fetchone():
            db_status = "healthy"
    except Exception as exc:
        db_status = f"error: {str(exc)}"

    return jsonify({
        "status": "healthy" if db_status == "healthy" else "degraded",
        "service": "Disaster Intelligence Backend",
        "version": "1.0.0-alpha",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "database": {
            "status": db_status,
            "path": db_path
        }
    }), 200 if db_status == "healthy" else 503


@api_bp.route("/sources", methods=["GET"])
def list_sources():
    """Returns the operational status of all satellite data sources."""
    try:
        db = get_db()
        cursor = db.execute(
            "SELECT source_name, last_sync_timestamp, status, records_count, message FROM source_sync_status"
        )
        sources = [dict(row) for row in cursor.fetchall()]
        return jsonify({
            "status": "success",
            "count": len(sources),
            "sources": sources
        }), 200
    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": str(exc)
        }), 500


@api_bp.route("/stats", methods=["GET"])
def get_system_stats():
    """Returns top-level metric counters for dashboard KPI cards."""
    try:
        db = get_db()
        
        # Count total and active incidents
        total_incidents = db.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
        critical_count = db.execute(
            "SELECT COUNT(*) FROM incidents WHERE priority_level = 'CRITICAL'"
        ).fetchone()[0]
        active_hazards = db.execute("SELECT COUNT(*) FROM hazards").fetchone()[0]

        return jsonify({
            "status": "success",
            "metrics": {
                "active_incidents": total_incidents,
                "critical_priority": critical_count,
                "detected_hazards": active_hazards,
                "satellite_constellations": 4  # FIRMS, Sentinel-1, Sentinel-2, GPM
            }
        }), 200
    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": str(exc)
        }), 500


@api_bp.route("/incidents", methods=["GET"])
def get_sample_incidents():
    """Returns prioritized incidents from the SQLite database."""
    try:
        db = get_db()
        hazard_filter = request.args.get("hazard_type", "").upper()

        query = """
            SELECT incident_uid, title, hazard_type, status, priority_level,
                   priority_score, confidence_score, centroid_lat, centroid_lon,
                   affected_area_sqkm, summary, created_at
            FROM incidents
        """
        params = []
        if hazard_filter in ("FIRE", "FLOOD", "DROUGHT"):
            query += " WHERE hazard_type = ?"
            params.append(hazard_filter)

        query += " ORDER BY priority_score DESC"

        cursor = db.execute(query, params)
        records = [dict(row) for row in cursor.fetchall()]

        # If database is freshly initialized and empty, auto-sync across all 3 satellite pipelines
        if not records and not hazard_filter:
            try:
                ingest_fire_data_to_db(db)
                ingest_flood_data_to_db(db)
                ingest_drought_data_to_db(db)
                cursor = db.execute(query, params)
                records = [dict(row) for row in cursor.fetchall()]
            except Exception:
                pass

        return jsonify({
            "status": "success",
            "count": len(records),
            "incidents": records
        }), 200
    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": str(exc)
        }), 500


@api_bp.route("/incidents/<incident_uid>", methods=["GET"])
def get_incident_detail(incident_uid):
    """
    Returns deep-dive intelligence for a single incident including exposure metrics,
    synthesized natural language summary, and historical comparison.
    """
    try:
        db = get_db()
        row = db.execute(
            """
            SELECT incident_uid, title, hazard_type, status, priority_level,
                   priority_score, confidence_score, centroid_lat, centroid_lon,
                   affected_area_sqkm, summary, created_at, updated_at
            FROM incidents
            WHERE incident_uid = ?
            """,
            (incident_uid,)
        ).fetchone()

        if not row:
            return jsonify({"status": "error", "message": f"Incident '{incident_uid}' not found"}), 404

        incident = dict(row)

        # 1. Compute exposure & infrastructure vulnerability
        exposure = calculate_nearby_exposure(
            incident["centroid_lat"],
            incident["centroid_lon"],
            incident["affected_area_sqkm"],
            incident["hazard_type"]
        )

        # 2. Compute composite priority score
        composite = compute_composite_incident_priority(incident["priority_score"], exposure["exposure_score"])

        # 3. Generate natural language summary & tactical directives
        summary_data = generate_incident_summary(incident, exposure)

        # 4. Compute historical comparison
        history_data = compare_incident_with_history(incident)

        return jsonify({
            "status": "success",
            "incident": incident,
            "exposure": exposure,
            "composite_priority": composite,
            "summary_intel": summary_data,
            "historical_comparison": history_data
        }), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/incidents/<incident_uid>/pdf", methods=["GET"])
def download_incident_pdf(incident_uid):
    """
    Generates and downloads a printable emergency incident PDF report.
    """
    try:
        db = get_db()
        row = db.execute(
            """
            SELECT incident_uid, title, hazard_type, status, priority_level,
                   priority_score, confidence_score, centroid_lat, centroid_lon,
                   affected_area_sqkm, summary, created_at
            FROM incidents
            WHERE incident_uid = ?
            """,
            (incident_uid,)
        ).fetchone()

        if not row:
            return jsonify({"status": "error", "message": f"Incident '{incident_uid}' not found"}), 404

        incident = dict(row)
        exposure = calculate_nearby_exposure(
            incident["centroid_lat"],
            incident["centroid_lon"],
            incident["affected_area_sqkm"],
            incident["hazard_type"]
        )
        summary_data = generate_incident_summary(incident, exposure)

        pdf_bytes = generate_incident_pdf_report(incident, exposure, summary_data)

        filename = f"DisasterIntel_Report_{incident_uid}.pdf"
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/incidents/<incident_uid>/compare", methods=["GET"])
def get_incident_comparison(incident_uid):
    """
    Returns historical comparison metrics against multi-year disaster records.
    """
    try:
        db = get_db()
        row = db.execute(
            """
            SELECT incident_uid, title, hazard_type, status, priority_level,
                   priority_score, confidence_score, centroid_lat, centroid_lon,
                   affected_area_sqkm, summary
            FROM incidents
            WHERE incident_uid = ?
            """,
            (incident_uid,)
        ).fetchone()

        if not row:
            return jsonify({"status": "error", "message": f"Incident '{incident_uid}' not found"}), 404

        comparison = compare_incident_with_history(dict(row))
        return jsonify({"status": "success", "comparison": comparison}), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


# ==============================================================================
# FOREST FIRE MONITORING ENDPOINTS (NASA FIRMS PIPELINE)
# ==============================================================================

@api_bp.route("/fire/sync", methods=["POST"])
def sync_fire_data():
    """
    Triggers the NASA FIRMS data ingestion, DBSCAN clustering,
    and priority scoring pipeline.
    """
    try:
        db = get_db()
        result = ingest_fire_data_to_db(db)
        return jsonify({
            "status": "success",
            "message": "NASA FIRMS fire observations synchronized successfully.",
            "details": result
        }), 200
    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": f"Failed to sync fire data: {str(exc)}"
        }), 500


@api_bp.route("/fire/hotspots", methods=["GET"])
def get_fire_hotspots():
    """
    Returns raw individual thermal anomaly hotspot detections from NASA FIRMS.
    """
    try:
        db = get_db()
        cursor = db.execute(
            """
            SELECT id, source, latitude, longitude, intensity_value AS frp,
                   confidence, observation_timestamp, metadata_json
            FROM hazards
            WHERE source = 'NASA_FIRMS'
            ORDER BY intensity_value DESC
            """
        )
        hotspots = [dict(row) for row in cursor.fetchall()]
        return jsonify({
            "status": "success",
            "count": len(hotspots),
            "hotspots": hotspots
        }), 200
    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": str(exc)
        }), 500


@api_bp.route("/fire/incidents", methods=["GET"])
def get_fire_incidents():
    """
    Returns clustered wildfire incidents with transparent priority rankings.
    """
    try:
        db = get_db()
        cursor = db.execute(
            """
            SELECT incident_uid, title, hazard_type, status, priority_level,
                   priority_score, confidence_score, centroid_lat, centroid_lon,
                   affected_area_sqkm, summary, created_at
            FROM incidents
            WHERE hazard_type = 'FIRE'
            ORDER BY priority_score DESC
            """
        )
        fire_incidents = [dict(row) for row in cursor.fetchall()]
        return jsonify({
            "status": "success",
            "count": len(fire_incidents),
            "incidents": fire_incidents
        }), 200
    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": str(exc)
        }), 500


# ==============================================================================
# FLOOD MONITORING ENDPOINTS (COPERNICUS SENTINEL-1 SAR & NASA GPM)
# ==============================================================================

@api_bp.route("/flood/sync", methods=["POST"])
def sync_flood_data():
    """
    Triggers the Copernicus Sentinel-1 SAR & NASA GPM data ingestion,
    DBSCAN clustering, and flood priority scoring pipeline.
    """
    try:
        db = get_db()
        result = ingest_flood_data_to_db(db)
        return jsonify({
            "status": "success",
            "message": "Copernicus Sentinel-1 & NASA GPM observations synchronized successfully.",
            "details": result
        }), 200
    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": f"Failed to sync flood data: {str(exc)}"
        }), 500


@api_bp.route("/flood/inundation", methods=["GET"])
def get_flood_inundation_pixels():
    """
    Returns raw SAR inundated surface vector detections from Sentinel-1.
    """
    try:
        db = get_db()
        cursor = db.execute(
            """
            SELECT id, source, latitude, longitude, intensity_value AS backscatter_drop_db,
                   confidence AS inundation_prob, observation_timestamp, metadata_json
            FROM hazards
            WHERE source = 'SENTINEL_1'
            ORDER BY intensity_value DESC
            """
        )
        pixels = [dict(row) for row in cursor.fetchall()]
        return jsonify({
            "status": "success",
            "count": len(pixels),
            "inundation_pixels": pixels
        }), 200
    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": str(exc)
        }), 500


@api_bp.route("/flood/incidents", methods=["GET"])
def get_flood_incidents():
    """
    Returns clustered flood plain incidents with transparent priority rankings.
    """
    try:
        db = get_db()
        cursor = db.execute(
            """
            SELECT incident_uid, title, hazard_type, status, priority_level,
                   priority_score, confidence_score, centroid_lat, centroid_lon,
                   affected_area_sqkm, summary, created_at
            FROM incidents
            WHERE hazard_type = 'FLOOD'
            ORDER BY priority_score DESC
            """
        )
        flood_incidents = [dict(row) for row in cursor.fetchall()]
        return jsonify({
            "status": "success",
            "count": len(flood_incidents),
            "incidents": flood_incidents
        }), 200
    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": str(exc)
        }), 500


# ==============================================================================
# DROUGHT MONITORING ENDPOINTS (COPERNICUS SENTINEL-2 MSI VEGETATION INDICES)
# ==============================================================================

@api_bp.route("/drought/sync", methods=["POST"])
def sync_drought_data():
    """
    Triggers Copernicus Sentinel-2 MSI vegetation indices ingestion,
    DBSCAN agricultural drought corridor clustering, and priority scoring.
    """
    try:
        db = get_db()
        result = ingest_drought_data_to_db(db)
        return jsonify({
            "status": "success",
            "message": "Copernicus Sentinel-2 vegetation observations synchronized successfully.",
            "details": result
        }), 200
    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": f"Failed to sync drought data: {str(exc)}"
        }), 500


@api_bp.route("/drought/observations", methods=["GET"])
def get_drought_observations():
    """
    Returns raw Sentinel-2 MSI multispectral vegetation index observations (NDVI, NDWI, VCI).
    """
    try:
        db = get_db()
        cursor = db.execute(
            """
            SELECT id, source, latitude, longitude, intensity_value AS ndvi_anomaly_drop,
                   confidence AS atmospheric_confidence, observation_timestamp, metadata_json
            FROM hazards
            WHERE source = 'SENTINEL_2'
            ORDER BY intensity_value DESC
            """
        )
        observations = [dict(row) for row in cursor.fetchall()]
        return jsonify({
            "status": "success",
            "count": len(observations),
            "observations": observations
        }), 200
    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": str(exc)
        }), 500


@api_bp.route("/drought/incidents", methods=["GET"])
def get_drought_incidents():
    """
    Returns clustered agricultural drought complexes with transparent priority rankings.
    """
    try:
        db = get_db()
        cursor = db.execute(
            """
            SELECT incident_uid, title, hazard_type, status, priority_level,
                   priority_score, confidence_score, centroid_lat, centroid_lon,
                   affected_area_sqkm, summary, created_at
            FROM incidents
            WHERE hazard_type = 'DROUGHT'
            ORDER BY priority_score DESC
            """
        )
        drought_incidents = [dict(row) for row in cursor.fetchall()]
        return jsonify({
            "status": "success",
            "count": len(drought_incidents),
            "incidents": drought_incidents
        }), 200
    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": str(exc)
        }), 500


# ==============================================================================
# AI / MACHINE LEARNING DISASTER RISK PREDICTION ENDPOINTS
# ==============================================================================

@api_bp.route("/risk/fire/metrics", methods=["GET"])
def get_fire_ml_metrics():
    """
    Returns model validation evaluation metrics, 5-fold cross-validation scores,
    confusion matrix, and feature importances for Forest Fire Risk Prediction.
    """
    try:
        data = get_fire_model_metrics()
        return jsonify(data), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/risk/fire/predict", methods=["POST"])
def predict_fire_risk_endpoint():
    """
    Predicts forest fire risk category (Low/Medium/High), probability score (0-100),
    uncertainty, and factor contributions from user-provided or telemetry parameters:
    - temperature_c: Ambient temperature in °C
    - relative_humidity_pct: Relative humidity in %
    - wind_speed_kmh: Wind velocity in km/h
    - rainfall_mm: Recent 24h rainfall in mm
    - vegetation_ndvi: Sentinel-2 vegetation condition index (0.0 to 1.0)
    """
    try:
        body = request.get_json(silent=True) or {}
        result = predict_fire_risk_from_params(body)
        return jsonify(result), 200
    except ValueError as val_err:
        return jsonify({"status": "error", "message": str(val_err)}), 400
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/risk/fire/zones", methods=["GET"])
def get_fire_risk_zones():
    """
    Returns proactive AI risk predictions across monitored regional wildland corridors
    based on current ambient environmental readings.
    """
    try:
        zones = get_monitored_fire_risk_zones()
        return jsonify({
            "status": "success",
            "count": len(zones),
            "zones": zones
        }), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/risk/flood/metrics", methods=["GET"])
def get_flood_ml_metrics():
    """Returns evaluation metrics and feature importances for Flood Risk ML."""
    try:
        data = get_flood_model_metrics()
        return jsonify(data), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/risk/flood/predict", methods=["POST"])
def predict_flood_risk_endpoint():
    """
    Predicts flood inundation risk category (Low/Medium/High), probability score (0-100),
    uncertainty, and factor contributions from hydrological parameters:
    - precipitation_24h_mm: NASA GPM 24h rainfall
    - soil_moisture_pct: Soil moisture saturation %
    - radar_backscatter_drop_db: Sentinel-1 SAR backscatter drop in dB
    - elevation_m: Surface elevation in meters
    - river_proximity_km: Distance to river basin in km
    """
    try:
        body = request.get_json(silent=True) or {}
        result = predict_flood_risk_from_params(body)
        return jsonify(result), 200
    except ValueError as val_err:
        return jsonify({"status": "error", "message": str(val_err)}), 400
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/risk/flood/zones", methods=["GET"])
def get_flood_risk_zones():
    """Returns proactive AI risk predictions across monitored regional river basins."""
    try:
        zones = get_monitored_flood_risk_zones()
        return jsonify({
            "status": "success",
            "count": len(zones),
            "zones": zones
        }), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/risk/drought/metrics", methods=["GET"])
def get_drought_ml_metrics():
    """Returns evaluation metrics and feature importances for Drought Risk ML."""
    try:
        data = get_drought_model_metrics()
        return jsonify(data), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/risk/drought/predict", methods=["POST"])
def predict_drought_risk_endpoint():
    """
    Predicts agricultural drought stress risk category (Low/Medium/High), probability score (0-100),
    uncertainty, and factor contributions from multispectral and climatic parameters:
    - ndvi_anomaly: Sentinel-2 NDVI anomaly (-1.0 to +1.0)
    - ndwi_moisture: Sentinel-2 NDWI canopy liquid moisture (-1.0 to +1.0)
    - vci_percent: Vegetation Condition Index historical percentile (0 - 100%)
    - precipitation_deficit_pct: 90-day rainfall deficit (0 - 100%)
    - soil_temperature_c: Soil root-zone temperature in °C
    """
    try:
        body = request.get_json(silent=True) or {}
        result = predict_drought_risk_from_params(body)
        return jsonify(result), 200
    except ValueError as val_err:
        return jsonify({"status": "error", "message": str(val_err)}), 400
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/risk/drought/zones", methods=["GET"])
def get_drought_risk_zones():
    """Returns proactive AI risk predictions across monitored agricultural belts."""
    try:
        zones = get_monitored_drought_risk_zones()
        return jsonify({
            "status": "success",
            "count": len(zones),
            "zones": zones
        }), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


# ==========================================
# CYCLONE TRACKING & RISK ASSESSMENT ENDPOINTS
# ==========================================

@api_bp.route("/cyclone/storms", methods=["GET"])
def get_cyclone_storms_list():
    """Returns list of all available cyclone systems (active & reference benchmarks)."""
    try:
        storms = get_available_storms()
        return jsonify({
            "status": "success",
            "count": len(storms),
            "storms": storms
        }), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/cyclone/active", methods=["GET"])
def get_active_cyclone_systems():
    """Returns currently monitored tropical cyclone systems with official agency metadata."""
    try:
        systems = get_active_cyclones()
        return jsonify({
            "status": "success",
            "count": len(systems),
            "systems": systems
        }), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/cyclone/tracks", methods=["GET"])
def get_cyclone_tracks():
    """
    Returns separate observed and forecast track coordinates and uncertainty cone.
    Query parameter: ?storm_id=<id>
    """
    try:
        storm_id = request.args.get("storm_id", None)
        track_data = get_cyclone_track_data(storm_id)
        return jsonify({
            "status": "success",
            "data": track_data
        }), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/cyclone/advisories", methods=["GET"])
def get_cyclone_advisories_feed():
    """Returns official tropical cyclone advisories, warnings, and verified source links."""
    try:
        advisories = get_official_advisories()
        return jsonify({
            "status": "success",
            "count": len(advisories),
            "advisories": advisories
        }), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/risk/cyclone/metrics", methods=["GET"])
def get_cyclone_ml_metrics():
    """Returns evaluation metrics, cross-validation results, and feature importances for Cyclone ML."""
    try:
        data = get_cyclone_model_metrics()
        return jsonify(data), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/risk/cyclone/predict", methods=["POST"])
def predict_cyclone_risk_endpoint():
    """
    Predicts cyclone risk category (Low/Medium/High), probability score (0-100),
    uncertainty, and factor contributions from meteorological parameters:
    - central_pressure_hpa: Barometric core pressure in hPa
    - max_sustained_wind_kmh: 1-minute sustained wind in km/h
    - sea_surface_temp_c: Oceanic thermal energy in °C
    - storm_forward_speed_kmh: Translation velocity in km/h
    - coastal_distance_km: Distance to nearest coastline in km
    """
    try:
        body = request.get_json(silent=True) or {}
        result = predict_cyclone_risk_from_params(body)
        return jsonify(result), 200
    except ValueError as val_err:
        return jsonify({"status": "error", "message": str(val_err)}), 400
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/risk/cyclone/zones", methods=["GET"])
def get_cyclone_risk_zones():
    """Returns proactive AI risk predictions across monitored maritime and coastal sectors."""
    try:
        zones = get_monitored_cyclone_risk_zones()
        return jsonify({
            "status": "success",
            "count": len(zones),
            "zones": zones
        }), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


# ==========================================
# LIVE METEOROLOGICAL STATION & AUTO-FILL API
# ==========================================

@api_bp.route("/weather/presets", methods=["GET"])
def get_weather_presets_endpoint():
    """Returns curated meteorological preset stations for 1-click simulator auto-fill."""
    try:
        presets = get_weather_presets()
        return jsonify({
            "status": "success",
            "count": len(presets),
            "presets": presets
        }), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/weather/live", methods=["GET"])
def get_live_weather_endpoint():
    """
    Fetches live real-time weather from Open-Meteo free API for given lat/lon coordinates.
    Maps parameters directly to simulator inputs for Fire, Flood, Drought, and Cyclone.
    Query parameters: ?lat=<float>&lon=<float>
    """
    try:
        lat = float(request.args.get("lat", 22.24))
        lon = float(request.args.get("lon", 68.96))

        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return jsonify({"status": "error", "message": "Invalid latitude (-90 to 90) or longitude (-180 to 180)"}), 400

        weather_data = get_live_weather(lat, lon)
        return jsonify(weather_data), 200
    except ValueError as val_err:
        return jsonify({"status": "error", "message": f"Numerical error: {str(val_err)}"}), 400
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


# ==============================================================================
# EMERGENCY RESPONSE & HELPING ORGANIZATION TRACKING ENDPOINTS
# ==============================================================================

def _get_authenticated_responder():
    """Helper to retrieve current authenticated responder user profile from Bearer token or session."""
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    elif "token" in request.args:
        token = request.args.get("token")

    if token:
        user = get_user_by_token(token)
        if user:
            return user

    user_id = session.get("org_user_id")
    if user_id:
        db = get_db()
        row = db.execute(
            """
            SELECT u.id, u.org_id, u.username, u.full_name, u.role, u.auth_token,
                   o.org_uid, o.name as org_name, o.category as org_category, o.city, o.state, o.availability_status
            FROM organization_users u
            JOIN organizations o ON u.org_id = o.id
            WHERE u.id = ? AND u.is_active = 1
            """,
            (user_id,)
        ).fetchone()
        if row:
            return dict(row)
    return None


@api_bp.route("/response/categories", methods=["GET"])
def get_response_categories_endpoint():
    """Returns supported helping organization categories and lifecycle statuses."""
    return jsonify({
        "status": "success",
        "categories": ORGANIZATION_CATEGORIES,
        "statuses": RESPONSE_STATUSES
    }), 200


@api_bp.route("/response/organizations", methods=["GET"])
def get_organizations_endpoint():
    """Returns list of helping organizations with optional category and availability filters."""
    try:
        category = request.args.get("category")
        availability = request.args.get("availability")
        orgs = get_organizations(category=category, availability=availability)
        return jsonify({
            "status": "success",
            "count": len(orgs),
            "organizations": orgs
        }), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/response/organizations/<int:org_id>", methods=["GET"])
def get_single_organization_endpoint(org_id):
    """Retrieves an organization profile by ID."""
    org = get_organization_by_id(org_id)
    if not org:
        return jsonify({"status": "error", "message": f"Organization {org_id} not found"}), 404
    return jsonify({"status": "success", "organization": org}), 200


@api_bp.route("/response/nearby", methods=["GET"])
def get_nearby_organizations_endpoint():
    """
    Computes distance to registered organizations and returns them sorted by nearest distance.
    Parameters:
      - incident_id: (Optional) looks up incident centroid automatically
      - lat, lon: (Optional) GPS coordinates
      - max_distance_km: (Optional) distance threshold in km
      - category: (Optional) filter by NDRF, SDRF, Fire, Hospital, etc.
    """
    try:
        incident_id = request.args.get("incident_id", type=int)
        lat = request.args.get("lat", type=float)
        lon = request.args.get("lon", type=float)
        max_dist = request.args.get("max_distance_km", type=float)
        category = request.args.get("category")
        limit = request.args.get("limit", default=15, type=int)

        incident_info = None

        if incident_id:
            db = get_db()
            inc_row = db.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
            if not inc_row:
                return jsonify({"status": "error", "message": f"Incident {incident_id} not found"}), 404
            incident_info = dict(inc_row)
            lat = incident_info["centroid_lat"]
            lon = incident_info["centroid_lon"]

        if lat is None or lon is None:
            return jsonify({"status": "error", "message": "Must provide either incident_id or (lat, lon) coordinates"}), 400

        nearby_orgs = find_nearby_organizations(
            lat=lat,
            lon=lon,
            max_distance_km=max_dist,
            category=category,
            limit=limit
        )

        return jsonify({
            "status": "success",
            "incident": incident_info,
            "origin_coordinates": [lat, lon],
            "count": len(nearby_orgs),
            "nearby_organizations": nearby_orgs,
            "organizations": nearby_orgs
        }), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/response/requests", methods=["POST"])
def create_emergency_request_endpoint():
    """
    Dispatches a new emergency response request to an organization.
    Body JSON:
      - incident_id (int, required)
      - org_id (int, required)
      - priority_level (str, optional)
      - requester_name (str, optional)
      - requester_contact (str, optional)
      - remarks (str, optional)
    """
    try:
        body = request.get_json(silent=True) or {}
        incident_id = body.get("incident_id")
        org_id = body.get("org_id") or body.get("organization_id")

        if not incident_id or not org_id:
            return jsonify({"status": "error", "message": "Fields 'incident_id' and 'org_id' are required"}), 400

        result = create_emergency_request(
            incident_id=int(incident_id),
            org_id=int(org_id),
            requester_name=body.get("requester_name", "Emergency Operations Center"),
            requester_contact=body.get("requester_contact"),
            priority_level=body.get("priority_level"),
            remarks=body.get("remarks")
        )
        status_code = 200 if result.get("status") == "warning" else 201
        return jsonify(result), status_code
    except ValueError as val_err:
        return jsonify({"status": "error", "message": str(val_err)}), 400
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/response/requests", methods=["GET"])
def get_emergency_requests_endpoint():
    """
    Lists all emergency response requests joined with incident & organization details.
    Query filters: ?status=... &disaster_type=... &priority=... &org_id=... &incident_id=...
    """
    try:
        incident_id = request.args.get("incident_id", type=int)
        org_id = request.args.get("org_id", type=int)
        status = request.args.get("status")
        disaster_type = request.args.get("disaster_type")
        priority = request.args.get("priority")

        requests_list = get_emergency_requests(
            incident_id=incident_id,
            org_id=org_id,
            status=status,
            disaster_type=disaster_type,
            priority=priority
        )
        return jsonify({
            "status": "success",
            "count": len(requests_list),
            "requests": requests_list
        }), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/response/requests/<int:request_id>", methods=["GET"])
def get_single_request_endpoint(request_id):
    """Retrieves full details for a single request including history audit trail."""
    try:
        reqs = get_emergency_requests()
        matched = next((r for r in reqs if r["id"] == request_id), None)
        if not matched:
            return jsonify({"status": "error", "message": f"Request {request_id} not found"}), 404

        history = get_request_history(request_id)
        latest_location = get_latest_team_location(request_id)

        matched["history"] = history
        matched["latest_team_location"] = latest_location
        return jsonify({"status": "success", "request": matched}), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/response/requests/<int:request_id>/action", methods=["POST"])
def accept_or_reject_request_endpoint(request_id):
    """
    Organization action to ACCEPT (acknowledge) or REJECT an emergency request.
    Body JSON:
      - action: 'ACCEPT' or 'REJECT' (required)
      - remarks: optional notes
      - eta_minutes: optional ETA in minutes if accepted
    """
    try:
        body = request.get_json(silent=True) or {}
        action = (body.get("action") or "").upper()
        remarks = body.get("remarks")
        eta = body.get("eta_minutes", type=int) if body.get("eta_minutes") is not None else None

        if action not in ["ACCEPT", "REJECT"]:
            return jsonify({"status": "error", "message": "Action must be 'ACCEPT' or 'REJECT'"}), 400

        user = _get_authenticated_responder()
        updated_by_id = user["id"] if user else None
        updated_by_name = user["full_name"] if user else body.get("updated_by_name", "Organization Responder")
        verify_org = user["org_id"] if user else None

        new_status = "Acknowledged" if action == "ACCEPT" else "Rejected"

        result = update_request_status(
            request_id=request_id,
            new_status=new_status,
            updated_by_user_id=updated_by_id,
            updated_by_name=updated_by_name,
            remarks=remarks or (f"Request {action.lower()}ed by organization"),
            eta_minutes=eta,
            verify_org_id=verify_org
        )
        return jsonify(result), 200
    except PermissionError as perm_err:
        return jsonify({"status": "error", "message": str(perm_err)}), 403
    except ValueError as val_err:
        return jsonify({"status": "error", "message": str(val_err)}), 400
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/response/requests/<int:request_id>/status", methods=["POST"])
def update_request_status_endpoint(request_id):
    """
    Updates lifecycle status of an emergency request:
    Pending -> Acknowledged -> Dispatched -> On The Way -> Arrived -> Assistance In Progress -> Completed (or Cancelled).
    Body JSON:
      - new_status (str, required)
      - remarks (str, optional)
      - eta_minutes (int, optional)
      - updated_by_name (str, optional)
    """
    try:
        body = request.get_json(silent=True) or {}
        new_status = body.get("new_status")
        remarks = body.get("remarks")
        eta = body.get("eta_minutes")
        if eta is not None:
            eta = int(eta)

        if not new_status:
            return jsonify({"status": "error", "message": "Field 'new_status' is required"}), 400

        user = _get_authenticated_responder()
        updated_by_id = user["id"] if user else None
        updated_by_name = user["full_name"] if user else body.get("updated_by_name", "Authorized Officer")
        verify_org = user["org_id"] if user else None

        result = update_request_status(
            request_id=request_id,
            new_status=new_status,
            updated_by_user_id=updated_by_id,
            updated_by_name=updated_by_name,
            remarks=remarks,
            eta_minutes=eta,
            verify_org_id=verify_org
        )
        return jsonify(result), 200
    except PermissionError as perm_err:
        return jsonify({"status": "error", "message": str(perm_err)}), 403
    except ValueError as val_err:
        return jsonify({"status": "error", "message": str(val_err)}), 400
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/response/requests/<int:request_id>/history", methods=["GET"])
def get_request_history_endpoint(request_id):
    """Returns chronological audit trail for a request."""
    try:
        history = get_request_history(request_id)
        return jsonify({
            "status": "success",
            "request_id": request_id,
            "count": len(history),
            "history": history
        }), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/response/stats", methods=["GET"])
def get_response_stats_endpoint():
    """Returns real-time emergency response dashboard statistics."""
    try:
        stats = get_response_dashboard_stats()
        return jsonify(stats), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/response/requests/<int:request_id>/location", methods=["POST"])
def update_team_location_endpoint(request_id):
    """
    Records verified GPS telemetry from responding team.
    Body JSON:
      - latitude (float, required)
      - longitude (float, required)
      - speed_kmh (float, optional)
      - heading (float, optional)
    """
    try:
        body = request.get_json(silent=True) or {}
        lat = float(body.get("latitude"))
        lon = float(body.get("longitude"))
        speed = float(body.get("speed_kmh", 0.0))
        heading = float(body.get("heading", 0.0))

        result = record_team_location(request_id, lat, lon, speed, heading)
        return jsonify(result), 200
    except (ValueError, TypeError) as val_err:
        return jsonify({"status": "error", "message": f"Invalid coordinate: {str(val_err)}"}), 400
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/response/requests/<int:request_id>/location", methods=["GET"])
def get_team_location_endpoint(request_id):
    """Retrieves latest verified GPS coordinates for responding team."""
    loc = get_latest_team_location(request_id)
    return jsonify({
        "status": "success",
        "request_id": request_id,
        "location": loc
    }), 200


@api_bp.route("/response/notifications", methods=["GET"])
def get_notifications_endpoint():
    """Retrieves in-app notifications for an organization."""
    org_id = request.args.get("org_id", type=int)
    user = _get_authenticated_responder()
    if not org_id and user:
        org_id = user["org_id"]

    if not org_id:
        return jsonify({"status": "error", "message": "Must provide org_id or authenticate"}), 400

    db = get_db()
    cursor = db.execute(
        """
        SELECT * FROM organization_notifications
        WHERE org_id = ?
        ORDER BY created_at DESC LIMIT 30
        """,
        (org_id,)
    )
    notifs = [dict(row) for row in cursor.fetchall()]
    return jsonify({
        "status": "success",
        "org_id": org_id,
        "count": len(notifs),
        "notifications": notifs
    }), 200


# ==============================================================================
# AUTHENTICATION ENDPOINTS
# ==============================================================================

@api_bp.route("/response/auth/login", methods=["POST"])
def org_login_endpoint():
    """
    Authenticates organization responder accounts.
    Body JSON:
      - username (str, required)
      - password (str, required)
    """
    try:
        body = request.get_json(silent=True) or {}
        username = body.get("username", "").strip()
        password = body.get("password", "")

        if not username or not password:
            return jsonify({"status": "error", "message": "Username and password required"}), 400

        user = authenticate_org_user(username, password)
        if not user:
            return jsonify({"status": "error", "message": "Invalid username or password"}), 401

        # Store in session as well
        session["org_user_id"] = user["id"]
        session["org_id"] = user["org_id"]

        return jsonify({
            "status": "success",
            "message": f"Welcome back, {user['full_name']} ({user['org_name']})",
            "token": user["auth_token"],
            "user": user
        }), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/response/auth/logout", methods=["POST"])
def org_logout_endpoint():
    """Clears responder user session."""
    session.pop("org_user_id", None)
    session.pop("org_id", None)
    return jsonify({"status": "success", "message": "Logged out successfully"}), 200


@api_bp.route("/response/auth/me", methods=["GET"])
def get_current_user_endpoint():
    """Returns currently authenticated responder user profile."""
    user = _get_authenticated_responder()
    if not user:
        return jsonify({"status": "error", "authenticated": False, "message": "Not authenticated"}), 401

    return jsonify({
        "status": "success",
        "authenticated": True,
        "user": user
    }), 200


# ==============================================================================
# PHASE 4: SMART EVACUATION & SAFE ROUTE PLANNER ENDPOINTS
# ==============================================================================

@api_bp.route("/evacuation/stats", methods=["GET"])
def get_evacuation_stats_endpoint():
    """Returns real-time evacuation planning statistics (shelters, capacity, hospitals, closures)."""
    try:
        stats = get_evacuation_dashboard_stats()
        return jsonify(stats), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/evacuation/shelters", methods=["GET"])
def list_shelters_endpoint():
    """Returns directory of emergency shelters with optional filters."""
    try:
        category = request.args.get("category")
        status = request.args.get("status")
        db = get_db()
        query = "SELECT * FROM shelters WHERE 1=1"
        params = []
        if category and category.upper() != "ALL":
            query += " AND category = ?"
            params.append(category)
        if status and status.upper() != "ALL":
            query += " AND operating_status = ?"
            params.append(status.upper())
        query += " ORDER BY name ASC"
        cursor = db.execute(query, params)
        shelters = [dict(r) for r in cursor.fetchall()]
        for s in shelters:
            s["available_capacity"] = max(0, s["capacity"] - s["current_occupancy"])
            s["occupancy_pct"] = round((s["current_occupancy"] / s["capacity"]) * 100.0, 1) if s["capacity"] > 0 else 100.0
        return jsonify({
            "status": "success",
            "count": len(shelters),
            "shelters": shelters
        }), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/evacuation/shelters/<int:shelter_id>", methods=["GET"])
def get_shelter_endpoint(shelter_id: int):
    """Retrieves a single shelter by ID with capacity breakdown."""
    shelter = get_shelter_by_id(shelter_id)
    if not shelter:
        return jsonify({"status": "error", "message": f"Shelter {shelter_id} not found"}), 404
    return jsonify({"status": "success", "shelter": shelter}), 200


@api_bp.route("/evacuation/shelters", methods=["POST"])
def create_shelter_endpoint():
    """Adds a new verified emergency shelter record."""
    try:
        data = request.get_json(silent=True) or {}
        name = data.get("name")
        lat = data.get("latitude")
        lon = data.get("longitude")
        cap = data.get("capacity", 500)
        if not name or lat is None or lon is None:
            return jsonify({"status": "error", "message": "Fields 'name', 'latitude', and 'longitude' are required."}), 400

        db = get_db()
        cursor = db.cursor()
        uid = f"SHL-CUSTOM-{int(datetime.now().timestamp())}"
        cursor.execute(
            """
            INSERT INTO shelters (
                shelter_uid, name, category, latitude, longitude,
                address, city, state, contact_phone, capacity, current_occupancy,
                facilities, accessibility_info, operating_status, is_verified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, 'OPEN', 1)
            """,
            (
                uid, name, data.get("category", "CYCLONE_SHELTER"),
                float(lat), float(lon), data.get("address"), data.get("city", "Gujarat"),
                data.get("state", "Gujarat"), data.get("contact_phone"), int(cap),
                data.get("facilities", "Water, Sanitation, Generator"),
                data.get("accessibility_info", "Ground Floor Accessible")
            )
        )
        shelter_id = cursor.lastrowid
        db.commit()
        return jsonify({"status": "success", "shelter_id": shelter_id, "shelter_uid": uid, "message": "Shelter created successfully."}), 201
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/evacuation/shelters/<int:shelter_id>", methods=["PUT"])
def update_shelter_endpoint(shelter_id: int):
    """Updates basic shelter information."""
    try:
        data = request.get_json(silent=True) or {}
        db = get_db()
        row = db.execute("SELECT id FROM shelters WHERE id = ?", (shelter_id,)).fetchone()
        if not row:
            return jsonify({"status": "error", "message": f"Shelter {shelter_id} not found"}), 404

        now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        db.execute(
            """
            UPDATE shelters
            SET name = coalesce(?, name),
                contact_phone = coalesce(?, contact_phone),
                facilities = coalesce(?, facilities),
                accessibility_info = coalesce(?, accessibility_info),
                operating_status = coalesce(?, operating_status),
                updated_at = ?
            WHERE id = ?
            """,
            (
                data.get("name"), data.get("contact_phone"), data.get("facilities"),
                data.get("accessibility_info"), data.get("operating_status"),
                now_ts, shelter_id
            )
        )
        db.commit()
        return jsonify({"status": "success", "message": f"Shelter {shelter_id} updated successfully."}), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/evacuation/shelters/<int:shelter_id>/occupancy", methods=["POST"])
def update_shelter_occupancy_endpoint(shelter_id: int):
    """Updates shelter occupancy and logs capacity transition."""
    try:
        body = request.get_json(silent=True) or {}
        new_occ = body.get("new_occupancy")
        if new_occ is None:
            return jsonify({"status": "error", "message": "Field 'new_occupancy' is required."}), 400

        result = update_shelter_occupancy(
            shelter_id=shelter_id,
            new_occupancy=int(new_occ),
            updated_by=body.get("updated_by", "Evacuation Coordinator"),
            remarks=body.get("remarks")
        )
        return jsonify(result), 200
    except ValueError as val_err:
        return jsonify({"status": "error", "message": str(val_err)}), 400
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/evacuation/shelters/<int:shelter_id>/history", methods=["GET"])
def get_shelter_occupancy_history_endpoint(shelter_id: int):
    """Retrieves capacity audit trail for a shelter."""
    try:
        db = get_db()
        cursor = db.execute(
            """
            SELECT * FROM shelter_capacity_history
            WHERE shelter_id = ?
            ORDER BY timestamp DESC
            """,
            (shelter_id,)
        )
        history = [dict(r) for r in cursor.fetchall()]
        return jsonify({"status": "success", "shelter_id": shelter_id, "history": history}), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/evacuation/hospitals", methods=["GET"])
def list_hospitals_endpoint():
    """Lists emergency hospitals and trauma centers."""
    try:
        f_type = request.args.get("facility_type")
        db = get_db()
        query = "SELECT * FROM emergency_facilities WHERE 1=1"
        params = []
        if f_type and f_type.upper() != "ALL":
            query += " AND facility_type = ?"
            params.append(f_type.upper())
        query += " ORDER BY name ASC"
        cursor = db.execute(query, params)
        facilities = [dict(r) for r in cursor.fetchall()]
        return jsonify({
            "status": "success",
            "count": len(facilities),
            "hospitals": facilities,
            "facilities": facilities
        }), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/evacuation/facilities", methods=["GET"])
def list_facilities_endpoint():
    """Alias for emergency facilities directory."""
    return list_hospitals_endpoint()


@api_bp.route("/evacuation/nearby", methods=["GET"])
def get_nearby_destinations_endpoint():
    """
    Finds nearby shelters and hospitals for a given incident or coordinate pair.
    Query params: ?incident_id=... OR ?lat=...&lon=... &limit=... &type=all|shelters|hospitals
    """
    try:
        incident_id = request.args.get("incident_id", type=int)
        lat = request.args.get("lat", type=float)
        lon = request.args.get("lon", type=float)
        limit = request.args.get("limit", default=10, type=int)
        dest_type = request.args.get("type", default="all").lower()

        incident_info = None
        if incident_id:
            db = get_db()
            inc = db.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
            if not inc:
                return jsonify({"status": "error", "message": f"Incident {incident_id} not found"}), 404
            incident_info = dict(inc)
            lat = incident_info["centroid_lat"]
            lon = incident_info["centroid_lon"]

        if lat is None or lon is None:
            return jsonify({"status": "error", "message": "Must provide incident_id or (lat, lon) coordinates."}), 400

        shelters = []
        hospitals = []
        if dest_type in ["all", "shelters"]:
            shelters = find_nearby_shelters(lat, lon, limit=limit)
        if dest_type in ["all", "hospitals"]:
            hospitals = find_nearby_hospitals(lat, lon, limit=limit)

        return jsonify({
            "status": "success",
            "origin": [lat, lon],
            "incident": incident_info,
            "shelters": shelters,
            "hospitals": hospitals,
            "total_destinations": len(shelters) + len(hospitals)
        }), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/evacuation/route", methods=["POST"])
def calculate_route_endpoint():
    """
    Calculates primary and alternative evacuation routes, evaluates hazard intersections,
    and returns GeoJSON polylines and detailed safety scorecards.
    Body JSON:
      - origin_lat (float, required)
      - origin_lon (float, required)
      - dest_lat (float, required)
      - dest_lon (float, required)
      - incident_id (int, optional)
    """
    try:
        body = request.get_json(silent=True) or {}
        origin_lat = body.get("origin_lat")
        origin_lon = body.get("origin_lon")
        dest_lat = body.get("dest_lat")
        dest_lon = body.get("dest_lon")
        incident_id = body.get("incident_id")

        if origin_lat is None or origin_lon is None or dest_lat is None or dest_lon is None:
            return jsonify({
                "status": "error",
                "message": "Fields 'origin_lat', 'origin_lon', 'dest_lat', and 'dest_lon' are required."
            }), 400

        result = calculate_evacuation_routes(
            origin_lat=float(origin_lat),
            origin_lon=float(origin_lon),
            dest_lat=float(dest_lat),
            dest_lon=float(dest_lon),
            incident_id=int(incident_id) if incident_id else None
        )
        return jsonify(result), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/evacuation/hazards", methods=["GET"])
def get_evacuation_hazards_endpoint():
    """Returns GeoJSON layer of all active road obstacles and satellite hazard zones."""
    try:
        geojson_data = get_evacuation_hazards_geojson()
        return jsonify(geojson_data), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500







