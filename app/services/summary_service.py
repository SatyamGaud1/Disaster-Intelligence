"""
Natural Language Incident Summary Generation Service.
Generates deterministic, domain-specific executive emergency briefs,
evidence analyses, and actionable tactical directives without paid AI dependencies.
"""

from typing import Dict, Any


def generate_incident_summary(incident_data: Dict[str, Any], exposure_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Synthesizes multi-hazard satellite observations, exposure metrics, and priority scores
    into a structured emergency operations executive summary.
    """
    hazard_type = incident_data.get("hazard_type", "MULTI_HAZARD").upper()
    priority_level = incident_data.get("priority_level", "MEDIUM")
    priority_score = incident_data.get("priority_score", 50.0)
    title = incident_data.get("title", "Active Incident")
    lat = incident_data.get("centroid_lat", 0.0)
    lon = incident_data.get("centroid_lon", 0.0)
    area = incident_data.get("affected_area_sqkm", 0.0)
    conf = incident_data.get("confidence_score", 0.85) * 100.0

    exp = exposure_data or {}
    pop_est = exp.get("estimated_population", 0)
    facilities = exp.get("critical_facilities", ["Transport arteries in impact zone"])
    exposure_score = exp.get("exposure_score", 45.0)

    # 1. Executive Briefing Paragraph
    if hazard_type == "FIRE":
        brief = (
            f"SATELLITE EMERGENCY ALERT: High-intensity wildfire complex detected at [{lat:.3f}, {lon:.3f}] "
            f"with an active burning footprint of ~{area:.1f} sq km. Satellite thermal radiometry confirms "
            f"aggressive combustion with {conf:.0f}% sensor confidence. The incident has been classified as "
            f"{priority_level} priority ({priority_score:.1f}/100) based on peak radiative output, rapid spatial spread, "
            f"and proximity to approximately {pop_est:,} residents within the regional response buffer."
        )
    elif hazard_type == "FLOOD":
        brief = (
            f"SATELLITE EMERGENCY ALERT: Major surface water inundation complex detected at [{lat:.3f}, {lon:.3f}] "
            f"spanning an estimated ~{area:.1f} sq km across the river basin. Synthetic Aperture Radar (SAR) backscatter "
            f"indicates severe standing water depth corroborated by torrential precipitation telemetry. "
            f"Classified at {priority_level} priority ({priority_score:.1f}/100) threatening approximately "
            f"{pop_est:,} residents and vital transportation corridors."
        )
    elif hazard_type == "DROUGHT":
        brief = (
            f"SATELLITE AGRICULTURAL ALERT: Multi-temporal Sentinel-2 MSI observations identify severe vegetative "
            f"desiccation and root-zone moisture deficit spanning ~{area:.1f} sq km at [{lat:.3f}, {lon:.3f}]. "
            f"Acute chlorophyll degradation and negative canopy water indices establish {priority_level} priority "
            f"({priority_score:.1f}/100) affecting an estimated {pop_est:,} agrarian dependents across the regional agrozone."
        )
    else:
        brief = f"Multi-hazard disaster anomaly registered at [{lat:.3f}, {lon:.3f}]. Priority score: {priority_score:.1f} ({priority_level})."

    # 2. Key Earth Observation Evidence Highlights
    evidence_bullets = [
        f"Geospatial Centroid: [{lat:.4f}, {lon:.4f}] with ~{area:.1f} km² active perimeter",
        f"Algorithm Prioritization Rating: {priority_score:.1f} / 100 ({priority_level} Urgency)",
        f"Sensor Observation Confidence: {conf:.0f}%",
        f"Estimated Impact Buffer Population: {pop_est:,} inhabitants",
        f"Exposed Lifelines: {', '.join(facilities[:3])}"
    ]

    # 3. Actionable Tactical Directives
    directives = []
    if priority_level == "CRITICAL":
        if hazard_type == "FIRE":
            directives = [
                "Issue immediate Level 3 Evacuation Orders for settlements within 10 km downwind perimeter.",
                "Mobilize regional aerial retardant drop tankers and establish secondary firebreaks.",
                "Protect electrical substations and healthcare facilities from ember cast.",
                "Initiate public air quality advisories for downwind particulate matter (PM2.5)."
            ]
        elif hazard_type == "FLOOD":
            directives = [
                "Issue mandatory evacuation warnings for low-lying floodplain communities.",
                "Deploy mobile flood barriers and reinforce municipal drainage culverts.",
                "Pre-stage boat rescue teams and emergency water purification units.",
                "Reroute highway traffic around submerged transportation corridors."
            ]
        else: # DROUGHT
            directives = [
                "Activate regional emergency water rationing and irrigation allocation quotas.",
                "Disburse drought relief livestock fodder and agricultural financial support.",
                "Deploy borehole drilling units to critical water-stressed settlements.",
                "Enact strict reservoir water conservation protocols."
            ]
    elif priority_level == "HIGH":
        directives = [
            "Place regional emergency response personnel and quick-response teams on standby.",
            "Conduct high-frequency 6-hour satellite and drone reconnaissance overflights.",
            "Verify backup generators and emergency supplies at critical facilities within buffer.",
            "Issue precautionary public safety alerts to local municipal authorities."
        ]
    else:
        directives = [
            "Maintain automated orbital satellite monitoring on next scheduled constellation pass.",
            "Log observation telemetry into historical database for trend divergence tracking.",
            "Cross-reference local rain gauges and ground telemetry sensors."
        ]

    return {
        "executive_summary": brief,
        "evidence_highlights": evidence_bullets,
        "tactical_directives": directives,
        "exposure_assessment": {
            "population_exposed": pop_est,
            "facilities_exposed": facilities,
            "exposure_score": exposure_score
        }
    }

