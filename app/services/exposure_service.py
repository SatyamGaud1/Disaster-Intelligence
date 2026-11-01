"""
Exposure and Vulnerability Assessment Service.
Calculates nearby population count, critical infrastructure exposure,
and composite multi-hazard prioritization scores using open spatial heuristics.
"""

import math
from typing import Dict, Any, List

# Regional baseline population densities (persons / sq km) based on open global census data
REGIONAL_DENSITIES = {
    "SOUTH_ASIA": 450.0,
    "EAST_ASIA": 320.0,
    "NORTH_AMERICA": 65.0,
    "EUROPE": 180.0,
    "SOUTH_AMERICA": 40.0,
    "SUB_SAHARAN_AFRICA": 85.0,
    "OCEANIA": 25.0,
    "GLOBAL_DEFAULT": 90.0,
}


def estimate_region_from_coords(lat: float, lon: float) -> str:
    """Classifies geographic coordinates into standard open regional zones."""
    if 5.0 <= lat <= 38.0 and 65.0 <= lon <= 95.0:
        return "SOUTH_ASIA"
    elif 15.0 <= lat <= 55.0 and 95.0 <= lon <= 145.0:
        return "EAST_ASIA"
    elif 25.0 <= lat <= 60.0 and -130.0 <= lon <= -65.0:
        return "NORTH_AMERICA"
    elif 35.0 <= lat <= 70.0 and -10.0 <= lon <= 40.0:
        return "EUROPE"
    elif -55.0 <= lat <= 12.0 and -85.0 <= lon <= -35.0:
        return "SOUTH_AMERICA"
    elif -35.0 <= lat <= 15.0 and -20.0 <= lon <= 55.0:
        return "SUB_SAHARAN_AFRICA"
    elif -45.0 <= lat <= -10.0 and 110.0 <= lon <= 155.0:
        return "OCEANIA"
    return "GLOBAL_DEFAULT"


def calculate_nearby_exposure(lat: float, lon: float, affected_area_sqkm: float, hazard_type: str) -> Dict[str, Any]:
    """
    Computes nearby population exposure, critical infrastructure facilities count,
    and normalized exposure vulnerability index (0 - 100).
    """
    region = estimate_region_from_coords(lat, lon)
    base_density = REGIONAL_DENSITIES.get(region, REGIONAL_DENSITIES["GLOBAL_DEFAULT"])

    # Effective impact buffer radius in km based on affected area
    radius_km = math.sqrt(max(1.0, affected_area_sqkm) / math.pi) + 6.0
    impact_zone_sqkm = math.pi * (radius_km ** 2)

    # Urban / settlement proximity multiplier
    # Near river plains or coastal lines, densities increase
    proximity_factor = 1.0
    if hazard_type == "FLOOD":
        proximity_factor = 1.4  # Floodplains historically have high human habitation
    elif hazard_type == "DROUGHT":
        proximity_factor = 0.9  # Arable agrarian basins
    elif hazard_type == "FIRE":
        proximity_factor = 0.6  # Forest / wildland-urban interface (WUI)

    estimated_population = int(impact_zone_sqkm * base_density * proximity_factor)

    # Estimate critical infrastructure facilities exposed in impact buffer
    # Ratios based on standard OpenStreetMap settlement amenity distribution
    hospitals = max(0, int(estimated_population / 45000))
    schools = max(1, int(estimated_population / 12000))
    power_substations = max(0, int(estimated_population / 60000))
    transport_corridors_km = round(radius_km * 2.4, 1)

    # Normalize Exposure Score (0 - 100)
    # A population of 100,000+ or high infrastructure proximity reaches near 100
    pop_score = min(100.0, (estimated_population / 80000.0) * 100.0)
    infra_score = min(100.0, (hospitals * 20.0 + power_substations * 25.0 + schools * 5.0))
    
    exposure_score = round((pop_score * 0.65) + (infra_score * 0.35), 1)

    critical_facilities = []
    if hospitals > 0:
        critical_facilities.append(f"{hospitals} Regional Hospital(s)")
    if power_substations > 0:
        critical_facilities.append(f"{power_substations} Power Grid Substation(s)")
    if schools > 0:
        critical_facilities.append(f"{schools} Educational/Shelter Center(s)")
    critical_facilities.append(f"{transport_corridors_km} km Primary Transport Arteries")

    return {
        "region_code": region,
        "buffer_radius_km": round(radius_km, 1),
        "estimated_population": estimated_population,
        "exposure_score": exposure_score,
        "critical_facilities_count": hospitals + power_substations + schools,
        "critical_facilities": critical_facilities,
        "transport_corridors_km": transport_corridors_km
    }


def compute_composite_incident_priority(hazard_priority_score: float, exposure_score: float) -> Dict[str, Any]:
    """
    Combines satellite hazard severity with human & infrastructure exposure.
    65% Hazard Severity + 35% Human Exposure.
    """
    composite = (hazard_priority_score * 0.65) + (exposure_score * 0.35)
    composite = round(max(5.0, min(99.9, composite)), 1)

    if composite >= 80.0:
        level = "CRITICAL"
    elif composite >= 60.0:
        level = "HIGH"
    elif composite >= 40.0:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "composite_priority_score": composite,
        "composite_priority_level": level,
        "hazard_weight": 0.65,
        "exposure_weight": 0.35
    }

