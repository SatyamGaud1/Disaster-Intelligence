"""
Unit tests for Cyclone Monitoring and Tracking Service.
Verifies reference data loading, active storm queries, track parsing (observed vs forecast),
cone generation, and official advisories.
"""

import pytest
from app.services.cyclone_service import (
    load_cyclone_reference_data,
    get_available_storms,
    get_active_cyclones,
    get_cyclone_track_data,
    get_official_advisories
)


def test_load_cyclone_reference_data():
    df = load_cyclone_reference_data()
    assert not df.empty
    assert "storm_id" in df.columns
    assert "central_pressure_hpa" in df.columns
    assert "max_sustained_wind_kmh" in df.columns
    assert "track_type" in df.columns


def test_get_available_storms():
    storms = get_available_storms()
    assert len(storms) >= 3
    storm_ids = [s["storm_id"] for s in storms]
    assert "2023-ARB-BIPARJOY" in storm_ids
    assert "2020-NIO-AMPHAN" in storm_ids


def test_get_active_cyclones():
    active = get_active_cyclones()
    assert len(active) >= 1
    first = active[0]
    assert "storm_name" in first
    assert "category_saffir" in first
    assert "category_imd" in first
    assert "movement_direction" in first
    assert "intensification_trend" in first
    assert first["data_source"] == "NOAA NHC / IMD RSMC Official Track Surveillance"


def test_get_cyclone_track_data_observed_and_forecast():
    # Test storm with forecast track (Biparjoy)
    track_data = get_cyclone_track_data("2023-ARB-BIPARJOY")
    assert track_data["storm_name"] == "Biparjoy"
    assert len(track_data["observed_track"]) > 0
    assert len(track_data["forecast_track"]) > 0
    assert track_data["has_forecast"] is True
    assert len(track_data["uncertainty_cone"]) >= 3

    # Check observed tracks have valid coordinates
    for pt in track_data["observed_track"]:
        assert -90 <= pt["latitude"] <= 90
        assert -180 <= pt["longitude"] <= 180
        assert pt["wind_kmh"] > 0

    # Check forecast tracks have forecast hour > 0
    for fc in track_data["forecast_track"]:
        assert fc["forecast_hour"] > 0


def test_get_official_advisories():
    advisories = get_official_advisories()
    assert len(advisories) >= 3
    for adv in advisories:
        assert adv["warning_level_code"] in ["RED", "ORANGE", "YELLOW", "WATCH"]
        assert adv["advisory_url"].startswith("http")
        assert len(adv["headline"]) > 0

