"""
Main Blueprint: Serves front-facing HTML dashboard views.
"""

from flask import Blueprint, render_template

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Renders the primary multi-hazard monitoring dashboard."""
    return render_template(
        "dashboard.html",
        page_title="Multi-Hazard Command Center",
        active_nav="dashboard"
    )


@main_bp.route("/fire")
def fire_view():
    """Renders the dedicated Forest Fire & Thermal Anomaly Monitoring Module."""
    return render_template(
        "fire_module.html",
        page_title="Forest Fire & Thermal Anomaly Monitoring (NASA FIRMS)",
        active_nav="fire"
    )


@main_bp.route("/flood")
def flood_view():
    """Renders the dedicated Flood & Inundation Monitoring Module (Sentinel-1 SAR & GPM)."""
    return render_template(
        "flood_module.html",
        page_title="Flood & Inundation Monitoring (Copernicus Sentinel-1 SAR & NASA GPM)",
        active_nav="flood"
    )


@main_bp.route("/drought")
def drought_view():
    """Renders the dedicated Drought & Vegetation Monitoring Module (Sentinel-2 MSI)."""
    return render_template(
        "drought_module.html",
        page_title="Drought & Vegetation Stress Monitoring (Copernicus Sentinel-2 MSI)",
        active_nav="drought"
    )


@main_bp.route("/cyclone")
def cyclone_view():
    """Renders the dedicated Cyclone Tracking & Risk Assessment Module (NOAA NHC & IMD RSMC)."""
    return render_template(
        "cyclone_module.html",
        page_title="Tropical Cyclone Monitoring, Tracking & Risk Assessment",
        active_nav="cyclone"
    )


@main_bp.route("/response")
def response_view():
    """Renders the Emergency Response & Organization Tracking Module."""
    return render_template(
        "response_module.html",
        page_title="Emergency Response & Organization Tracking",
        active_nav="response"
    )


@main_bp.route("/evacuation")
def evacuation_view():
    """Renders Phase 4: Smart Evacuation & Safe Route Planner Module."""
    return render_template(
        "evacuation_module.html",
        page_title="Smart Evacuation & Safe Route Planner",
        active_nav="evacuation"
    )


@main_bp.route("/org-portal")
def org_portal_view():
    """Renders the Organization Response Portal for authorized responders."""
    return render_template(
        "org_portal.html",
        page_title="Organization Response Portal",
        active_nav="response"
    )


@main_bp.route("/presentation")
def presentation_view():
    """Renders the interactive pitch and project presentation slide deck."""
    return render_template(
        "presentation.html",
        page_title="Project Presentation Deck - Disaster Intelligence"
    )


@main_bp.route("/incidents")
def incidents_view():
    """View for detailed incident prioritization & analysis."""
    return render_template(
        "dashboard.html",
        page_title="Incident Prioritization & Prior Records",
        active_nav="incidents"
    )


@main_bp.route("/about")
def about_view():
    """Overview of open data sources, algorithms, and project scope."""
    return render_template(
        "dashboard.html",
        page_title="System Architecture & Open Data Sources",
        active_nav="about"
    )
