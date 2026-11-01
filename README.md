# Disaster Intelligence
### Satellite-Based Multi-Hazard Monitoring and Incident Prioritization Platform

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Backend-Flask-black.svg)](https://flask.palletsprojects.com/)
[![Database](https://img.shields.io/badge/Database-SQLite3-003B57.svg)](https://www.sqlite.org/)
[![Mapping](https://img.shields.io/badge/Mapping-Leaflet.js%20%7C%20OpenStreetMap-brightgreen.svg)](https://leafletjs.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-97%20Passed-success.svg)]()

---

## 📌 Project Overview

**Disaster Intelligence** is an end-to-end, open-source platform designed to autonomously monitor, cluster, and prioritize multi-hazard disaster events globally using free and publicly accessible Earth Observation satellite datasets and to coordinate on-the-ground emergency relief with helping organizations and smart evacuation planning.

The system ingests real satellite and environmental data across four core peril domains plus operational emergency coordination:
1. **Forest Fires**: Active thermal anomalies and Fire Radiative Power (FRP) via **NASA FIRMS (VIIRS & MODIS)**.
2. **Floods**: Surface water inundation changes via **Copernicus Sentinel-1 (C-Band SAR)** & **NASA GPM (IMERG)**.
3. **Droughts & Vegetation Stress**: Multi-spectral moisture indices (NDVI / NDWI) via **Copernicus Sentinel-2 (MSI)**.
4. **Tropical Cyclones**: Live cyclone tracking, official forecast vectors, uncertainty cones, and risk assessment via **NOAA National Hurricane Center (NHC)** & **IMD RSMC New Delhi**.
5. **Emergency Response & Helping Organization Tracking**: Automated proximity-based helper matching (NDRF, SDRF, Fire, Hospitals, Ambulances, NGOs, Relief & Rescue) with a full 9-stage dispatch response lifecycle, audit logging, and dedicated responder portal.
6. **Smart Evacuation & Safe Route Planner**: Intelligent destination discovery (cyclone shelters, relief camps, emergency hospitals), road-network routing (OSRM & geometric highway engine), and real-time hazard intersection risk assessment (fire buffers, flood washouts, road closures).

Emergency response teams often suffer from *data overload* during crises. This platform solves that bottleneck through **transparent algorithmic priority scoring**, clustering related observations, quantifying spatial uncertainty, and rendering actionable situational awareness onto an interactive dark-navy command dashboard.

---

## 🛡️ Core Architectural Principles

- **100% Free & Open-Source Stack**: No paid APIs, no commercial AI subscriptions, and no expensive proprietary database services.
- **Real Satellite Data Only**: Zero simulated or fake satellite telemetry passed as real data.
- **Local-First on Windows**: Engineered to run smoothly on standard local machines with zero configuration friction.
- **Explainable Prioritization**: Deterministic scoring combining hazard intensity, observation confidence, and exposed area.
- **Auditability**: Complete transparency with SQLite WAL mode tracking every ingested hazard and audit action.

---

## 💻 Technology Stack

### Frontend
- **HTML5 & Semantic Markup**: Clean, accessible component structure.
- **Advanced Custom CSS**: Custom dark navy dashboard theme, glassmorphism, responsive grid & flex layouts, typography powered by *Inter* and *JetBrains Mono*.
- **Vanilla JavaScript**: Lightweight, dependency-free DOM manipulation, real-time telemetry polling, and custom event handlers.
- **Leaflet.js & OpenStreetMap**: High-performance interactive geospatial mapping with custom hazard layer filters.

### Backend
- **Python 3.11+**: Core runtime environment.
- **Flask**: Microframework providing application factory architecture, Blueprints, and RESTful JSON APIs.
- **SQLite 3**: Embedded database with Foreign Key enforcement and Write-Ahead Logging (`WAL`).
- **Data & ML Libraries**: NumPy, Pandas, Scikit-learn (for spatial clustering and prioritization in upcoming modules).

---

## 📂 Project Directory Structure

```text
Disaster Intelligence/
├── app/
│   ├── __init__.py           # Flask Application Factory & blueprint registration
│   ├── config.py             # Configuration classes (Dev, Test, Prod)
│   ├── database.py           # SQLite connection pooling & schema management
│   ├── models/
│   │   ├── __init__.py
│   │   └── schema.py         # DDL definitions (hazards, incidents, sync status, audit logs)
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── main.py           # HTML view endpoints (Dashboard, Incidents, About)
│   │   └── api.py            # RESTful endpoints (/api/health, /api/stats, /api/incidents)
│   ├── services/
│   │   └── __init__.py       # Placeholder for satellite data ingestion pipelines
│   ├── static/
│   │   ├── css/
│   │   │   └── dashboard.css # Dark navy dashboard theme & responsive styling
│   │   └── js/
│   │       └── app.js        # Vanilla JS, Leaflet map controllers, live telemetry
│   └── templates/
│       ├── base.html         # Master layout with sidebar navigation & topbar
│       └── dashboard.html    # Command center dashboard with KPI cards & incident feed
├── data/
│   ├── .gitkeep              # Ensures directory persistence in git
│   └── disaster_intel.db     # Local SQLite database (auto-created on first run)
├── tests/
│   ├── __init__.py
│   ├── test_app.py           # Flask routes, healthcheck, and API tests
│   └── test_database.py      # SQLite schema creation & transaction tests
├── .env.example              # Sample environment configuration template
├── .gitignore                # Git exclusions (virtual env, sqlite databases, cache)
├── requirements.txt          # Python project dependencies
├── run.py                    # Application launch script
└── README.md                 # Project documentation
```

---

## 🚀 Step-by-Step Quickstart Guide (Windows)

### 1. Prerequisites
Ensure you have **Python 3.11** (or later) installed on your Windows machine:
```powershell
python --version
```

### 2. Create and Activate a Virtual Environment
From inside the project root folder:
```powershell
# Create the virtual environment
python -m venv .venv

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1
```
*(If PowerShell displays an ExecutionPolicy warning, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)*

### 3. Install Dependencies
Install the required packages:
```powershell
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the `.env.example` file to create your local `.env`:
```powershell
copy .env.example .env
```
*(Note: No paid API keys are required! All default endpoints operate completely offline or using public open feeds.)*

### 5. Initialize Database (Optional)
The application will automatically initialize the database on startup, but you can also explicitly trigger it via Flask CLI:
```powershell
flask --app run init-db
```

### 6. Start the Application
Run the entry point script:
```powershell
python run.py
```
Open your web browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 🧪 Running Tests

A complete automated test suite is included to guarantee reliability:
```powershell
.\.venv\Scripts\pytest -v
```

Expected result:
```
tests/test_app.py::test_dashboard_home_page PASSED
tests/test_app.py::test_api_health_endpoint PASSED
tests/test_app.py::test_api_sources_endpoint PASSED
tests/test_app.py::test_api_stats_endpoint PASSED
tests/test_app.py::test_api_incidents_endpoint PASSED
tests/test_app.py::test_404_error_handler PASSED
tests/test_database.py::test_database_initialization PASSED
tests/test_database.py::test_hazard_insertion_and_query PASSED

============================== 8 passed ==============================
```

---

## 🗺️ Development Roadmap

- [x] **Phase 1: Project Initialization & Core Framework**
  - Modular Flask architecture & configuration.
  - SQLite database schema & connection lifecycle.
  - Premium dark navy dashboard layout with Leaflet.js mapping.
  - Automated unit and integration test suite.
- [x] **Phase 2: Forest Fire Module (NASA FIRMS & DBSCAN)**
  - Real NASA FIRMS satellite active fire observation ingestion.
  - Geospatial DBSCAN clustering with Haversine distance metric.
  - Transparent 4-factor priority scoring formula (FRP, confidence, density, night persistence).
  - Evidence, footprint area, and spatial uncertainty quantification.
  - Dedicated interactive fire command center with raw pixel and clustered complex views.
- [x] **Phase 3: Flood Module (Copernicus Sentinel-1 SAR & NASA GPM)**
  - Synthetic Aperture Radar (SAR) C-Band backscatter drop ($\Delta\sigma^0$) change detection.
  - All-weather 24/7 cloud penetration for real-time flood monitoring.
  - Correlated NASA GPM IMERG 24h precipitation driving validation.
  - DBSCAN watershed sub-basin clustering (~12 km radius).
  - Transparent 4-factor flood priority scoring ($35\%\text{ SAR} + 30\%\text{ Rain} + 20\%\text{ Extent} + 15\%\text{ Conf}$).
  - Dedicated interactive flood command center with dual-layer radar viewing.
- [x] **Phase 4: Drought Module (Copernicus Sentinel-2 MSI)**
  - Multispectral optical index extraction (NDVI, NDWI, VCI).
  - Red vs Near-Infrared vegetative health and canopy chlorophyll loss analysis.
  - Short-Wave Infrared (SWIR) moisture deficit detection.
  - DBSCAN agricultural corridor clustering (~25 km radius).
  - Transparent 4-factor drought priority scoring ($35\%\text{ NDVI} + 30\%\text{ NDWI} + 20\%\text{ VCI} + 15\%\text{ Extent}$).
  - Dedicated interactive drought command center with multispectral viewing.
- [x] **Phase 5: Tropical Cyclone Monitoring, Tracking & Risk Assessment**
  - Live storm surveillance and official forecast cone visualization (NOAA NHC & IMD RSMC New Delhi).
  - Observed track history with time-indexed eye coordinates and central pressure readings.
  - Landfall sector forecasting, storm surge estimates, and heavy rainfall advisories.
  - Saffir-Simpson Hurricane Wind Scale & IMD Cyclonic Disturbance intensity classification.
  - 5-factor Machine Learning coastal risk assessment model.
- [x] **Phase 6: Emergency Response & Helping Organization Tracking System**
  - Geospatial nearest organization identification across 8 agency categories using spherical Haversine math.
  - 9-stage dispatch lifecycle: Pending → Acknowledged → Dispatched → On The Way → Arrived → Assistance In Progress → Completed (with Rejected/Cancelled handling).
  - Complete immutable audit logging and chronological status transition history.
  - In-app notification service alerting organizations upon dispatch.
  - Interactive Leaflet.js response map with proximity tier vectors (<30km immediate, 30-80km regional, >80km strategic).
  - Dedicated Organization Response Portal with role-based authentication (Bearer token & session) for field responders.
  - Live dashboard with real-time polling (15s auto-refresh) and multi-factor filtering.
  - Telemetry location updates for dispatched emergency response units.
- [x] **Phase 7: Smart Evacuation & Safe Route Planner**
  - Discovery of verified emergency shelters, relief camps, and trauma hospitals sorted by proximity.
  - Dual-mode routing engine: Open Source Routing Machine (OSRM) integration with high-fidelity geometric highway corridor fallback.
  - Multi-hazard route intersection risk assessment scanning fire perimeters, flood washouts, and active road closures.
  - Route risk classification (`SAFE`, `CAUTION`, `HIGH_RISK`, `UNVERIFIED`) with human-readable safety advisories and timestamps.
  - Interactive 3-panel command dashboard with primary and alternative bypass routes.
  - Live shelter capacity & occupancy headroom management with audit trail.
- [ ] **Phase 8: Multi-Hazard Incident Prioritization & Official PDF Reporting**

---

## 🗺️ Smart Evacuation & Safe Route Planner (Phase 4)

### Safe Destination Categories
- **Cyclone Shelters**: Multi-storey reinforced concrete refuges with potable water and emergency power.
- **Relief Camps**: Municipal halls, community staging grounds, and temporary tent hubs.
- **Emergency Hospitals & Apex Trauma Centers**: Level 1 & Level 2 casualty facilities with dedicated triage beds.
- **School Shelters**: Educational campuses equipped with emergency dormitory halls.

### Routing & Safety Evaluation Architecture
1. **Origin & Destination Pairing**: Dispatches routes from selected incident epicenters or custom GPS points to nearby verified shelters or hospitals.
2. **Routing Engine**: Direct OSRM public engine integration with robust geometric highway fallback ensuring zero external dependency outages.
3. **Hazard Intersection Detection**: Cross-references every route waypoint against:
   - NASA FIRMS active thermal fire clusters (buffer: $<2.5\text{ km}$ = High Risk).
   - Copernicus Sentinel-1 SAR flood inundations (buffer: $<2.0\text{ km}$ = High Risk).
   - Confirmed road closure observations and structural washouts.
4. **Alternative Bypass Routing**: Dynamically calculates alternative highway bypass routes avoiding detected danger zones.

### Key Evacuation API Endpoints
- `GET /api/evacuation/stats`: Real-time KPI summary (shelters, capacity, hospitals, beds, road closures).
- `GET /api/evacuation/shelters`: Directory of emergency shelters (filterable by category and status).
- `GET /api/evacuation/shelters/<id>`: Single shelter capacity details.
- `POST /api/evacuation/shelters`: Register a new emergency shelter.
- `PUT /api/evacuation/shelters/<id>`: Update shelter information.
- `POST /api/evacuation/shelters/<id>/occupancy`: Update current occupancy with capacity ceiling validation and audit history.
- `GET /api/evacuation/shelters/<id>/history`: Retrieve occupancy change history for a shelter.
- `GET /api/evacuation/hospitals`: Directory of emergency hospitals, trauma levels, and available beds.
- `GET /api/evacuation/nearby`: Proximity-based discovery of shelters and hospitals (`?incident_id=...` or `?lat=...&lon=...`).
- `POST /api/evacuation/route`: Compute primary and alternative routes with full hazard risk evaluation scorecard.
- `GET /api/evacuation/hazards`: GeoJSON feature collection of active road obstacles and satellite hazard buffers.

---

## 🚑 Emergency Response Module & Demo Accounts

### Helping Organization Categories
- **NDRF** (National Disaster Response Force)
- **SDRF** (State Disaster Response Force)
- **Fire Department**
- **Hospitals**
- **Ambulance Services** (ALS / BLS)
- **NGOs** (Indian Red Cross, etc.)
- **Disaster Relief Organizations** (SEEDS India, etc.)
- **Rescue Teams** (Indian Coast Guard, Maritime SAR)

### Pre-Seeded Responder Demo Accounts
| Organization | Category | Username | Password | Role |
| :--- | :--- | :--- | :--- | :--- |
| **NDRF 6th Battalion Quick Reaction Unit** | NDRF | `ndrf_gujarat` | `password123` | DISPATCHER |
| **NDRF 2nd Battalion Coastal Hub** | NDRF | `ndrf_wb` | `password123` | DISPATCHER |
| **SDRF Gujarat Rapid Deployment Cell** | SDRF | `sdrf_dwarka` | `password123` | RESPONDER |
| **Rajkot Municipal Fire & Emergency Services** | Fire Department | `fire_rajkot` | `password123` | DISPATCHER |
| **GG Govt Hospital Emergency Trauma Center** | Hospitals | `hospital_jamnagar` | `password123` | RESPONDER |
| **GVK EMRI 108 Emergency Ambulance Coastal Fleet** | Ambulance Services | `ambulance_fleet` | `password123` | DISPATCHER |
| **Indian Coast Guard Search & Rescue Station** | Rescue Teams | `coastguard_okha` | `password123` | RESPONDER |
| **Indian Red Cross Society Relief Depot** | NGOs | `redcross_relief` | `password123` | RESPONDER |
| **SEEDS India Community Rapid Shelter Unit** | Relief Organizations | `seeds_relief` | `password123` | RESPONDER |

### Key API Endpoints
- `GET /api/response/categories`: List supported organization categories and response statuses.
- `GET /api/response/organizations`: Organization directory (filterable by category, availability).
- `GET /api/response/nearby`: Haversine-sorted nearest organizations by incident ID or latitude/longitude.
- `POST /api/response/requests`: Dispatch formal emergency request to an organization.
- `GET /api/response/requests`: List emergency requests (filterable by status, disaster type, priority, org).
- `POST /api/response/requests/<id>/action`: Accept or reject a dispatch request (authorized responders).
- `POST /api/response/requests/<id>/status`: Update lifecycle status with optional remarks and ETA.
- `GET /api/response/requests/<id>/history`: Retrieve audit trail of all status transitions.
- `GET /api/response/stats`: Real-time KPI statistics for command center dashboard.
- `POST /api/response/auth/login`: Authenticate responder and obtain session/bearer token.
- `GET /api/response/auth/me`: Current responder profile and organization data.
- `POST /api/response/requests/<id>/location`: Transmit live GPS coordinates for an active team.
- `GET /api/response/requests/<id>/location`: Get latest GPS coordinates for an active dispatch.

---

## 📄 License
This project is open-source under the MIT License.

