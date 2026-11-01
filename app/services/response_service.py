"""
Emergency Response & Helping Organization Tracking Service.
Handles organization directories, geospatial distance sorting, emergency request dispatching,
multi-stage response lifecycle tracking, in-app notifications, and responder authorization.
"""

import math
import secrets
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple

from werkzeug.security import generate_password_hash, check_password_hash
from app.database import get_db

EARTH_RADIUS_KM = 6371.0088

# Permitted response lifecycle statuses
RESPONSE_STATUSES = [
    "Pending",
    "Acknowledged",
    "Dispatched",
    "On The Way",
    "Arrived",
    "Assistance In Progress",
    "Completed",
    "Rejected",
    "Cancelled"
]

# Supported helping organization categories
ORGANIZATION_CATEGORIES = [
    "NDRF",
    "SDRF",
    "Fire Department",
    "Hospitals",
    "Ambulance Services",
    "NGOs",
    "Disaster Relief Organizations",
    "Rescue Teams"
]


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes Great-Circle spherical distance in kilometers between two GPS coordinates."""
    r_lat1 = math.radians(lat1)
    r_lat2 = math.radians(lat2)
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat / 2.0)**2 + math.cos(r_lat1) * math.cos(r_lat2) * math.sin(d_lon / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(EARTH_RADIUS_KM * c, 2)


# ==============================================================================
# SEEDING VERIFIED ORGANIZATIONS & DEMO RESPONDER ACCOUNTS
# ==============================================================================

DEFAULT_ORGANIZATIONS = [
    {
        "org_uid": "ORG-NDRF-006",
        "name": "NDRF 6th Battalion Rapid Action Force",
        "category": "NDRF",
        "latitude": 22.3072,
        "longitude": 73.1812,
        "address": "Jarod Camp, Vadodara Highway",
        "city": "Vadodara",
        "state": "Gujarat",
        "contact_person": "Commandant R. K. Verma",
        "phone": "+91-265-2830100",
        "emergency_hotline": "1078",
        "email": "controlroom.ndrf06@nic.in",
        "capacity_description": "45 Flood & Cyclone Rescuers, 8 Inflatable Motor Boats, Advanced Deep-Diver Gear, Drone Surveillance",
        "availability_status": "AVAILABLE",
        "user": {
            "username": "ndrf_gujarat",
            "password": "password123",
            "full_name": "Inspector Manoj Singh",
            "role": "DISPATCHER"
        }
    },
    {
        "org_uid": "ORG-NDRF-002",
        "name": "NDRF 2nd Battalion Coastal Command",
        "category": "NDRF",
        "latitude": 22.9868,
        "longitude": 88.4697,
        "address": "Haringhata Base Camp",
        "city": "Kolkata",
        "state": "West Bengal",
        "contact_person": "Commandant Alok Kumar",
        "phone": "+91-33-25870022",
        "emergency_hotline": "1078",
        "email": "bn02-ndrf@gov.in",
        "capacity_description": "60 Storm & Surge Specialists, 12 High-Power Outboard Motor Boats, Satellite Comm Trailer",
        "availability_status": "AVAILABLE",
        "user": {
            "username": "ndrf_wb",
            "password": "password123",
            "full_name": "Sub-Inspector Debashis Roy",
            "role": "DISPATCHER"
        }
    },
    {
        "org_uid": "ORG-SDRF-001",
        "name": "Gujarat SDRF Marine & Flood Rescue Cell",
        "category": "SDRF",
        "latitude": 22.2442,
        "longitude": 68.9685,
        "address": "Coastal Police Station Complex",
        "city": "Dwarka",
        "state": "Gujarat",
        "contact_person": "Deputy SP J. B. Jadeja",
        "phone": "+91-2892-234200",
        "emergency_hotline": "1077",
        "email": "sdrf.saurashtra@gujarat.gov.in",
        "capacity_description": "30 Amphibious Rescue Troops, 4 Zodiac Boats, Emergency Chainsaws, Submersible Water Pumps",
        "availability_status": "AVAILABLE",
        "user": {
            "username": "sdrf_dwarka",
            "password": "password123",
            "full_name": "Team Lead Jayesh Patel",
            "role": "RESPONDER"
        }
    },
    {
        "org_uid": "ORG-FIRE-001",
        "name": "Rajkot Regional Fire & Emergency Headquarters",
        "category": "Fire Department",
        "latitude": 22.3039,
        "longitude": 70.8022,
        "address": "Dhebar Road Central Fire Station",
        "city": "Rajkot",
        "state": "Gujarat",
        "contact_person": "Chief Fire Officer I. V. Khambhalia",
        "phone": "+91-281-2224444",
        "emergency_hotline": "101",
        "email": "fire.rajkot@rmc.gov.in",
        "capacity_description": "14 Foam Tenders, 2 Hydraulic Turntable Ladders (54m), 80 Wildfire Hazmat Responders",
        "availability_status": "AVAILABLE",
        "user": {
            "username": "fire_rajkot",
            "password": "password123",
            "full_name": "Station Officer Vikram Gohil",
            "role": "DISPATCHER"
        }
    },
    {
        "org_uid": "ORG-HOSP-001",
        "name": "Civil Hospital & Level-1 Trauma Critical Care",
        "category": "Hospitals",
        "latitude": 22.4707,
        "longitude": 70.0577,
        "address": "Indira Marg Medical Enclave",
        "city": "Jamnagar",
        "state": "Gujarat",
        "contact_person": "Dr. Pratik Solanki (Medical Supt.)",
        "phone": "+91-288-2550201",
        "emergency_hotline": "102",
        "email": "trauma.civiljamnagar@gujhealth.gov.in",
        "capacity_description": "250 Emergency Surge Beds, 40 ICU Ventilators, 2 Dedicated Burn Wards, Blood Bank On-Site",
        "availability_status": "AVAILABLE",
        "user": {
            "username": "hospital_jamnagar",
            "password": "password123",
            "full_name": "Dr. Neha Shah",
            "role": "RESPONDER"
        }
    },
    {
        "org_uid": "ORG-AMB-001",
        "name": "GVK EMRI 108 Emergency Ambulance Coastal Fleet",
        "category": "Ambulance Services",
        "latitude": 22.2587,
        "longitude": 71.1924,
        "address": "State Emergency Transport Depot",
        "city": "Surendranagar",
        "state": "Gujarat",
        "contact_person": "Fleet Operations Manager K. Mehta",
        "phone": "+91-79-23969108",
        "emergency_hotline": "108",
        "email": "dispatch@emri108.org",
        "capacity_description": "24 Advanced Life Support (ALS) Ambulances, 4 Neonatal Units, Oxygen Generators",
        "availability_status": "AVAILABLE",
        "user": {
            "username": "ambulance_fleet",
            "password": "password123",
            "full_name": "Dispatch Controller Aarti Sharma",
            "role": "DISPATCHER"
        }
    },
    {
        "org_uid": "ORG-RESC-001",
        "name": "Indian Coast Guard Coastal Search & Rescue Station",
        "category": "Rescue Teams",
        "latitude": 22.4633,
        "longitude": 69.0722,
        "address": "Port Road Naval Enclave",
        "city": "Okha",
        "state": "Gujarat",
        "contact_person": "Commanding Officer N. Joshi",
        "phone": "+91-2892-262100",
        "emergency_hotline": "1554",
        "email": "icgs.okha@indiancoastguard.gov.in",
        "capacity_description": "2 Fast Patrol Interceptor Boats, 1 Air-Cushion Hovercraft, Maritime Helo Winch Team",
        "availability_status": "AVAILABLE",
        "user": {
            "username": "coastguard_okha",
            "password": "password123",
            "full_name": "Lt. Cdr. S. Nambiar",
            "role": "RESPONDER"
        }
    },
    {
        "org_uid": "ORG-NGO-001",
        "name": "Indian Red Cross Society Disaster Relief Depot",
        "category": "NGOs",
        "latitude": 21.7645,
        "longitude": 72.1519,
        "address": "Red Cross Bhavan, Crescent Circle",
        "city": "Bhavnagar",
        "state": "Gujarat",
        "contact_person": "Relief Coordinator Sunita Parekh",
        "phone": "+91-278-2428800",
        "emergency_hotline": "+91-9825000108",
        "email": "disaster.redcross@ircs.org",
        "capacity_description": "10,000 Emergency Food Ration Kits, 2 Mobile Water Purification Trucks (20,000 L/day), 500 Tarpaulins",
        "availability_status": "AVAILABLE",
        "user": {
            "username": "redcross_relief",
            "password": "password123",
            "full_name": "Field Officer Ananya Desai",
            "role": "RESPONDER"
        }
    },
    {
        "org_uid": "ORG-RELIEF-001",
        "name": "SEEDS India Community Rapid Shelter Unit",
        "category": "Disaster Relief Organizations",
        "latitude": 20.2961,
        "longitude": 85.8245,
        "address": "Baramunda Emergency Hub",
        "city": "Bhubaneswar",
        "state": "Odisha",
        "contact_person": "Programme Director T. Mohanty",
        "phone": "+91-674-2350811",
        "emergency_hotline": "+91-9437000222",
        "email": "response@seedsindia.org",
        "capacity_description": "Prefab Emergency Shelter Staging (1,200 Families), Solar Powered Charging Hubs, Hygiene Packs",
        "availability_status": "AVAILABLE",
        "user": {
            "username": "seeds_relief",
            "password": "password123",
            "full_name": "Field Manager Tapas Das",
            "role": "RESPONDER"
        }
    }
]


def seed_default_organizations() -> None:
    """
    Seeds verified regional helping organizations and responder accounts into SQLite if not present.
    """
    db = get_db()
    cursor = db.cursor()

    for org in DEFAULT_ORGANIZATIONS:
        cursor.execute("SELECT id FROM organizations WHERE org_uid = ?", (org["org_uid"],))
        existing = cursor.fetchone()

        if not existing:
            cursor.execute(
                """
                INSERT INTO organizations (
                    org_uid, name, category, latitude, longitude,
                    address, city, state, contact_person, phone,
                    emergency_hotline, email, capacity_description,
                    availability_status, is_verified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    org["org_uid"], org["name"], org["category"], org["latitude"], org["longitude"],
                    org["address"], org["city"], org["state"], org["contact_person"], org["phone"],
                    org["emergency_hotline"], org["email"], org["capacity_description"],
                    org["availability_status"], 1
                )
            )
            org_id = cursor.lastrowid

            # Create default responder user account
            user = org["user"]
            pw_hash = generate_password_hash(user["password"])
            token = secrets.token_hex(20)
            cursor.execute(
                """
                INSERT INTO organization_users (
                    org_id, username, password_hash, full_name, role, auth_token, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, 1)
                """,
                (org_id, user["username"], pw_hash, user["full_name"], user["role"], token)
            )

    db.commit()


