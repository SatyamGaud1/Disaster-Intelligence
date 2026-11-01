"""
Free Public Weather Service (Open-Meteo Integration).
Provides 100% free, zero-key, open-access real-time meteorological observations
for any latitude and longitude, with resilient offline regional fallback.
"""

import json
import math
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

EARTH_RADIUS_KM = 6371.0088

# Curated regional meteorological reference stations across hazard corridors
WEATHER_PRESET_STATIONS = [
    {
        "id": "dwarka_gujarat",
        "name": "Dwarka Coastal Radar (Gujarat)",
        "lat": 22.24,
        "lon": 68.96,
        "region": "Arabian Sea Littoral",
        "defaults": {
            "temperature_c": 32.5,
            "relative_humidity_pct": 78.0,
            "surface_pressure_hpa": 978.0,
            "wind_speed_kmh": 142.0,
            "precipitation_mm": 65.0,
            "sea_surface_temp_c": 30.2,
            "soil_moisture_pct": 74.0,
            "soil_temperature_c": 31.0
        }
    },
    {
        "id": "sundarbans_wb",
        "name": "Sundarbans Estuary (West Bengal)",
        "lat": 21.95,
        "lon": 88.85,
        "region": "Bay of Bengal Mangrove Delta",
        "defaults": {
            "temperature_c": 31.8,
            "relative_humidity_pct": 86.0,
            "surface_pressure_hpa": 962.0,
            "wind_speed_kmh": 165.0,
            "precipitation_mm": 135.0,
            "sea_surface_temp_c": 30.8,
            "soil_moisture_pct": 88.0,
            "soil_temperature_c": 30.5
        }
    },
    {
        "id": "puri_odisha",
        "name": "Puri Coastal Observatory (Odisha)",
        "lat": 19.81,
        "lon": 85.83,
        "region": "Bay of Bengal Coastal Corridor",
        "defaults": {
            "temperature_c": 33.2,
            "relative_humidity_pct": 79.0,
            "surface_pressure_hpa": 994.0,
            "wind_speed_kmh": 72.0,
            "precipitation_mm": 48.0,
            "sea_surface_temp_c": 29.5,
            "soil_moisture_pct": 65.0,
            "soil_temperature_c": 32.0
        }
    },
    {
        "id": "dehradun_forest",
        "name": "Dehradun Forest Reserve (Uttarakhand)",
        "lat": 30.31,
        "lon": 78.03,
        "region": "Himalayan Pine Forest Belt",
        "defaults": {
            "temperature_c": 38.5,
            "relative_humidity_pct": 16.0,
            "surface_pressure_hpa": 1008.0,
            "wind_speed_kmh": 32.0,
            "precipitation_mm": 0.0,
            "sea_surface_temp_c": 25.0,
            "soil_moisture_pct": 22.0,
            "soil_temperature_c": 38.0
        }
    },
    {
        "id": "vidarbha_agro",
        "name": "Vidarbha Agricultural Basin (Maharashtra)",
        "lat": 20.93,
        "lon": 77.75,
        "region": "Semi-Arid Rainfed Farmlands",
        "defaults": {
            "temperature_c": 41.5,
            "relative_humidity_pct": 24.0,
            "surface_pressure_hpa": 1006.0,
            "wind_speed_kmh": 18.0,
            "precipitation_mm": 0.0,
            "sea_surface_temp_c": 26.0,
            "soil_moisture_pct": 18.0,
            "soil_temperature_c": 42.0
        }
    },
    {
        "id": "miami_florida",
        "name": "Miami Coastal Station (Florida, USA)",
        "lat": 25.76,
        "lon": -80.19,
        "region": "North Atlantic Hurricane Alley",
        "defaults": {
            "temperature_c": 31.0,
            "relative_humidity_pct": 82.0,
            "surface_pressure_hpa": 952.0,
            "wind_speed_kmh": 175.0,
            "precipitation_mm": 95.0,
            "sea_surface_temp_c": 30.4,
            "soil_moisture_pct": 76.0,
            "soil_temperature_c": 29.5
        }
    }
]


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes spherical distance in kilometers between two GPS points."""
    r_lat1 = math.radians(lat1)
    r_lat2 = math.radians(lat2)
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat / 2.0)**2 + math.cos(r_lat1) * math.cos(r_lat2) * math.sin(d_lon / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_KM * c


def get_weather_presets() -> List[Dict[str, Any]]:
    """Returns curated meteorological preset stations for 1-click auto-fill."""
    return WEATHER_PRESET_STATIONS


def find_closest_station(lat: float, lon: float) -> Dict[str, Any]:
    """Finds the geographically closest reference station."""
    best = WEATHER_PRESET_STATIONS[0]
    min_dist = float("inf")
    for st in WEATHER_PRESET_STATIONS:
        d = haversine_distance(lat, lon, st["lat"], st["lon"])
        if d < min_dist:
            min_dist = d
            best = st
    return best, round(min_dist, 1)


def get_live_weather(lat: float, lon: float, timeout_sec: float = 2.5) -> Dict[str, Any]:
    """
    Fetches real-time weather from Open-Meteo free API (no API key required).
    Falls back gracefully to the closest regional observation if offline or unreachable.
    """
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat:.4f}&longitude={lon:.4f}"
        f"&current=temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m,precipitation"
        f"&daily=precipitation_sum&timezone=auto"
    )

    data = None
    is_live = False
    source_label = "Open-Meteo Free Public Weather API"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "DisasterIntelligencePlatform/1.0 (Educational/OpenData)"}
        )
        with urllib.request.urlopen(req, timeout=timeout_sec) as response:
            if response.status == 200:
                raw = response.read().decode("utf-8")
                data = json.loads(raw)
                is_live = True
    except Exception:
        # Fall back gracefully to closest preset observation
        data = None

    if is_live and data and "current" in data:
        curr = data["current"]
        temp = float(curr.get("temperature_2m", 28.0))
        humidity = float(curr.get("relative_humidity_2m", 65.0))
        pressure = float(curr.get("surface_pressure", 1010.0))
        wind = float(curr.get("wind_speed_10m", 15.0))
        precip = float(curr.get("precipitation", 0.0))

        # Check daily precipitation sum if available for 24h accumulation
        daily = data.get("daily", {})
        daily_precip_list = daily.get("precipitation_sum", [])
        precip_24h = float(daily_precip_list[0]) if daily_precip_list else precip * 8.0

        # Estimate ocean SST (for marine coordinates, SST tracks within 1-2 degrees of coastal air)
        sst = round(max(24.0, min(32.5, temp * 0.95 + 1.2)), 1)
        soil_moisture = round(min(95.0, max(15.0, humidity * 0.75 + precip * 3.0)), 1)
        soil_temp = round(max(15.0, min(48.0, temp + 2.0)), 1)
        location_desc = f"Live GPS [{lat:.2f}, {lon:.2f}]"
    else:
        # Regional Fallback
        closest, dist_km = find_closest_station(lat, lon)
        d = closest["defaults"]
        temp = d["temperature_c"]
        humidity = d["relative_humidity_pct"]
        pressure = d["surface_pressure_hpa"]
        wind = d["wind_speed_kmh"]
        precip = d["precipitation_mm"]
        precip_24h = d["precipitation_mm"]
        sst = d["sea_surface_temp_c"]
        soil_moisture = d["soil_moisture_pct"]
        soil_temp = d["soil_temperature_c"]
        location_desc = f"{closest['name']} ({dist_km} km away)"
        source_label = "Regional Meteorological Station Reference (Offline Fallback)"

    # Formulate inputs ready for each hazard simulator
    simulator_inputs = {
        "fire": {
            "temperature_c": round(temp, 1),
            "relative_humidity_pct": round(humidity, 1),
            "wind_speed_kmh": round(wind, 1),
            "rainfall_mm": round(precip, 1),
            "vegetation_ndvi": 0.22 if humidity < 35.0 else 0.45
        },
        "flood": {
            "precipitation_24h_mm": round(precip_24h, 1),
            "soil_moisture_pct": round(soil_moisture, 1),
            "radar_backscatter_drop_db": round(min(18.0, max(1.0, (precip_24h / 15.0))), 1),
            "elevation_m": 45.0,
            "river_proximity_km": 2.5
        },
        "cyclone": {
            "central_pressure_hpa": round(pressure, 1),
            "max_sustained_wind_kmh": round(max(wind, 45.0), 1),
            "sea_surface_temp_c": round(sst, 1),
            "storm_forward_speed_kmh": 16.0,
            "coastal_distance_km": 75.0
        },
        "drought": {
            "ndvi_anomaly": -0.28 if (humidity < 30.0 and precip < 5.0) else -0.05,
            "ndwi_moisture": -0.22 if humidity < 35.0 else 0.05,
            "vci_percent": 22.0 if humidity < 35.0 else 65.0,
            "precipitation_deficit_pct": 68.0 if precip < 10.0 else 15.0,
            "soil_temperature_c": round(soil_temp, 1)
        }
    }

    return {
        "status": "success",
        "is_live_api": is_live,
        "source": source_label,
        "coordinates": [round(lat, 4), round(lon, 4)],
        "location_name": location_desc,
        "current_weather": {
            "temperature_c": round(temp, 1),
            "relative_humidity_pct": round(humidity, 1),
            "surface_pressure_hpa": round(pressure, 1),
            "wind_speed_kmh": round(wind, 1),
            "precipitation_mm": round(precip, 1),
            "sea_surface_temp_c": round(sst, 1)
        },
        "simulator_inputs": simulator_inputs,
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    }

