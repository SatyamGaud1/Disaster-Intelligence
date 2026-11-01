"""
Database schema definitions for the Disaster Intelligence Platform.
All tables are created using SQLite 3 standard syntax.
"""

SCHEMA_SQL = """
-- Hazards Table: Stores raw, processed observations from satellite sources
CREATE TABLE IF NOT EXISTS hazards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,                     -- e.g., 'NASA_FIRMS', 'SENTINEL_1', 'SENTINEL_2', 'NASA_GPM', 'NOAA_IBTRACS', 'IMD_RSMC'
    hazard_type TEXT NOT NULL,                -- 'FIRE', 'FLOOD', 'DROUGHT', 'CYCLONE', 'CYCLONE'
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    intensity_value REAL,                     -- FRP (Fire Radiative Power), Flood Inundation Index, or NDVI anomaly
    confidence REAL,                          -- Detection confidence (0.0 to 1.0 or 0 to 100%)
    observation_timestamp TEXT NOT NULL,      -- UTC ISO-8601 string
    metadata_json TEXT,                       -- Raw metadata for transparency and evidence tracking
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Incidents Table: Prioritized incident clusters derived from hazard observations
CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_uid TEXT UNIQUE NOT NULL,        -- Human-readable unique code (e.g., 'INC-2026-FIRE-001')
    title TEXT NOT NULL,
    hazard_type TEXT NOT NULL,                -- 'FIRE', 'FLOOD', 'DROUGHT', 'CYCLONE'
    status TEXT DEFAULT 'ACTIVE',             -- 'ACTIVE', 'MONITORING', 'RESOLVED'
    priority_level TEXT NOT NULL,             -- 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
    priority_score REAL NOT NULL,             -- Transparent 0 - 100 score
    confidence_score REAL NOT NULL,           -- Confidence metric 0.0 - 1.0
    centroid_lat REAL NOT NULL,
    centroid_lon REAL NOT NULL,
    affected_area_sqkm REAL DEFAULT 0.0,
    summary TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- System Metrics / Data Source Sync Log: Tracks public satellite feed status
CREATE TABLE IF NOT EXISTS source_sync_status (
    source_name TEXT PRIMARY KEY,             -- e.g., 'NASA_FIRMS', 'SENTINEL_1', 'SENTINEL_2', 'NASA_GPM'
    last_sync_timestamp TEXT,
    status TEXT DEFAULT 'READY',              -- 'READY', 'SYNCING', 'ERROR'
    records_count INTEGER DEFAULT 0,
    message TEXT
);

-- Audit / Action Logs: Ensures complete transparency for emergency management operations
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    details TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Helping Organizations Directory (Verified & Regional Entities)
CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_uid TEXT UNIQUE NOT NULL,             -- e.g., 'ORG-NDRF-001'
    name TEXT NOT NULL,
    category TEXT NOT NULL,                   -- 'NDRF', 'SDRF', 'Fire Department', 'Hospitals', 'Ambulance Services', 'NGOs', 'Disaster Relief Organizations', 'Rescue Teams'
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    address TEXT,
    city TEXT,
    state TEXT,
    contact_person TEXT,
    phone TEXT NOT NULL,
    emergency_hotline TEXT,
    email TEXT NOT NULL,
    capacity_description TEXT,
    availability_status TEXT DEFAULT 'AVAILABLE', -- 'AVAILABLE', 'BUSY', 'OFFLINE'
    is_verified INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Organization Responder Users (Role-based access for response teams)
CREATE TABLE IF NOT EXISTS organization_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id INTEGER NOT NULL,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT DEFAULT 'RESPONDER',            -- 'ADMIN', 'DISPATCHER', 'RESPONDER'
    auth_token TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(org_id) REFERENCES organizations(id) ON DELETE CASCADE
);

-- Emergency Response Requests (Disaster incident dispatch requests)
CREATE TABLE IF NOT EXISTS emergency_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_uid TEXT UNIQUE NOT NULL,         -- e.g., 'REQ-2026-FIRE-001-NDRF01'
    incident_id INTEGER NOT NULL,
    org_id INTEGER NOT NULL,
    current_status TEXT DEFAULT 'Pending',    -- 'Pending', 'Acknowledged', 'Dispatched', 'On The Way', 'Arrived', 'Assistance In Progress', 'Completed', 'Rejected', 'Cancelled'
    priority_level TEXT NOT NULL,             -- 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
    distance_km REAL NOT NULL,
    estimated_arrival_minutes INTEGER,
    estimated_affected_area_sqkm REAL DEFAULT 0.0,
    requester_name TEXT DEFAULT 'Emergency Operations Center',
    requester_contact TEXT,
    remarks TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(incident_id) REFERENCES incidents(id) ON DELETE CASCADE,
    FOREIGN KEY(org_id) REFERENCES organizations(id) ON DELETE CASCADE
);

-- Response Status Audit History (Timestamped lifecycle transitions)
CREATE TABLE IF NOT EXISTS response_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    previous_status TEXT,
    new_status TEXT NOT NULL,
    updated_by_user_id INTEGER,
    updated_by_name TEXT NOT NULL,
    remarks TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(request_id) REFERENCES emergency_requests(id) ON DELETE CASCADE,
    FOREIGN KEY(updated_by_user_id) REFERENCES organization_users(id) ON DELETE SET NULL
);

-- Organization In-App Notifications (Dispatch alerts & updates)
CREATE TABLE IF NOT EXISTS organization_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id INTEGER NOT NULL,
    request_id INTEGER,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    notification_type TEXT DEFAULT 'EMERGENCY_DISPATCH',
    is_read INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(org_id) REFERENCES organizations(id) ON DELETE CASCADE,
    FOREIGN KEY(request_id) REFERENCES emergency_requests(id) ON DELETE CASCADE
);

-- Response Team Live Location Updates (Optional live telemetry)
CREATE TABLE IF NOT EXISTS response_location_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    speed_kmh REAL DEFAULT 0.0,
    heading REAL,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(request_id) REFERENCES emergency_requests(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_org_category ON organizations(category);
CREATE INDEX IF NOT EXISTS idx_req_incident ON emergency_requests(incident_id);
CREATE INDEX IF NOT EXISTS idx_req_org ON emergency_requests(org_id);
CREATE INDEX IF NOT EXISTS idx_req_status ON emergency_requests(current_status);
CREATE INDEX IF NOT EXISTS idx_hist_request ON response_status_history(request_id);

-- ==============================================================================
-- PHASE 4: SMART EVACUATION & SAFE ROUTE PLANNER TABLES
-- ==============================================================================

-- Shelters Table: Verified emergency shelters, cyclone shelters, relief centers
CREATE TABLE IF NOT EXISTS shelters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shelter_uid TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT DEFAULT 'CYCLONE_SHELTER',   -- 'CYCLONE_SHELTER', 'RELIEF_CAMP', 'COMMUNITY_CENTER', 'SCHOOL_SHELTER'
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    address TEXT,
    city TEXT,
    state TEXT,
    contact_phone TEXT,
    capacity INTEGER NOT NULL DEFAULT 500,
    current_occupancy INTEGER NOT NULL DEFAULT 0,
    facilities TEXT,                           -- 'Water, Medical, Generator, Sanitation, Kitchen'
    accessibility_info TEXT,                   -- 'Wheelchair Ramp, Heavy Vehicle Access'
    operating_status TEXT DEFAULT 'OPEN',      -- 'OPEN', 'FULL', 'RESERVED', 'INACTIVE'
    is_verified INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    CHECK (current_occupancy >= 0 AND current_occupancy <= capacity)
);

-- Emergency Facilities Table: Hospitals, Trauma Centers, Relief Staging, Police Posts
CREATE TABLE IF NOT EXISTS emergency_facilities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    facility_uid TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    facility_type TEXT NOT NULL,               -- 'HOSPITAL', 'TRAUMA_CENTER', 'RELIEF_CAMP', 'POLICE_POST', 'FIRE_STATION'
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    address TEXT,
    city TEXT,
    state TEXT,
    phone TEXT,
    emergency_hotline TEXT,
    bed_capacity INTEGER DEFAULT 100,
    available_beds INTEGER DEFAULT 50,
    trauma_care_level TEXT DEFAULT 'LEVEL_1',  -- 'LEVEL_1', 'LEVEL_2', 'BASIC', 'MOBILE'
    operating_status TEXT DEFAULT 'OPERATIONAL',-- 'OPERATIONAL', 'OVERLOADED', 'CLOSED'
    is_verified INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Shelter Capacity History: Real-time occupancy audit log
CREATE TABLE IF NOT EXISTS shelter_capacity_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shelter_id INTEGER NOT NULL,
    previous_occupancy INTEGER NOT NULL,
    new_occupancy INTEGER NOT NULL,
    updated_by TEXT DEFAULT 'Shelter Officer',
    remarks TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(shelter_id) REFERENCES shelters(id) ON DELETE CASCADE
);

-- Evacuation Routes: Calculated routes and path geometries
CREATE TABLE IF NOT EXISTS evacuation_routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_uid TEXT UNIQUE NOT NULL,
    incident_id INTEGER,
    origin_lat REAL NOT NULL,
    origin_lon REAL NOT NULL,
    dest_type TEXT NOT NULL,                   -- 'SHELTER', 'HOSPITAL', 'FACILITY'
    dest_id INTEGER,
    dest_name TEXT,
    dest_lat REAL NOT NULL,
    dest_lon REAL NOT NULL,
    route_type TEXT DEFAULT 'PRIMARY',         -- 'PRIMARY', 'ALTERNATIVE'
    distance_km REAL NOT NULL,
    duration_minutes REAL NOT NULL,
    risk_level TEXT DEFAULT 'SAFE',            -- 'SAFE', 'CAUTION', 'HIGH_RISK', 'UNVERIFIED'
    risk_score REAL DEFAULT 0.0,
    hazard_intersections INTEGER DEFAULT 0,
    route_geojson TEXT NOT NULL,
    verification_status TEXT DEFAULT 'VERIFIED',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(incident_id) REFERENCES incidents(id) ON DELETE SET NULL
);

-- Route Risk Assessments: Quantitative multi-hazard risk evaluation for routes
CREATE TABLE IF NOT EXISTS route_risk_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id INTEGER,
    incident_id INTEGER,
    risk_level TEXT NOT NULL,                  -- 'SAFE', 'CAUTION', 'HIGH_RISK', 'UNVERIFIED'
    risk_score REAL NOT NULL,                  -- 0 to 100
    flood_exposure_km REAL DEFAULT 0.0,
    fire_proximity_km REAL DEFAULT 999.0,
    active_road_closures INTEGER DEFAULT 0,
    hazard_summary TEXT,
    warnings_json TEXT,
    confidence_score REAL DEFAULT 0.85,
    evaluated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(route_id) REFERENCES evacuation_routes(id) ON DELETE CASCADE,
    FOREIGN KEY(incident_id) REFERENCES incidents(id) ON DELETE SET NULL
);

-- Road Hazard Observations: Road closures, washouts, debris, and active obstructions
CREATE TABLE IF NOT EXISTS road_hazard_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hazard_type TEXT NOT NULL,                 -- 'FLOOD_WATER', 'FIRE_PERIMETER', 'ROAD_BLOCK', 'BRIDGE_DAMAGE', 'FALLEN_DEBRIS'
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    radius_km REAL DEFAULT 1.0,
    severity TEXT DEFAULT 'HIGH',              -- 'CRITICAL', 'HIGH', 'MODERATE'
    status TEXT DEFAULT 'ACTIVE',              -- 'ACTIVE', 'CLEARED', 'MONITORING'
    description TEXT,
    source TEXT DEFAULT 'SATELLITE_CORROBORATION',
    reported_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_shelter_city ON shelters(city);
CREATE INDEX IF NOT EXISTS idx_facility_type ON emergency_facilities(facility_type);
CREATE INDEX IF NOT EXISTS idx_evac_incident ON evacuation_routes(incident_id);
CREATE INDEX IF NOT EXISTS idx_road_hazard_coords ON road_hazard_observations(latitude, longitude);
"""