# ==============================================================================
# QUERIES: DIRECTORY & NEARBY MATCHING
# ==============================================================================

def get_organizations(category: Optional[str] = None, availability: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns list of helping organizations with optional category or availability filters."""
    db = get_db()
    query = "SELECT * FROM organizations WHERE 1=1"
    params = []

    if category and category.upper() != "ALL":
        query += " AND category = ?"
        params.append(category)

    if availability and availability.upper() != "ALL":
        query += " AND availability_status = ?"
        params.append(availability.upper())

    query += " ORDER BY name ASC"
    cursor = db.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def get_organization_by_id(org_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves an organization by its primary key ID."""
    db = get_db()
    cursor = db.execute("SELECT * FROM organizations WHERE id = ?", (org_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def find_nearby_organizations(
    lat: float,
    lon: float,
    max_distance_km: Optional[float] = None,
    category: Optional[str] = None,
    limit: int = 15
) -> List[Dict[str, Any]]:
    """
    Computes exact spherical Haversine distance from disaster GPS coordinates
    to all registered organizations, returns them sorted from nearest to farthest.
    """
    orgs = get_organizations(category=category)
    results = []

    for org in orgs:
        dist = haversine_distance(lat, lon, org["latitude"], org["longitude"])
        if max_distance_km is not None and dist > max_distance_km:
            continue

        # Proximity tier classification
        if dist <= 30.0:
            tier = "IMMEDIATE_RESPONSE"
            tier_label = "Immediate Vicinity (< 30 km)"
        elif dist <= 80.0:
            tier = "REGIONAL_SUPPORT"
            tier_label = "Regional Perimeter (30 - 80 km)"
        else:
            tier = "STRATEGIC_RESERVE"
            tier_label = "Strategic Reinforcement (> 80 km)"

        org_copy = dict(org)
        org_copy["distance_km"] = dist
        org_copy["proximity_tier"] = tier
        org_copy["proximity_label"] = tier_label
        results.append(org_copy)

    results.sort(key=lambda x: x["distance_km"])
    return results[:limit]


# ==============================================================================
# EMERGENCY DISPATCH REQUESTS & STATUS LIFECYCLE
# ==============================================================================

def create_emergency_request(
    incident_id: int,
    org_id: int,
    requester_name: str = "Emergency Operations Center",
    requester_contact: Optional[str] = None,
    priority_level: Optional[str] = None,
    remarks: Optional[str] = None
) -> Dict[str, Any]:
    """
    Dispatches a formal emergency response request from an incident to an organization.
    Initializes status to 'Pending' and writes audit log.
    """
    db = get_db()

    # 1. Verify incident exists
    inc_row = db.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
    if not inc_row:
        raise ValueError(f"Incident with ID {incident_id} not found.")
    inc = dict(inc_row)

    # 2. Verify organization exists
    org = get_organization_by_id(org_id)
    if not org:
        raise ValueError(f"Organization with ID {org_id} not found.")

    # 3. Check if an active request already exists for this pair
    existing = db.execute(
        """
        SELECT id, request_uid, current_status FROM emergency_requests
        WHERE incident_id = ? AND org_id = ? AND current_status NOT IN ('Completed', 'Rejected', 'Cancelled')
        """,
        (incident_id, org_id)
    ).fetchone()

    if existing:
        return {
            "status": "warning",
            "message": f"Active request already in progress ({existing['request_uid']}, status: {existing['current_status']}).",
            "request_id": existing["id"],
            "request_uid": existing["request_uid"]
        }

    # 4. Compute distance
    dist = haversine_distance(inc["centroid_lat"], inc["centroid_lon"], org["latitude"], org["longitude"])
    p_level = priority_level or inc["priority_level"]
    req_uid = f"REQ-2026-{inc['hazard_type']}-{inc['id']:03d}-{org['org_uid'].replace('ORG-', '')}"

    cursor = db.cursor()
    cursor.execute(
        """
        INSERT INTO emergency_requests (
            request_uid, incident_id, org_id, current_status, priority_level,
            distance_km, estimated_affected_area_sqkm, requester_name,
            requester_contact, remarks
        ) VALUES (?, ?, ?, 'Pending', ?, ?, ?, ?, ?, ?)
        """,
        (
            req_uid, incident_id, org_id, p_level, dist,
            inc.get("affected_area_sqkm", 0.0), requester_name,
            requester_contact or "EOC Hotline 112", remarks or f"Emergency dispatch for {inc['title']}"
        )
    )
    request_id = cursor.lastrowid

    # 5. Insert initial status history audit record
    cursor.execute(
        """
        INSERT INTO response_status_history (
            request_id, previous_status, new_status, updated_by_name, remarks
        ) VALUES (?, NULL, 'Pending', ?, ?)
        """,
        (request_id, requester_name, f"Emergency request issued to {org['name']}")
    )

    # 6. Insert in-app notification for the organization
    cursor.execute(
        """
        INSERT INTO organization_notifications (
            org_id, request_id, title, message, notification_type
        ) VALUES (?, ?, ?, ?, 'EMERGENCY_DISPATCH')
        """,
        (
            org_id, request_id,
            f"URGENT: Dispatch Request for {inc['hazard_type']} Incident",
            f"{inc['title']} (Priority: {p_level}, ~{dist} km away). Immediate acknowledgment requested."
        )
    )

    db.commit()
    return {
        "status": "success",
        "request_id": request_id,
        "request_uid": req_uid,
        "current_status": "Pending",
        "distance_km": dist,
        "message": f"Emergency request successfully dispatched to {org['name']}."
    }


def update_request_status(
    request_id: int,
    new_status: str,
    updated_by_user_id: Optional[int] = None,
    updated_by_name: str = "Authorized Responder",
    remarks: Optional[str] = None,
    eta_minutes: Optional[int] = None,
    verify_org_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Transitions an emergency request to a new status.
    Enforces authorization check (if verify_org_id is passed, request must belong to that org).
    """
    if new_status not in RESPONSE_STATUSES:
        raise ValueError(f"Invalid status '{new_status}'. Permitted: {RESPONSE_STATUSES}")

    db = get_db()
    req_row = db.execute("SELECT * FROM emergency_requests WHERE id = ?", (request_id,)).fetchone()
    if not req_row:
        raise ValueError(f"Emergency request ID {request_id} does not exist.")
    req = dict(req_row)

    # Authorization check
    if verify_org_id is not None and req["org_id"] != verify_org_id:
        raise PermissionError(f"Unauthorized: You can only update requests assigned to your organization (ID {verify_org_id}).")

    prev_status = req["current_status"]
    if prev_status == new_status:
        return {
            "status": "unchanged",
            "message": f"Request {req['request_uid']} is already at status '{new_status}'."
        }

    # Disallow transitioning out of terminal states
    if prev_status in ["Completed", "Rejected", "Cancelled"]:
        raise ValueError(f"Cannot update request in terminal state '{prev_status}'.")

    cursor = db.cursor()
    update_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if eta_minutes is not None:
        cursor.execute(
            """
            UPDATE emergency_requests
            SET current_status = ?, estimated_arrival_minutes = ?, remarks = coalesce(?, remarks), updated_at = ?
            WHERE id = ?
            """,
            (new_status, eta_minutes, remarks, update_time, request_id)
        )
    else:
        cursor.execute(
            """
            UPDATE emergency_requests
            SET current_status = ?, remarks = coalesce(?, remarks), updated_at = ?
            WHERE id = ?
            """,
            (new_status, remarks, update_time, request_id)
        )

    # Write status audit trail record
    cursor.execute(
        """
        INSERT INTO response_status_history (
            request_id, previous_status, new_status, updated_by_user_id, updated_by_name, remarks
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            request_id, prev_status, new_status,
            updated_by_user_id, updated_by_name,
            remarks or f"Status changed from {prev_status} to {new_status}"
        )
    )

    # If arriving or dispatched, notify requester
    cursor.execute(
        """
        INSERT INTO organization_notifications (
            org_id, request_id, title, message, notification_type
        ) VALUES (?, ?, ?, ?, 'STATUS_UPDATE')
        """,
        (
            req["org_id"], request_id,
            f"Status Update: {new_status}",
            f"Request {req['request_uid']} updated to '{new_status}' by {updated_by_name}. Remarks: {remarks or 'None'}"
        )
    )

    db.commit()
    return {
        "status": "success",
        "request_id": request_id,
        "request_uid": req["request_uid"],
        "previous_status": prev_status,
        "new_status": new_status,
        "updated_at": update_time,
        "message": f"Response status updated to '{new_status}'."
    }


def get_emergency_requests(
    incident_id: Optional[int] = None,
    org_id: Optional[int] = None,
    status: Optional[str] = None,
    disaster_type: Optional[str] = None,
    priority: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieves emergency response requests joined with incident and organization details.
    """
    db = get_db()
    query = """
        SELECT
            er.id, er.request_uid, er.incident_id, er.org_id,
            er.current_status, er.priority_level, er.distance_km,
            er.estimated_arrival_minutes, er.estimated_affected_area_sqkm,
            er.requester_name, er.requester_contact, er.remarks,
            er.created_at, er.updated_at,
            i.incident_uid, i.title as incident_title, i.hazard_type,
            i.centroid_lat as incident_lat, i.centroid_lon as incident_lon,
            i.priority_score,
            o.name as org_name, o.category as org_category, o.phone as org_phone,
            o.emergency_hotline as org_hotline, o.email as org_email,
            o.latitude as org_lat, o.longitude as org_lon
        FROM emergency_requests er
        JOIN incidents i ON er.incident_id = i.id
        JOIN organizations o ON er.org_id = o.id
        WHERE 1=1
    """
    params = []

    if incident_id:
        query += " AND er.incident_id = ?"
        params.append(incident_id)

    if org_id:
        query += " AND er.org_id = ?"
        params.append(org_id)

    if status and status.upper() != "ALL":
        query += " AND er.current_status = ?"
        params.append(status)

    if disaster_type and disaster_type.upper() != "ALL":
        query += " AND i.hazard_type = ?"
        params.append(disaster_type.upper())

    if priority and priority.upper() != "ALL":
        query += " AND er.priority_level = ?"
        params.append(priority.upper())

    query += " ORDER BY er.created_at DESC"
    cursor = db.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def get_request_history(request_id: int) -> List[Dict[str, Any]]:
    """Retrieves complete chronological audit history for an emergency request."""
    db = get_db()
    cursor = db.execute(
        """
        SELECT h.*, u.username as responder_username, u.role as responder_role
        FROM response_status_history h
        LEFT JOIN organization_users u ON h.updated_by_user_id = u.id
        WHERE h.request_id = ?
        ORDER BY h.timestamp ASC
        """,
        (request_id,)
    )
    return [dict(row) for row in cursor.fetchall()]


# ==============================================================================
# DASHBOARD TELEMETRY & AGGREGATE STATISTICS
# ==============================================================================

def get_response_dashboard_stats() -> Dict[str, Any]:
    """Computes real-time KPI counters for emergency response tracking."""
    db = get_db()

    total_contacted = db.execute("SELECT COUNT(*) FROM emergency_requests").fetchone()[0]
    pending = db.execute("SELECT COUNT(*) FROM emergency_requests WHERE current_status = 'Pending'").fetchone()[0]
    acknowledged = db.execute("SELECT COUNT(*) FROM emergency_requests WHERE current_status = 'Acknowledged'").fetchone()[0]
    dispatched = db.execute("SELECT COUNT(*) FROM emergency_requests WHERE current_status IN ('Dispatched', 'On The Way')").fetchone()[0]
    in_progress = db.execute("SELECT COUNT(*) FROM emergency_requests WHERE current_status IN ('Arrived', 'Assistance In Progress')").fetchone()[0]
    completed = db.execute("SELECT COUNT(*) FROM emergency_requests WHERE current_status = 'Completed'").fetchone()[0]
    rejected = db.execute("SELECT COUNT(*) FROM emergency_requests WHERE current_status = 'Rejected'").fetchone()[0]

    orgs_count = db.execute("SELECT COUNT(*) FROM organizations").fetchone()[0]
    available_orgs = db.execute("SELECT COUNT(*) FROM organizations WHERE availability_status = 'AVAILABLE'").fetchone()[0]

    return {
        "status": "success",
        "total_contacted": total_contacted,
        "pending_responses": pending,
        "acknowledged_requests": acknowledged,
        "teams_dispatched": dispatched,
        "assistance_in_progress": in_progress,
        "completed_operations": completed,
        "rejected_requests": rejected,
        "total_organizations": orgs_count,
        "available_organizations": available_orgs,
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    }


# ==============================================================================
# AUTHENTICATION & RESPONDER USER SESSIONS
# ==============================================================================

def authenticate_org_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticates an organization user by username & password, returns user profile + org data."""
    db = get_db()
    cursor = db.execute(
        """
        SELECT u.id, u.org_id, u.username, u.password_hash, u.full_name, u.role, u.auth_token, u.is_active,
               o.org_uid, o.name as org_name, o.category as org_category, o.city, o.state, o.availability_status
        FROM organization_users u
        JOIN organizations o ON u.org_id = o.id
        WHERE u.username = ?
        """,
        (username,)
    )
    row = cursor.fetchone()
    if not row:
        return None

    user = dict(row)
    if not user["is_active"]:
        return None

    if not check_password_hash(user["password_hash"], password):
        return None

    # Strip hash from return
    del user["password_hash"]
    return user


def get_user_by_token(token: str) -> Optional[Dict[str, Any]]:
    """Validates an auth token and retrieves user profile."""
    if not token:
        return None
    db = get_db()
    cursor = db.execute(
        """
        SELECT u.id, u.org_id, u.username, u.full_name, u.role, u.auth_token,
               o.org_uid, o.name as org_name, o.category as org_category, o.city, o.state, o.availability_status
        FROM organization_users u
        JOIN organizations o ON u.org_id = o.id
        WHERE u.auth_token = ? AND u.is_active = 1
        """,
        (token,)
    )
    row = cursor.fetchone()
    return dict(row) if row else None


# ==============================================================================
# LIVE LOCATION UPDATES
# ==============================================================================

def record_team_location(request_id: int, lat: float, lon: float, speed_kmh: float = 0.0, heading: float = 0.0) -> Dict[str, Any]:
    """Records real-time GPS coordinate updates from an active responding unit."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        """
        INSERT INTO response_location_updates (request_id, latitude, longitude, speed_kmh, heading)
        VALUES (?, ?, ?, ?, ?)
        """,
        (request_id, lat, lon, speed_kmh, heading)
    )
    db.commit()
    return {
        "status": "success",
        "request_id": request_id,
        "latitude": lat,
        "longitude": lon,
        "speed_kmh": speed_kmh,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    }


def get_latest_team_location(request_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves the latest verified GPS coordinate update for a responding team."""
    db = get_db()
    cursor = db.execute(
        """
        SELECT * FROM response_location_updates
        WHERE request_id = ?
        ORDER BY timestamp DESC LIMIT 1
        """,
        (request_id,)
    )
    row = cursor.fetchone()
    return dict(row) if row else None

