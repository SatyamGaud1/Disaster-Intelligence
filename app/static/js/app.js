/**
 * Disaster Intelligence Platform - Frontend Application Script
 * Vanilla JavaScript implementation for Leaflet.js mapping, telemetry polling, and incident streams.
 */

document.addEventListener("DOMContentLoaded", () => {
    initClock();
    const mapController = initMap();
    initModal();
    fetchBackendHealth();

    // Check if on dedicated views or General Dashboard
    const isFireView = document.getElementById("fire-incidents-table-body") !== null;
    const isFloodView = document.getElementById("flood-incidents-table-body") !== null;
    const isDroughtView = document.getElementById("drought-incidents-table-body") !== null;
    const isCycloneView = document.getElementById("cyclone-advisories-list") !== null;
    const isResponseView = document.getElementById("response-tracking-table-body") !== null;
    const isOrgPortal = document.getElementById("org-login-panel") !== null;
    const isEvacuationView = document.getElementById("evac-destinations-container") !== null;

    if (isFireView) {
        initFireModule(mapController);
    } else if (isFloodView) {
        initFloodModule(mapController);
    } else if (isDroughtView) {
        initDroughtModule(mapController);
    } else if (isCycloneView) {
        initCycloneModule(mapController);
    } else if (isResponseView) {
        initResponseModule(mapController);
    } else if (isOrgPortal) {
        initOrgPortal();
    } else if (isEvacuationView) {
        initEvacuationModule(mapController);
    } else {
        fetchDashboardStats();
        fetchIncidents(mapController);
    }

    // Initialize AI Disaster Risk Prediction Modules if present
    if (document.getElementById("fire-risk-form")) {
        initFireRiskSimulator();
        fetchFireRiskMetrics();
        if (document.getElementById("monitored-zones-container")) {
            fetchMonitoredFireZones();
        }
    }

    if (document.getElementById("flood-risk-form")) {
        initFloodRiskSimulator();
        fetchFloodRiskMetrics();
        if (document.getElementById("monitored-flood-zones-container")) {
            fetchMonitoredFloodZones();
        }
    }

    if (document.getElementById("drought-risk-form")) {
        initDroughtRiskSimulator();
        fetchDroughtRiskMetrics();
        if (document.getElementById("monitored-drought-zones-container")) {
            fetchMonitoredDroughtZones();
        }
    }

    if (document.getElementById("cyclone-risk-form")) {
        initCycloneRiskSimulator();
        fetchCycloneRiskMetrics();
        if (document.getElementById("monitored-cyclone-zones-container")) {
            fetchMonitoredCycloneZones();
        }
    }

    // Initialize 1-Click Live Weather Auto-Fill & Map Probe
    initWeatherAutoFill(mapController);

    // Bind Global Sync Feeds button
    const refreshBtn = document.getElementById("refresh-data-btn");
    if (refreshBtn) {
        refreshBtn.addEventListener("click", async () => {
            refreshBtn.classList.add("loading");
            // Trigger backend sync across active pipelines
            try {
                await Promise.all([
                    fetch("/api/fire/sync", { method: "POST" }),
                    fetch("/api/flood/sync", { method: "POST" }),
                    fetch("/api/drought/sync", { method: "POST" })
                ]);
            } catch (e) {
                console.warn("Sync triggered:", e);
            }
            fetchBackendHealth();
            if (isFireView) {
                initFireModule(mapController);
            } else if (isFloodView) {
                initFloodModule(mapController);
            } else if (isDroughtView) {
                initDroughtModule(mapController);
            } else {
                fetchDashboardStats();
                fetchIncidents(mapController);
            }
            setTimeout(() => refreshBtn.classList.remove("loading"), 600);
        });
    }
});

/**
 * Updates topbar live digital clock.
 */
function initClock() {
    const clockEl = document.getElementById("system-clock");
    const updateTime = () => {
        const now = new Date();
        if (clockEl) {
            clockEl.textContent = now.toTimeString().split(" ")[0] + " LOC";
        }
    };
    updateTime();
    setInterval(updateTime, 1000);
}

/**
 * Initializes Leaflet Map with real-world satellite imagery and a layer switcher.
 * Tile sources: ESRI World Imagery (satellite), OSM Street, CartoDB Dark, OpenTopoMap.
 * All tile providers are free and require no API key.
 */
function initMap() {
    const mapElement = document.getElementById("disaster-map");
    if (!mapElement) return null;

    // ── 1. Real Satellite Imagery (ESRI World Imagery) ─────────────────────────
    const satellite = L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        {
            attribution: "Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community",
            maxZoom: 19
        }
    );

    // ── 2. Satellite + Country/City Labels overlay (Hybrid) ────────────────────
    const hybridLabels = L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
        { opacity: 0.9, maxZoom: 19 }
    );
    const hybridGroup = L.layerGroup([satellite, hybridLabels]);

    // ── 3. OpenStreetMap Streets ────────────────────────────────────────────────
    const streets = L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            attribution: "&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors",
            maxZoom: 19
        }
    );

    // ── 4. CartoDB Dark Matter (Command Center aesthetic) ──────────────────────
    const darkMatter = L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        {
            attribution: "&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors &copy; <a href='https://carto.com/attributions'>CARTO</a>",
            subdomains: "abcd",
            maxZoom: 19
        }
    );

    // ── 5. OpenTopoMap — terrain & elevation contours ──────────────────────────
    const terrain = L.tileLayer(
        "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        {
            attribution: "Map data: &copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors, SRTM | Map style: &copy; <a href='https://opentopomap.org'>OpenTopoMap</a>",
            maxZoom: 17
        }
    );

    // ── Create Map — default to real satellite view ─────────────────────────────
    const map = L.map("disaster-map", {
        center: [20.0, 0.0],
        zoom: 2,
        zoomControl: true,
        attributionControl: true,
        layers: [satellite]
    });

    // ── Layer Switcher Control ──────────────────────────────────────────────────
    const baseLayers = {
        "\uD83D\uDEF0\uFE0F Satellite": satellite,
        "\uD83D\uDEF0\uFE0F Satellite + Labels": hybridGroup,
        "\uD83D\uDDFA\uFE0F Street Map": streets,
        "\uD83C\uDF11 Dark (Command)": darkMatter,
        "\uD83C\uDFD4\uFE0F Terrain": terrain
    };

    L.control.layers(baseLayers, null, {
        position: "topright",
        collapsed: true
    }).addTo(map);

    // ── Scale Bar ───────────────────────────────────────────────────────────────
    L.control.scale({ imperial: false, position: "bottomleft" }).addTo(map);

    // ── Incident Marker Layer ───────────────────────────────────────────────────
    const markerGroup = L.layerGroup().addTo(map);

    // Filter state
    let activeFilter = "ALL";
    let cachedIncidents = [];

    // Hazard type filter buttons (dashboard page)
    const filterBtns = document.querySelectorAll(".filter-btn[data-filter]");
    filterBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            filterBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            activeFilter = btn.dataset.filter;
            renderMarkers(cachedIncidents, markerGroup, map, activeFilter);
        });
    });

    return {
        map,
        markerGroup,
        setIncidents: (incidents) => {
            cachedIncidents = incidents;
            renderMarkers(cachedIncidents, markerGroup, map, activeFilter);
        }
    };
}
/**
 * Renders color-coded circular hazard markers on Leaflet map.
 */
function renderMarkers(incidents, markerGroup, map, filterType) {
    markerGroup.clearLayers();

    const filtered = (!filterType || filterType === "ALL")
        ? incidents
        : incidents.filter(i => i.hazard_type.toUpperCase() === filterType.toUpperCase());

    if (!filtered || filtered.length === 0) return;

    const bounds = [];

    filtered.forEach(inc => {
        let color = "#38bdf8"; // default cyan
        if (inc.hazard_type === "FIRE") color = "#ff4d4f";
        if (inc.hazard_type === "FLOOD") color = "#00d2ff";
        if (inc.hazard_type === "DROUGHT") color = "#faad14";
        if (inc.hazard_type === "CYCLONE") color = "#a855f7";

        const latLng = [inc.centroid_lat, inc.centroid_lon];
        bounds.push(latLng);

        // Circular hazard marker sized by priority
        const radius = Math.max(8, Math.min(inc.priority_score / 4, 22));

        const circle = L.circleMarker(latLng, {
            radius: radius,
            fillColor: color,
            color: "#ffffff",
            weight: 1.5,
            opacity: 0.9,
            fillOpacity: 0.7
        });

        const popupContent = `
            <div class="popup-box">
                <div class="popup-title">${inc.title}</div>
                <div class="popup-desc">${inc.summary || "No automated summary generated yet."}</div>
                <div class="popup-meta-grid">
                    <div class="popup-meta-item"><strong>UID:</strong> ${inc.incident_uid}</div>
                    <div class="popup-meta-item"><strong>HAZARD:</strong> ${inc.hazard_type}</div>
                    <div class="popup-meta-item"><strong>PRIORITY:</strong> ${inc.priority_score.toFixed(1)}/100 (${inc.priority_level})</div>
                    <div class="popup-meta-item"><strong>CONFIDENCE:</strong> ${(inc.confidence_score * 100).toFixed(0)}%</div>
                    <div class="popup-meta-item"><strong>AREA:</strong> ~${inc.affected_area_sqkm} kmÂ²</div>
                    <div class="popup-meta-item"><strong>STATUS:</strong> ${inc.status}</div>
                </div>
                <div style="margin-top:10px; text-align:right;">
                    <button class="action-inspect-btn" onclick="openIncidentModal('${inc.incident_uid}')">Inspect & PDF Report</button>
                </div>
            </div>
        `;

        circle.bindPopup(popupContent);
        markerGroup.addLayer(circle);
    });

    if (bounds.length > 0) {
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 6 });
    }
}

/**
 * Checks backend health and updates sidebar indicator.
 */
async function fetchBackendHealth() {
    const dot = document.getElementById("backend-status-dot");
    const text = document.getElementById("backend-status-text");

    try {
        const res = await fetch("/api/health");
        const data = await res.json();

        if (res.ok && data.status === "healthy") {
            if (dot) dot.className = "status-indicator online";
            if (text) text.textContent = `Backend Ready (v${data.version})`;
        } else {
            throw new Error(data.message || "Degraded");
        }
    } catch (err) {
        if (dot) dot.className = "status-indicator offline";
        if (text) text.textContent = "Backend Offline";
        console.warn("Backend health check:", err);
    }
}

/**
 * Fetches dashboard KPI counters.
 */
async function fetchDashboardStats() {
    try {
        const res = await fetch("/api/stats");
        const data = await res.json();
        if (res.ok && data.metrics) {
            const m = data.metrics;
            const activeEl = document.getElementById("stat-active-incidents");
            const critEl = document.getElementById("stat-critical-incidents");
            const constEl = document.getElementById("stat-constellations");

            if (activeEl) activeEl.textContent = m.active_incidents || "0";
            if (critEl) critEl.textContent = m.critical_priority || "0";
            if (constEl) constEl.textContent = m.satellite_constellations || "4";
        }
    } catch (err) {
        console.warn("Telemetry stats fetch error:", err);
    }
}

/**
 * Fetches prioritized incidents from the backend and populates the stream table.
 */
async function fetchIncidents(mapController) {
    const tableBody = document.getElementById("incidents-table-body");
    const badge = document.getElementById("incident-count-badge");

    try {
        const res = await fetch("/api/incidents");
        const data = await res.json();

        if (res.ok && data.incidents) {
            const list = data.incidents;
            if (badge) badge.textContent = `${list.length} Monitored`;

            if (mapController && mapController.setIncidents) {
                mapController.setIncidents(list);
            }

            if (!tableBody) return;

            if (list.length === 0) {
                tableBody.innerHTML = `<tr><td colspan="6" class="table-loading">No active incidents recorded in SQLite database. Click "Sync Feeds" above to ingest NASA FIRMS data.</td></tr>`;
                return;
            }

            tableBody.innerHTML = list.map(item => {
                let badgeClass = "badge-info";
                if (item.priority_level === "CRITICAL") badgeClass = "badge-danger";
                else if (item.priority_level === "HIGH") badgeClass = "badge-warning";
                else if (item.priority_level === "MEDIUM") badgeClass = "badge-primary";

                let hazardDot = "fire";
                if (item.hazard_type === "FLOOD") hazardDot = "flood";
                if (item.hazard_type === "DROUGHT") hazardDot = "drought";

                return `
                    <tr>
                        <td class="incident-uid-cell">${item.incident_uid}</td>
                        <td>
                            <span class="module-dot ${hazardDot}" style="display:inline-block; vertical-align:middle; margin-right:6px;"></span>
                            <strong>${item.hazard_type}</strong>
                        </td>
                        <td>
                            <div>${item.title}</div>
                            <small style="color:var(--text-muted); font-family:var(--font-mono);">Coord: [${item.centroid_lat.toFixed(3)}, ${item.centroid_lon.toFixed(3)}]</small>
                        </td>
                        <td>
                            <span class="score-badge">${item.priority_score.toFixed(1)}</span>
                            <span class="badge ${badgeClass}" style="margin-left: 6px;">${item.priority_level}</span>
                        </td>
                        <td>${(item.confidence_score * 100).toFixed(0)}%</td>
                        <td>
                            <button class="action-inspect-btn" onclick="openIncidentModal('${item.incident_uid}')">Inspect & PDF</button>
                        </td>
                    </tr>
                `;
            }).join("");
        }
    } catch (err) {
        console.error("Error fetching incidents:", err);
        if (tableBody) {
            tableBody.innerHTML = `<tr><td colspan="6" class="table-loading" style="color:var(--hazard-fire);">Failed to load incidents from server.</td></tr>`;
        }
    }
}

/**
 * Dedicated Controller for Forest Fire Monitoring Module.
 */
async function initFireModule(mapController) {
    const tableBody = document.getElementById("fire-incidents-table-body");
    const syncBtn = document.getElementById("sync-firms-now-btn");
    const viewClustersBtn = document.getElementById("view-fire-clusters-btn");
    const viewHotspotsBtn = document.getElementById("view-raw-hotspots-btn");

    let fireIncidents = [];
    let fireHotspots = [];

    async function loadData() {
        try {
            // Fetch fire incidents
            const incRes = await fetch("/api/fire/incidents");
            const incData = await incRes.json();
            fireIncidents = incData.incidents || [];

            // If empty, auto-sync first time
            if (fireIncidents.length === 0) {
                await fetch("/api/fire/sync", { method: "POST" });
                const retryRes = await fetch("/api/fire/incidents");
                const retryData = await retryRes.json();
                fireIncidents = retryData.incidents || [];
            }

            // Fetch raw hotspots
            const hotRes = await fetch("/api/fire/hotspots");
            const hotData = await hotRes.json();
            fireHotspots = hotData.hotspots || [];

            // Update KPI counters
            const clustersEl = document.getElementById("fire-clusters-count");
            const hotspotsEl = document.getElementById("fire-hotspots-count");
            const peakFrpEl = document.getElementById("fire-peak-frp");
            const nightEl = document.getElementById("fire-night-count");

            if (clustersEl) clustersEl.textContent = fireIncidents.length;
            if (hotspotsEl) hotspotsEl.textContent = fireHotspots.length;

            if (fireHotspots.length > 0) {
                const maxFrp = Math.max(...fireHotspots.map(h => h.frp || 0));
                if (peakFrpEl) peakFrpEl.textContent = `${maxFrp.toFixed(1)} MW`;

                let nightCount = 0;
                fireHotspots.forEach(h => {
                    try {
                        const meta = JSON.parse(h.metadata_json || "{}");
                        if (meta.daynight === "N") nightCount++;
                    } catch (e) { }
                });
                if (nightEl) nightEl.textContent = nightCount;
            }

            renderFireClustersMap();
            renderFireTable();
        } catch (err) {
            console.error("Fire module load error:", err);
        }
    }

    function renderFireClustersMap() {
        if (!mapController) return;
        mapController.setIncidents(fireIncidents);
    }

    function renderFireHotspotsMap() {
        if (!mapController) return;
        mapController.markerGroup.clearLayers();

        const bounds = [];
        fireHotspots.forEach(h => {
            const latLng = [h.latitude, h.longitude];
            bounds.push(latLng);

            const frp = h.frp || 10;
            let color = "#fadb14";
            if (frp > 80) color = "#ff4d4f";
            else if (frp > 40) color = "#faad14";

            const marker = L.circleMarker(latLng, {
                radius: Math.max(4, Math.min(frp / 8, 14)),
                fillColor: color,
                color: "#fff",
                weight: 1,
                opacity: 0.9,
                fillOpacity: 0.8
            });

            marker.bindPopup(`
                <div class="popup-box">
                    <div class="popup-title">Raw VIIRS Hotspot Detection</div>
                    <div class="popup-meta-grid">
                        <div class="popup-meta-item"><strong>FRP:</strong> ${frp.toFixed(1)} MW</div>
                        <div class="popup-meta-item"><strong>CONFIDENCE:</strong> ${(h.confidence * 100).toFixed(0)}%</div>
                        <div class="popup-meta-item"><strong>TIME:</strong> ${h.observation_timestamp}</div>
                        <div class="popup-meta-item"><strong>LAT/LON:</strong> ${h.latitude.toFixed(3)}, ${h.longitude.toFixed(3)}</div>
                    </div>
                </div>
            `);

            mapController.markerGroup.addLayer(marker);
        });

        if (bounds.length > 0) {
            mapController.map.fitBounds(bounds, { padding: [40, 40], maxZoom: 7 });
        }
    }

    function renderFireTable() {
        if (!tableBody) return;
        if (fireIncidents.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="6" class="table-loading">No active wildfire incidents detected.</td></tr>`;
            return;
        }

        tableBody.innerHTML = fireIncidents.map(inc => {
            let badgeClass = "badge-info";
            if (inc.priority_level === "CRITICAL") badgeClass = "badge-danger";
            else if (inc.priority_level === "HIGH") badgeClass = "badge-warning";
            else if (inc.priority_level === "MEDIUM") badgeClass = "badge-primary";

            return `
                <tr>
                    <td class="incident-uid-cell">${inc.incident_uid}</td>
                    <td>
                        <div><strong>${inc.title}</strong></div>
                        <small style="color:var(--text-muted); font-family:var(--font-mono);">Coord: [${inc.centroid_lat.toFixed(3)}, ${inc.centroid_lon.toFixed(3)}]</small>
                    </td>
                    <td>
                        <span class="score-badge">${inc.priority_score.toFixed(1)}</span>
                        <span class="badge ${badgeClass}" style="margin-left: 6px;">${inc.priority_level}</span>
                    </td>
                    <td><strong style="color:var(--hazard-fire);">${inc.summary.match(/[\d\.]+\s*MW/) || "Active"}</strong></td>
                    <td>${inc.affected_area_sqkm} kmÂ²</td>
                    <td><span class="badge badge-success">${inc.status}</span></td>
                </tr>
            `;
        }).join("");
    }

    // Toggle events
    if (viewClustersBtn) {
        viewClustersBtn.addEventListener("click", () => {
            viewClustersBtn.classList.add("active");
            if (viewHotspotsBtn) viewHotspotsBtn.classList.remove("active");
            renderFireClustersMap();
        });
    }

    if (viewHotspotsBtn) {
        viewHotspotsBtn.addEventListener("click", () => {
            viewHotspotsBtn.classList.add("active");
            if (viewClustersBtn) viewClustersBtn.classList.remove("active");
            renderFireHotspotsMap();
        });
    }

    if (syncBtn) {
        syncBtn.addEventListener("click", async () => {
            syncBtn.style.opacity = "0.5";
            syncBtn.disabled = true;
            try {
                await fetch("/api/fire/sync", { method: "POST" });
                await loadData();
            } finally {
                syncBtn.style.opacity = "1";
                syncBtn.disabled = false;
            }
        });
    }

    // Initial load
    await loadData();
}

/**
 * Initializes the incident detail modal â€” wires close buttons and backdrop click.
 */
function initModal() {
    const overlay = document.getElementById("incident-modal");
    const closeBtn = document.getElementById("modal-close-btn");
    const dismissBtn = document.getElementById("modal-dismiss-btn");

    if (!overlay) return;

    function closeModal() {
        overlay.style.display = "none";
        document.body.style.overflow = "";
    }

    if (closeBtn) closeBtn.addEventListener("click", closeModal);
    if (dismissBtn) dismissBtn.addEventListener("click", closeModal);

    // Click on the dark backdrop to close
    overlay.addEventListener("click", (e) => {
        if (e.target === overlay) closeModal();
    });

    // ESC key to close
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && overlay.style.display !== "none") closeModal();
    });
}

/**
 * Opens the incident detail modal and fetches deep-dive intelligence from the API.
 * Called from map popup buttons and table row buttons.
 *
 * @param {string} incidentUid - The unique incident identifier (e.g. "INC-FIRE-001")
 */
async function openIncidentModal(incidentUid) {
    const overlay = document.getElementById("incident-modal");
    const titleEl = document.getElementById("modal-incident-title");
    const uidEl = document.getElementById("modal-incident-uid");
    const bodyEl = document.getElementById("modal-body-content");
    const pdfBtn = document.getElementById("modal-download-pdf-btn");

    if (!overlay) return;

    // Show modal with loading state
    overlay.style.display = "flex";
    document.body.style.overflow = "hidden";

    if (titleEl) titleEl.textContent = "Incident Intelligence & Situational Assessment";
    if (uidEl) uidEl.textContent = incidentUid;
    if (bodyEl) bodyEl.innerHTML = `<div class="loading-spinner">Loading incident intelligence for ${incidentUid}â€¦</div>`;
    if (pdfBtn) pdfBtn.href = `/api/incidents/${incidentUid}/pdf`;

    try {
        const res = await fetch(`/api/incidents/${incidentUid}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        const inc = data.incident || {};
        const expo = data.exposure || {};
        const comp = data.composite_priority || {};
        const summ = data.summary_intel || {};
        const hist = data.historical_comparison || {};

        // Update modal header
        if (titleEl) titleEl.textContent = inc.title || incidentUid;
        if (uidEl) {
            let levelColor = "#3b82f6";
            if (inc.priority_level === "CRITICAL") levelColor = "#ef4444";
            else if (inc.priority_level === "HIGH") levelColor = "#f59e0b";
            else if (inc.priority_level === "MEDIUM") levelColor = "#6366f1";
            uidEl.innerHTML = `${incidentUid} &nbsp;<span style="background:${levelColor}20;color:${levelColor};padding:2px 8px;border-radius:4px;font-size:0.75rem;">${inc.priority_level || ""}</span>`;
        }

        // Helper: render a section block
        const section = (label, html) => `
            <div style="margin-bottom:18px;">
                <div style="font-size:0.68rem;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:var(--text-muted);margin-bottom:8px;">${label}</div>
                ${html}
            </div>`;

        const metaGrid = (items) => `
            <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:8px;">
                ${items.map(([k, v]) => `
                    <div style="background:rgba(0,0,0,0.3);padding:8px 10px;border-radius:6px;font-family:var(--font-mono);font-size:0.72rem;">
                        <div style="color:var(--text-muted);margin-bottom:3px;">${k}</div>
                        <div style="color:var(--text-primary);font-weight:600;">${v ?? "â€”"}</div>
                    </div>`).join("")}
            </div>`;

        // --- Core telemetry ---
        const hazardColor = inc.hazard_type === "FIRE" ? "var(--hazard-fire)"
            : inc.hazard_type === "FLOOD" ? "var(--hazard-flood)"
                : "var(--hazard-drought)";

        let html = section("Core Incident Telemetry", metaGrid([
            ["Hazard Type", `<span style="color:${hazardColor}">${inc.hazard_type || "â€”"}</span>`],
            ["Priority Score", inc.priority_score != null ? `${inc.priority_score.toFixed(1)} / 100` : "â€”"],
            ["Confidence", inc.confidence_score != null ? `${(inc.confidence_score * 100).toFixed(0)}%` : "â€”"],
            ["Affected Area", inc.affected_area_sqkm != null ? `${inc.affected_area_sqkm} kmÂ²` : "â€”"],
            ["Centroid", inc.centroid_lat != null ? `${inc.centroid_lat.toFixed(3)}, ${inc.centroid_lon.toFixed(3)}` : "â€”"],
            ["Status", inc.status || "â€”"],
            ["Detected", inc.created_at ? inc.created_at.split("T")[0] : "â€”"],
            ["Composite Score", comp.composite_score != null ? `${comp.composite_score.toFixed(1)} / 100` : "â€”"],
        ]));

        // --- AI Summary ---
        if (summ.summary_text) {
            html += section("Automated Situation Assessment", `
                <div style="font-size:0.82rem;line-height:1.65;color:var(--text-secondary);background:rgba(0,0,0,0.25);padding:12px 14px;border-radius:8px;border-left:3px solid ${hazardColor};">
                    ${summ.summary_text}
                </div>`);
        }

        // --- Tactical directives ---
        if (summ.tactical_directives && summ.tactical_directives.length) {
            const items = summ.tactical_directives.map((d, i) =>
                `<li style="margin-bottom:6px;padding-left:8px;">[${String(i + 1).padStart(2, "0")}] ${d}</li>`
            ).join("");
            html += section("Tactical Directives", `<ol style="padding-left:16px;font-size:0.8rem;color:var(--text-secondary);line-height:1.6;">${items}</ol>`);
        }

        // --- Exposure & vulnerability ---
        if (expo && Object.keys(expo).length) {
            html += section("Population & Infrastructure Exposure", metaGrid([
                ["Exposure Score", expo.exposure_score != null ? `${expo.exposure_score.toFixed(1)} / 100` : "â€”"],
                ["Est. Population", expo.estimated_population != null ? expo.estimated_population.toLocaleString() : "â€”"],
                ["Urban Areas", expo.urban_areas_count != null ? expo.urban_areas_count : "â€”"],
                ["Critical Infra", expo.critical_infrastructure != null ? expo.critical_infrastructure : "â€”"],
                ["Road Network", expo.road_network_km != null ? `${expo.road_network_km} km` : "â€”"],
                ["River/Water Body", expo.water_body_proximity != null ? expo.water_body_proximity : "â€”"],
            ]));
        }

        // --- Historical comparison ---
        if (hist && hist.comparison_summary) {
            html += section("Historical Context & Baseline Comparison", `
                <div style="font-size:0.8rem;line-height:1.6;color:var(--text-secondary);background:rgba(0,0,0,0.2);padding:10px 12px;border-radius:6px;">
                    ${hist.comparison_summary}
                </div>`);
        }

        if (bodyEl) bodyEl.innerHTML = html;

    } catch (err) {
        console.error("Modal fetch error:", err);
        if (bodyEl) {
            bodyEl.innerHTML = `
                <div style="text-align:center;padding:30px;color:var(--hazard-fire);">
                    <div style="font-size:1.4rem;margin-bottom:8px;">âš </div>
                    <div style="font-weight:600;">Failed to load incident intelligence</div>
                    <div style="font-size:0.8rem;color:var(--text-muted);margin-top:6px;">${err.message}</div>
                </div>`;
        }
    }
}

/**
 * Dedicated Controller for Drought Monitoring Module (Copernicus Sentinel-2 MSI).
 */
async function initDroughtModule(mapController) {
    const tableBody = document.getElementById("drought-incidents-table-body");
    const syncBtn = document.getElementById("sync-drought-now-btn");
    const viewClustersBtn = document.getElementById("view-drought-clusters-btn");
    const viewMsiBtn = document.getElementById("view-raw-sentinel2-btn");

    let droughtIncidents = [];
    let droughtObservations = [];

    async function loadData() {
        try {
            // Fetch drought incidents
            const incRes = await fetch("/api/drought/incidents");
            const incData = await incRes.json();
            droughtIncidents = incData.incidents || [];

            // If empty, auto-sync first time
            if (droughtIncidents.length === 0) {
                await fetch("/api/drought/sync", { method: "POST" });
                const retryRes = await fetch("/api/drought/incidents");
                const retryData = await retryRes.json();
                droughtIncidents = retryData.incidents || [];
            }

            // Fetch raw MSI vegetation index observations
            const obsRes = await fetch("/api/drought/observations");
            const obsData = await obsRes.json();
            droughtObservations = obsData.observations || [];

            // Update KPI counters
            const clustersEl = document.getElementById("drought-clusters-count");
            const areaEl = document.getElementById("drought-total-area");
            const peakAnomalyEl = document.getElementById("drought-peak-anomaly");
            const meanNdwiEl = document.getElementById("drought-mean-ndwi");

            if (clustersEl) clustersEl.textContent = droughtIncidents.length;

            const totalArea = droughtIncidents.reduce((acc, curr) => acc + (curr.affected_area_sqkm || 0), 0);
            if (areaEl) areaEl.textContent = `${totalArea.toFixed(1)} kmÂ²`;

            if (droughtObservations.length > 0) {
                let maxAnomaly = 0;
                let sumNdwi = 0;
                droughtObservations.forEach(o => {
                    const drop = o.ndvi_anomaly_drop || 0;
                    if (drop > maxAnomaly) maxAnomaly = drop;
                    try {
                        const meta = JSON.parse(o.metadata_json || "{}");
                        sumNdwi += (meta.ndwi_moisture || 0);
                    } catch (e) { }
                });

                if (peakAnomalyEl) peakAnomalyEl.textContent = `-${maxAnomaly.toFixed(2)}`;
                if (meanNdwiEl) meanNdwiEl.textContent = `${(sumNdwi / droughtObservations.length).toFixed(2)}`;
            }

            renderDroughtClustersMap();
            renderDroughtTable();
        } catch (err) {
            console.error("Drought module load error:", err);
        }
    }

    function renderDroughtClustersMap() {
        if (!mapController) return;
        mapController.setIncidents(droughtIncidents);
    }

    function renderDroughtMsiMap() {
        if (!mapController) return;
        mapController.markerGroup.clearLayers();

        const bounds = [];
        droughtObservations.forEach(o => {
            const latLng = [o.latitude, o.longitude];
            bounds.push(latLng);

            const drop = o.ndvi_anomaly_drop || 0.25;
            let color = "#fde047";
            if (drop > 0.30) color = "#b45309";
            else if (drop > 0.20) color = "#f59e0b";

            let meta = {};
            try { meta = JSON.parse(o.metadata_json || "{}"); } catch (e) { }

            const marker = L.circleMarker(latLng, {
                radius: Math.max(5, Math.min(drop * 40, 16)),
                fillColor: color,
                color: "#ffffff",
                weight: 1.2,
                opacity: 0.9,
                fillOpacity: 0.75
            });

            marker.bindPopup(`
                <div class="popup-box">
                    <div class="popup-title">Sentinel-2 MSI Vegetation Observation</div>
                    <div class="popup-meta-grid">
                        <div class="popup-meta-item"><strong>Î”NDVI DROP:</strong> -${drop.toFixed(2)}</div>
                        <div class="popup-meta-item"><strong>NDWI MOISTURE:</strong> ${meta.ndwi_moisture !== undefined ? meta.ndwi_moisture.toFixed(2) : "--"}</div>
                        <div class="popup-meta-item"><strong>CURRENT NDVI:</strong> ${meta.ndvi_current || "--"}</div>
                        <div class="popup-meta-item"><strong>BASELINE NDVI:</strong> ${meta.ndvi_baseline || "--"}</div>
                        <div class="popup-meta-item"><strong>VCI PERCENTILE:</strong> ${meta.vci_percent || "--"}%</div>
                        <div class="popup-meta-item"><strong>AGROZONE:</strong> ${meta.agricultural_zone || "Crop Basin"}</div>
                    </div>
                </div>
            `);

            mapController.markerGroup.addLayer(marker);
        });

        if (bounds.length > 0) {
            mapController.map.fitBounds(bounds, { padding: [40, 40], maxZoom: 6 });
        }
    }

    function renderDroughtTable() {
        if (!tableBody) return;
        if (droughtIncidents.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="6" class="table-loading">No active drought complexes recorded.</td></tr>`;
            return;
        }

        tableBody.innerHTML = droughtIncidents.map(inc => {
            let badgeClass = "badge-info";
            if (inc.priority_level === "CRITICAL") badgeClass = "badge-danger";
            else if (inc.priority_level === "HIGH") badgeClass = "badge-warning";
            else if (inc.priority_level === "MEDIUM") badgeClass = "badge-primary";

            return `
                <tr>
                    <td class="incident-uid-cell">${inc.incident_uid}</td>
                    <td>
                        <div><strong>${inc.title}</strong></div>
                        <small style="color:var(--text-muted); font-family:var(--font-mono);">Coord: [${inc.centroid_lat.toFixed(3)}, ${inc.centroid_lon.toFixed(3)}]</small>
                    </td>
                    <td>
                        <span class="score-badge">${inc.priority_score.toFixed(1)}</span>
                        <span class="badge ${badgeClass}" style="margin-left: 6px;">${inc.priority_level}</span>
                    </td>
                    <td><strong style="color:var(--hazard-drought);">${inc.summary.match(/-[\d\.]+\s*\(VCI/) || "Î”NDVI Stress"}</strong></td>
                    <td>${inc.affected_area_sqkm} kmÂ²</td>
                    <td><span class="badge badge-warning">${inc.status}</span></td>
                </tr>
            `;
        }).join("");
    }

    // Toggle controls
    if (viewClustersBtn) {
        viewClustersBtn.addEventListener("click", () => {
            viewClustersBtn.classList.add("active");
            if (viewMsiBtn) viewMsiBtn.classList.remove("active");
            renderDroughtClustersMap();
        });
    }

    if (viewMsiBtn) {
        viewMsiBtn.addEventListener("click", () => {
            viewMsiBtn.classList.add("active");
            if (viewClustersBtn) viewClustersBtn.classList.remove("active");
            renderDroughtMsiMap();
        });
    }

    if (syncBtn) {
        syncBtn.addEventListener("click", async () => {
            syncBtn.style.opacity = "0.5";
            syncBtn.disabled = true;
            try {
                await fetch("/api/drought/sync", { method: "POST" });
                await loadData();
            } finally {
                syncBtn.style.opacity = "1";
                syncBtn.disabled = false;
            }
        });
    }

    // Initial load
    await loadData();
}
/**
 * Dedicated Controller for Flood Monitoring Module (Copernicus Sentinel-1 SAR & NASA GPM).
 */
async function initFloodModule(mapController) {
    const tableBody = document.getElementById("flood-incidents-table-body");
    const syncBtn = document.getElementById("sync-flood-now-btn");
    const viewClustersBtn = document.getElementById("view-flood-clusters-btn");
    const viewSarBtn = document.getElementById("view-raw-sar-btn");

    let floodIncidents = [];
    let floodPixels = [];

    async function loadData() {
        try {
            // Fetch flood incidents
            const incRes = await fetch("/api/flood/incidents");
            const incData = await incRes.json();
            floodIncidents = incData.incidents || [];

            // If empty, auto-sync first time
            if (floodIncidents.length === 0) {
                await fetch("/api/flood/sync", { method: "POST" });
                const retryRes = await fetch("/api/flood/incidents");
                const retryData = await retryRes.json();
                floodIncidents = retryData.incidents || [];
            }

            // Fetch raw SAR inundation detections
            const sarRes = await fetch("/api/flood/inundation");
            const sarData = await sarRes.json();
            floodPixels = sarData.inundation_pixels || [];

            // Update KPI telemetry
            const clustersEl = document.getElementById("flood-clusters-count");
            const areaEl = document.getElementById("flood-total-area");
            const rainEl = document.getElementById("flood-peak-rainfall");
            const backscatterEl = document.getElementById("flood-mean-backscatter");

            if (clustersEl) clustersEl.textContent = floodIncidents.length;

            const totalArea = floodIncidents.reduce((acc, curr) => acc + (curr.affected_area_sqkm || 0), 0);
            if (areaEl) areaEl.textContent = `${totalArea.toFixed(1)} kmÂ²`;

            if (floodPixels.length > 0) {
                let maxRain = 0;
                let sumDrop = 0;
                floodPixels.forEach(p => {
                    sumDrop += (p.backscatter_drop_db || 0);
                    try {
                        const meta = JSON.parse(p.metadata_json || "{}");
                        if (meta.gpm_rainfall_mm_24h > maxRain) maxRain = meta.gpm_rainfall_mm_24h;
                    } catch (e) { }
                });

                if (rainEl) rainEl.textContent = `${maxRain.toFixed(1)} mm`;
                if (backscatterEl) backscatterEl.textContent = `-${(sumDrop / floodPixels.length).toFixed(1)} dB`;
            }

            renderFloodClustersMap();
            renderFloodTable();
        } catch (err) {
            console.error("Flood module load error:", err);
        }
    }

    function renderFloodClustersMap() {
        if (!mapController) return;
        mapController.setIncidents(floodIncidents);
    }

    function renderFloodSarMap() {
        if (!mapController) return;
        mapController.markerGroup.clearLayers();

        const bounds = [];
        floodPixels.forEach(p => {
            const latLng = [p.latitude, p.longitude];
            bounds.push(latLng);

            const drop = p.backscatter_drop_db || 8.0;
            let color = "#38bdf8";
            if (drop > 10.0) color = "#00d2ff";
            else if (drop > 7.0) color = "#0284c7";

            let meta = {};
            try { meta = JSON.parse(p.metadata_json || "{}"); } catch (e) { }

            const marker = L.circleMarker(latLng, {
                radius: Math.max(5, Math.min(drop * 1.2, 16)),
                fillColor: color,
                color: "#ffffff",
                weight: 1.2,
                opacity: 0.9,
                fillOpacity: 0.75
            });

            marker.bindPopup(`
                <div class="popup-box">
                    <div class="popup-title">Sentinel-1 SAR Radar Detection</div>
                    <div class="popup-meta-grid">
                        <div class="popup-meta-item"><strong>Î”Ïƒâ° DROP:</strong> -${drop.toFixed(1)} dB</div>
                        <div class="popup-meta-item"><strong>INUNDATION PROB:</strong> ${((p.inundation_prob || 0.8) * 100).toFixed(0)}%</div>
                        <div class="popup-meta-item"><strong>POLARIZATION:</strong> ${meta.polarization || "VH"}</div>
                        <div class="popup-meta-item"><strong>GPM 24H RAIN:</strong> ${meta.gpm_rainfall_mm_24h || "--"} mm</div>
                        <div class="popup-meta-item"><strong>BASIN:</strong> ${meta.region_name || "River Basin"}</div>
                        <div class="popup-meta-item"><strong>PASS:</strong> ${meta.orbit_pass || "DESCENDING"}</div>
                    </div>
                </div>
            `);

            mapController.markerGroup.addLayer(marker);
        });

        if (bounds.length > 0) {
            mapController.map.fitBounds(bounds, { padding: [40, 40], maxZoom: 7 });
        }
    }

    function renderFloodTable() {
        if (!tableBody) return;
        if (floodIncidents.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="6" class="table-loading">No active flood incidents recorded.</td></tr>`;
            return;
        }

        tableBody.innerHTML = floodIncidents.map(inc => {
            let badgeClass = "badge-info";
            if (inc.priority_level === "CRITICAL") badgeClass = "badge-danger";
            else if (inc.priority_level === "HIGH") badgeClass = "badge-warning";
            else if (inc.priority_level === "MEDIUM") badgeClass = "badge-primary";

            return `
                <tr>
                    <td class="incident-uid-cell">${inc.incident_uid}</td>
                    <td>
                        <div><strong>${inc.title}</strong></div>
                        <small style="color:var(--text-muted); font-family:var(--font-mono);">Coord: [${inc.centroid_lat.toFixed(3)}, ${inc.centroid_lon.toFixed(3)}]</small>
                    </td>
                    <td>
                        <span class="score-badge">${inc.priority_score.toFixed(1)}</span>
                        <span class="badge ${badgeClass}" style="margin-left: 6px;">${inc.priority_level}</span>
                    </td>
                    <td><strong style="color:var(--hazard-flood);">${inc.summary.match(/[\d\.]+\s*dB/) || "SAR Drop"}</strong></td>
                    <td>${inc.affected_area_sqkm} kmÂ²</td>
                    <td><span class="badge badge-success">${inc.status}</span></td>
                </tr>
            `;
        }).join("");
    }

    // Toggle controls
    if (viewClustersBtn) {
        viewClustersBtn.addEventListener("click", () => {
            viewClustersBtn.classList.add("active");
            if (viewSarBtn) viewSarBtn.classList.remove("active");
            renderFloodClustersMap();
        });
    }

    if (viewSarBtn) {
        viewSarBtn.addEventListener("click", () => {
            viewSarBtn.classList.add("active");
            if (viewClustersBtn) viewClustersBtn.classList.remove("active");
            renderFloodSarMap();
        });
    }

    if (syncBtn) {
        syncBtn.addEventListener("click", async () => {
            syncBtn.style.opacity = "0.5";
            syncBtn.disabled = true;
            try {
                await fetch("/api/flood/sync", { method: "POST" });
                await loadData();
            } finally {
                syncBtn.style.opacity = "1";
                syncBtn.disabled = false;
            }
        });
    }

    // Initial load
    await loadData();
}


/**
 * ==============================================================================
 * AI ENVIRONMENTAL DISASTER RISK PREDICTION & SIMULATION CONTROLLERS
 * ==============================================================================
 */

/**
 * Initializes the Interactive Weather & Environmental Fire Risk Simulator.
 * Attaches real-time change listeners to sliders and updates risk gauges.
 */
function initFireRiskSimulator() {
    const sliderTemp = document.getElementById("slider-temp");
    const sliderHum = document.getElementById("slider-humidity");
    const sliderWind = document.getElementById("slider-wind");
    const sliderRain = document.getElementById("slider-rain");
    const sliderNdvi = document.getElementById("slider-ndvi");

    if (!sliderTemp || !sliderHum || !sliderWind || !sliderRain || !sliderNdvi) return;

    let debounceTimer = null;

    async function triggerPrediction() {
        const temp = parseFloat(sliderTemp.value);
        const humidity = parseFloat(sliderHum.value);
        const wind = parseFloat(sliderWind.value);
        const rain = parseFloat(sliderRain.value);
        const ndvi = parseFloat(sliderNdvi.value);

        // Update slider value displays immediately
        const valTempEl = document.getElementById("val-temp");
        const valHumEl = document.getElementById("val-humidity");
        const valWindEl = document.getElementById("val-wind");
        const valRainEl = document.getElementById("val-rain");
        const valNdviEl = document.getElementById("val-ndvi");

        if (valTempEl) valTempEl.textContent = `${temp.toFixed(1)} °C`;
        if (valHumEl) valHumEl.textContent = `${humidity.toFixed(1)} %`;
        if (valWindEl) valWindEl.textContent = `${wind.toFixed(1)} km/h`;
        if (valRainEl) valRainEl.textContent = `${rain.toFixed(1)} mm`;
        if (valNdviEl) {
            let ndviLabel = "Moderate Canopy";
            if (ndvi <= 0.25) ndviLabel = "Dry / Fuel Stressed";
            else if (ndvi >= 0.50) ndviLabel = "Moist / Green";
            valNdviEl.textContent = `${ndvi.toFixed(3)} (${ndviLabel})`;
        }

        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
            try {
                const res = await fetch("/api/risk/fire/predict", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        temperature_c: temp,
                        relative_humidity_pct: humidity,
                        wind_speed_kmh: wind,
                        rainfall_mm: rain,
                        vegetation_ndvi: ndvi
                    })
                });

                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const data = await res.json();
                const pred = data.prediction;

                // 1. Update Risk Score & Category Badge
                const scoreEl = document.getElementById("risk-score-display");
                const badgeEl = document.getElementById("risk-category-badge");

                let scoreColor = "#10b981"; // Low (green)
                let badgeClass = "risk-badge low";

                if (pred.risk_category === "HIGH") {
                    scoreColor = "#ef4444";
                    badgeClass = "risk-badge high";
                } else if (pred.risk_category === "MEDIUM") {
                    scoreColor = "#f59e0b";
                    badgeClass = "risk-badge medium";
                }

                if (scoreEl) {
                    scoreEl.textContent = `${pred.risk_score.toFixed(1)} %`;
                    scoreEl.style.color = scoreColor;
                }

                if (badgeEl) {
                    badgeEl.className = badgeClass;
                    badgeEl.textContent = `${pred.risk_category} RISK`;
                }

                // 2. Update Uncertainty Readout
                const uncertEl = document.getElementById("uncertainty-display");
                if (uncertEl) {
                    uncertEl.textContent = `${pred.uncertainty_pct.toFixed(1)}% (${pred.uncertainty_level})`;
                    uncertEl.style.color = pred.uncertainty_level === "HIGH" ? "#f59e0b" : "#38bdf8";
                }

                // 3. Update Factor Breakdown Bars
                const factorsEl = document.getElementById("factor-bars-container");
                if (factorsEl && pred.factor_contributions) {
                    factorsEl.innerHTML = pred.factor_contributions.map(f => {
                        let fillClass = "low";
                        if (f.impact === "HIGH RISK") fillClass = "high";
                        else if (f.impact === "MODERATE") fillClass = "medium";

                        return `
                            <div class="factor-bar-row">
                                <div class="factor-bar-meta">
                                    <span>${f.name}: <strong>${f.value}</strong></span>
                                    <span style="font-size:0.7rem; font-weight:600;">${f.impact}</span>
                                </div>
                                <div class="factor-progress-bg">
                                    <div class="factor-progress-fill ${fillClass}" style="width: ${f.severity_score}%;"></div>
                                </div>
                            </div>
                        `;
                    }).join("");
                }

                // 4. Update Explanation Narrative
                const expEl = document.getElementById("risk-explanation-text");
                if (expEl) {
                    expEl.textContent = pred.explanation || "Risk calculation completed.";
                }

            } catch (err) {
                console.warn("Simulator prediction error:", err);
            }
        }, 120);
    }

    [sliderTemp, sliderHum, sliderWind, sliderRain, sliderNdvi].forEach(slider => {
        slider.addEventListener("input", triggerPrediction);
    });

    // Run initial prediction
    triggerPrediction();
}

/**
 * Fetches and displays ML model validation metrics (accuracy, recall, ROC-AUC).
 */
async function fetchFireRiskMetrics() {
    try {
        const res = await fetch("/api/risk/fire/metrics");
        if (!res.ok) return;
        const data = await res.json();
        const m = data.metrics || {};

        const accEl = document.getElementById("metric-accuracy-val");
        const recEl = document.getElementById("metric-recall-val");
        const rocEl = document.getElementById("metric-roc-val");

        if (accEl && m.accuracy !== undefined) {
            accEl.innerHTML = `Accuracy: <strong>${(m.accuracy * 100).toFixed(1)}%</strong>`;
        }
        if (recEl && m.recall !== undefined) {
            recEl.innerHTML = `Recall: <strong>${(m.recall * 100).toFixed(1)}%</strong>`;
        }
        if (rocEl && m.roc_auc !== undefined) {
            rocEl.innerHTML = `ROC-AUC: <strong>${m.roc_auc.toFixed(3)}</strong>`;
        }
    } catch (err) {
        console.warn("Error fetching ML metrics:", err);
    }
}

/**
 * Fetches and populates proactive wildland corridor risk cards.
 */
async function fetchMonitoredFireZones() {
    const container = document.getElementById("monitored-zones-container");
    if (!container) return;

    try {
        const res = await fetch("/api/risk/fire/zones");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const zones = data.zones || [];

        if (zones.length === 0) {
            container.innerHTML = '<div style="font-size:0.8rem; color:var(--text-muted);">No monitored zones configured.</div>';
            return;
        }

        container.innerHTML = zones.map(z => {
            let badgeClass = "risk-badge low";
            if (z.risk_category === "HIGH") badgeClass = "risk-badge high";
            else if (z.risk_category === "MEDIUM") badgeClass = "risk-badge medium";

            const w = z.weather;
            return `
                <div class="zone-risk-card">
                    <div class="zone-risk-header">
                        <span class="zone-risk-name">${z.zone_name}</span>
                        <span class="${badgeClass}" style="font-size:0.7rem; padding:3px 8px;">${z.risk_category} (${z.risk_score.toFixed(0)}%)</span>
                    </div>
                    <div class="zone-weather-pills">
                        <span>${w.temperature_c.toFixed(1)}°C</span>
                        <span>${w.relative_humidity_pct.toFixed(0)}% RH</span>
                        <span>${w.wind_speed_kmh.toFixed(0)} km/h</span>
                        <span>${w.rainfall_mm.toFixed(1)} mm</span>
                        <span>NDVI ${w.vegetation_ndvi.toFixed(2)}</span>
                    </div>
                    <div style="font-size:0.75rem; color:var(--text-secondary); line-height:1.4;">
                        ${z.explanation}
                    </div>
                    <div style="font-size:0.68rem; color:var(--text-muted); display:flex; justify-content:space-between; margin-top:2px;">
                        <span>Coords: [${z.coordinates[0].toFixed(2)}, ${z.coordinates[1].toFixed(2)}]</span>
                        <span>Uncertainty: ${z.uncertainty_pct.toFixed(0)}%</span>
                    </div>
                </div>
            `;
        }).join("");
    } catch (err) {
        console.warn("Error fetching monitored fire zones:", err);
        container.innerHTML = '<div style="font-size:0.8rem; color:var(--hazard-fire);">Failed to load regional fire zones.</div>';
    }
}


/**
 * ==============================================================================
 * AI FLOOD INUNDATION RISK PREDICTION & SIMULATION CONTROLLERS
 * ==============================================================================
 */

/**
 * Initializes the Interactive Hydrological & Radar Flood Risk Simulator.
 */
function initFloodRiskSimulator() {
    const sliderRain = document.getElementById("flood-slider-rain");
    const sliderSoil = document.getElementById("flood-slider-soil");
    const sliderSar = document.getElementById("flood-slider-sar");
    const sliderElev = document.getElementById("flood-slider-elev");
    const sliderDist = document.getElementById("flood-slider-dist");

    if (!sliderRain || !sliderSoil || !sliderSar || !sliderElev || !sliderDist) return;

    let debounceTimer = null;

    async function triggerFloodPrediction() {
        const rain = parseFloat(sliderRain.value);
        const soil = parseFloat(sliderSoil.value);
        const sar = parseFloat(sliderSar.value);
        const elev = parseFloat(sliderElev.value);
        const dist = parseFloat(sliderDist.value);

        const valRainEl = document.getElementById("flood-val-rain");
        const valSoilEl = document.getElementById("flood-val-soil");
        const valSarEl = document.getElementById("flood-val-sar");
        const valElevEl = document.getElementById("flood-val-elev");
        const valDistEl = document.getElementById("flood-val-dist");

        if (valRainEl) valRainEl.textContent = `${rain.toFixed(1)} mm`;
        if (valSoilEl) valSoilEl.textContent = `${soil.toFixed(1)} %`;
        if (valSarEl) valSarEl.textContent = `-${sar.toFixed(1)} dB`;
        if (valElevEl) valElevEl.textContent = `${elev.toFixed(1)} m`;
        if (valDistEl) valDistEl.textContent = `${dist.toFixed(1)} km`;

        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
            try {
                const res = await fetch("/api/risk/flood/predict", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        precipitation_24h_mm: rain,
                        soil_moisture_pct: soil,
                        radar_backscatter_drop_db: sar,
                        elevation_m: elev,
                        river_proximity_km: dist
                    })
                });

                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const data = await res.json();
                const pred = data.prediction;

                const scoreEl = document.getElementById("flood-risk-score-display");
                const badgeEl = document.getElementById("flood-risk-category-badge");

                let scoreColor = "#10b981";
                let badgeClass = "risk-badge low";

                if (pred.risk_category === "HIGH") {
                    scoreColor = "#ef4444";
                    badgeClass = "risk-badge high";
                } else if (pred.risk_category === "MEDIUM") {
                    scoreColor = "#f59e0b";
                    badgeClass = "risk-badge medium";
                }

                if (scoreEl) {
                    scoreEl.textContent = `${pred.risk_score.toFixed(1)} %`;
                    scoreEl.style.color = scoreColor;
                }

                if (badgeEl) {
                    badgeEl.className = badgeClass;
                    badgeEl.textContent = `${pred.risk_category} RISK`;
                }

                const uncertEl = document.getElementById("flood-uncertainty-display");
                if (uncertEl) {
                    uncertEl.textContent = `${pred.uncertainty_pct.toFixed(1)}% (${pred.uncertainty_level})`;
                    uncertEl.style.color = pred.uncertainty_level === "HIGH" ? "#f59e0b" : "#38bdf8";
                }

                const factorsEl = document.getElementById("flood-factor-bars-container");
                if (factorsEl && pred.factor_contributions) {
                    factorsEl.innerHTML = pred.factor_contributions.map(f => {
                        let fillClass = "low";
                        if (f.impact === "HIGH RISK") fillClass = "high";
                        else if (f.impact === "MODERATE") fillClass = "medium";

                        return `
                            <div class="factor-bar-row">
                                <div class="factor-bar-meta">
                                    <span>${f.name}: <strong>${f.value}</strong></span>
                                    <span style="font-size:0.7rem; font-weight:600;">${f.impact}</span>
                                </div>
                                <div class="factor-progress-bg">
                                    <div class="factor-progress-fill ${fillClass}" style="width: ${f.severity_score}%;"></div>
                                </div>
                            </div>
                        `;
                    }).join("");
                }

                const expEl = document.getElementById("flood-risk-explanation-text");
                if (expEl) {
                    expEl.textContent = pred.explanation || "Flood risk calculation completed.";
                }

            } catch (err) {
                console.warn("Flood simulator prediction error:", err);
            }
        }, 120);
    }

    [sliderRain, sliderSoil, sliderSar, sliderElev, sliderDist].forEach(slider => {
        slider.addEventListener("input", triggerFloodPrediction);
    });

    triggerFloodPrediction();
}

/**
 * Fetches and displays Flood ML model validation metrics.
 */
async function fetchFloodRiskMetrics() {
    try {
        const res = await fetch("/api/risk/flood/metrics");
        if (!res.ok) return;
        const data = await res.json();
        const m = data.metrics || {};

        const accEl = document.getElementById("flood-metric-accuracy-val");
        const recEl = document.getElementById("flood-metric-recall-val");
        const rocEl = document.getElementById("flood-metric-roc-val");

        if (accEl && m.accuracy !== undefined) {
            accEl.innerHTML = `Accuracy: <strong>${(m.accuracy * 100).toFixed(1)}%</strong>`;
        }
        if (recEl && m.recall !== undefined) {
            recEl.innerHTML = `Recall: <strong>${(m.recall * 100).toFixed(1)}%</strong>`;
        }
        if (rocEl && m.roc_auc !== undefined) {
            rocEl.innerHTML = `ROC-AUC: <strong>${m.roc_auc.toFixed(3)}</strong>`;
        }
    } catch (err) {
        console.warn("Error fetching flood ML metrics:", err);
    }
}

/**
 * Fetches and populates proactive river basin risk cards.
 */
async function fetchMonitoredFloodZones() {
    const container = document.getElementById("monitored-flood-zones-container");
    if (!container) return;

    try {
        const res = await fetch("/api/risk/flood/zones");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const zones = data.zones || [];

        if (zones.length === 0) {
            container.innerHTML = '<div style="font-size:0.8rem; color:var(--text-muted);">No monitored river basins configured.</div>';
            return;
        }

        container.innerHTML = zones.map(b => {
            let badgeClass = "risk-badge low";
            if (b.risk_category === "HIGH") badgeClass = "risk-badge high";
            else if (b.risk_category === "MEDIUM") badgeClass = "risk-badge medium";

            const h = b.hydrology;
            return `
                <div class="zone-risk-card">
                    <div class="zone-risk-header">
                        <span class="zone-risk-name">${b.basin_name}</span>
                        <span class="${badgeClass}" style="font-size:0.7rem; padding:3px 8px;">${b.risk_category} (${b.risk_score.toFixed(0)}%)</span>
                    </div>
                    <div class="zone-weather-pills">
                        <span>${h.precipitation_24h_mm.toFixed(0)} mm Rain</span>
                        <span>${h.soil_moisture_pct.toFixed(0)}% Soil Sat</span>
                        <span>-${h.radar_backscatter_drop_db.toFixed(1)} dB SAR</span>
                        <span>${h.elevation_m.toFixed(0)} m Elev</span>
                        <span>${h.river_proximity_km.toFixed(1)} km Dist</span>
                    </div>
                    <div style="font-size:0.75rem; color:var(--text-secondary); line-height:1.4;">
                        ${b.explanation}
                    </div>
                    <div style="font-size:0.68rem; color:var(--text-muted); display:flex; justify-content:space-between; margin-top:2px;">
                        <span>Coords: [${b.coordinates[0].toFixed(2)}, ${b.coordinates[1].toFixed(2)}]</span>
                        <span>Uncertainty: ${b.uncertainty_pct.toFixed(0)}%</span>
                    </div>
                </div>
            `;
        }).join("");
    } catch (err) {
        console.warn("Error fetching monitored flood basins:", err);
        container.innerHTML = '<div style="font-size:0.8rem; color:var(--hazard-flood);">Failed to load river basin assessments.</div>';
    }
}


/**
 * ==============================================================================
 * AI DROUGHT CROP STRESS RISK PREDICTION & SIMULATION CONTROLLERS
 * ==============================================================================
 */

/**
 * Initializes the Interactive Multispectral & Climatic Drought Risk Simulator.
 */
function initDroughtRiskSimulator() {
    const sliderNdvi = document.getElementById("drought-slider-ndvi");
    const sliderNdwi = document.getElementById("drought-slider-ndwi");
    const sliderVci = document.getElementById("drought-slider-vci");
    const sliderDeficit = document.getElementById("drought-slider-deficit");
    const sliderTemp = document.getElementById("drought-slider-temp");

    if (!sliderNdvi || !sliderNdwi || !sliderVci || !sliderDeficit || !sliderTemp) return;

    let debounceTimer = null;

    async function triggerDroughtPrediction() {
        const ndvi = parseFloat(sliderNdvi.value);
        const ndwi = parseFloat(sliderNdwi.value);
        const vci = parseFloat(sliderVci.value);
        const deficit = parseFloat(sliderDeficit.value);
        const temp = parseFloat(sliderTemp.value);

        const valNdviEl = document.getElementById("drought-val-ndvi");
        const valNdwiEl = document.getElementById("drought-val-ndwi");
        const valVciEl = document.getElementById("drought-val-vci");
        const valDeficitEl = document.getElementById("drought-val-deficit");
        const valTempEl = document.getElementById("drought-val-temp");

        if (valNdviEl) {
            let desc = "Normal / Vigorous";
            if (ndvi <= -0.25) desc = "Severe Desiccation";
            else if (ndvi <= -0.10) desc = "Moderate Stress";
            valNdviEl.textContent = `${ndvi >= 0 ? '+' : ''}${ndvi.toFixed(3)} (${desc})`;
        }
        if (valNdwiEl) {
            let desc = "Hydrated";
            if (ndwi <= -0.15) desc = "Water Deficit";
            valNdwiEl.textContent = `${ndwi >= 0 ? '+' : ''}${ndwi.toFixed(3)} (${desc})`;
        }
        if (valVciEl) valVciEl.textContent = `${vci.toFixed(1)} % (${vci <= 20 ? 'Critical' : vci <= 45 ? 'Below Avg' : 'Healthy'})`;
        if (valDeficitEl) valDeficitEl.textContent = `${deficit.toFixed(1)} % Deficit`;
        if (valTempEl) valTempEl.textContent = `${temp.toFixed(1)} °C`;

        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
            try {
                const res = await fetch("/api/risk/drought/predict", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        ndvi_anomaly: ndvi,
                        ndwi_moisture: ndwi,
                        vci_percent: vci,
                        precipitation_deficit_pct: deficit,
                        soil_temperature_c: temp
                    })
                });

                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const data = await res.json();
                const pred = data.prediction;

                const scoreEl = document.getElementById("drought-risk-score-display");
                const badgeEl = document.getElementById("drought-risk-category-badge");

                let scoreColor = "#10b981";
                let badgeClass = "risk-badge low";

                if (pred.risk_category === "HIGH") {
                    scoreColor = "#ef4444";
                    badgeClass = "risk-badge high";
                } else if (pred.risk_category === "MEDIUM") {
                    scoreColor = "#f59e0b";
                    badgeClass = "risk-badge medium";
                }

                if (scoreEl) {
                    scoreEl.textContent = `${pred.risk_score.toFixed(1)} %`;
                    scoreEl.style.color = scoreColor;
                }

                if (badgeEl) {
                    badgeEl.className = badgeClass;
                    badgeEl.textContent = `${pred.risk_category} RISK`;
                }

                const uncertEl = document.getElementById("drought-uncertainty-display");
                if (uncertEl) {
                    uncertEl.textContent = `${pred.uncertainty_pct.toFixed(1)}% (${pred.uncertainty_level})`;
                    uncertEl.style.color = pred.uncertainty_level === "HIGH" ? "#f59e0b" : "#38bdf8";
                }

                const factorsEl = document.getElementById("drought-factor-bars-container");
                if (factorsEl && pred.factor_contributions) {
                    factorsEl.innerHTML = pred.factor_contributions.map(f => {
                        let fillClass = "low";
                        if (f.impact === "HIGH RISK") fillClass = "high";
                        else if (f.impact === "MODERATE") fillClass = "medium";

                        return `
                            <div class="factor-bar-row">
                                <div class="factor-bar-meta">
                                    <span>${f.name}: <strong>${f.value}</strong></span>
                                    <span style="font-size:0.7rem; font-weight:600;">${f.impact}</span>
                                </div>
                                <div class="factor-progress-bg">
                                    <div class="factor-progress-fill ${fillClass}" style="width: ${f.severity_score}%;"></div>
                                </div>
                            </div>
                        `;
                    }).join("");
                }

                const expEl = document.getElementById("drought-risk-explanation-text");
                if (expEl) {
                    expEl.textContent = pred.explanation || "Drought risk calculation completed.";
                }

            } catch (err) {
                console.warn("Drought simulator prediction error:", err);
            }
        }, 120);
    }

    [sliderNdvi, sliderNdwi, sliderVci, sliderDeficit, sliderTemp].forEach(slider => {
        slider.addEventListener("input", triggerDroughtPrediction);
    });

    triggerDroughtPrediction();
}

/**
 * Fetches and displays Drought ML model validation metrics.
 */
async function fetchDroughtRiskMetrics() {
    try {
        const res = await fetch("/api/risk/drought/metrics");
        if (!res.ok) return;
        const data = await res.json();
        const m = data.metrics || {};

        const accEl = document.getElementById("drought-metric-accuracy-val");
        const recEl = document.getElementById("drought-metric-recall-val");
        const rocEl = document.getElementById("drought-metric-roc-val");

        if (accEl && m.accuracy !== undefined) {
            accEl.innerHTML = `Accuracy: <strong>${(m.accuracy * 100).toFixed(1)}%</strong>`;
        }
        if (recEl && m.recall !== undefined) {
            recEl.innerHTML = `Recall: <strong>${(m.recall * 100).toFixed(1)}%</strong>`;
        }
        if (rocEl && m.roc_auc !== undefined) {
            rocEl.innerHTML = `ROC-AUC: <strong>${m.roc_auc.toFixed(3)}</strong>`;
        }
    } catch (err) {
        console.warn("Error fetching drought ML metrics:", err);
    }
}

/**
 * Fetches and populates proactive agricultural belt risk cards.
 */
async function fetchMonitoredDroughtZones() {
    const container = document.getElementById("monitored-drought-zones-container");
    if (!container) return;

    try {
        const res = await fetch("/api/risk/drought/zones");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const zones = data.zones || [];

        if (zones.length === 0) {
            container.innerHTML = '<div style="font-size:0.8rem; color:var(--text-muted);">No monitored agricultural zones configured.</div>';
            return;
        }

        container.innerHTML = zones.map(z => {
            let badgeClass = "risk-badge low";
            if (z.risk_category === "HIGH") badgeClass = "risk-badge high";
            else if (z.risk_category === "MEDIUM") badgeClass = "risk-badge medium";

            const v = z.vegetation;
            return `
                <div class="zone-risk-card">
                    <div class="zone-risk-header">
                        <span class="zone-risk-name">${z.zone_name}</span>
                        <span class="${badgeClass}" style="font-size:0.7rem; padding:3px 8px;">${z.risk_category} (${z.risk_score.toFixed(0)}%)</span>
                    </div>
                    <div class="zone-weather-pills">
                        <span>ΔNDVI ${v.ndvi_anomaly >= 0 ? '+' : ''}${v.ndvi_anomaly.toFixed(2)}</span>
                        <span>NDWI ${v.ndwi_moisture >= 0 ? '+' : ''}${v.ndwi_moisture.toFixed(2)}</span>
                        <span>VCI ${v.vci_percent.toFixed(0)}%</span>
                        <span>Deficit ${v.precipitation_deficit_pct.toFixed(0)}%</span>
                        <span>${v.soil_temperature_c.toFixed(1)}°C Soil</span>
                    </div>
                    <div style="font-size:0.75rem; color:var(--text-secondary); line-height:1.4;">
                        ${z.explanation}
                    </div>
                    <div style="font-size:0.68rem; color:var(--text-muted); display:flex; justify-content:space-between; margin-top:2px;">
                        <span>Coords: [${z.coordinates[0].toFixed(2)}, ${z.coordinates[1].toFixed(2)}]</span>
                        <span>Uncertainty: ${z.uncertainty_pct.toFixed(0)}%</span>
                    </div>
                </div>
            `;
        }).join("");
    } catch (err) {
        console.warn("Error fetching monitored drought zones:", err);
        container.innerHTML = '<div style="font-size:0.8rem; color:var(--hazard-drought);">Failed to load agricultural assessments.</div>';
    }
}

/**
 * ==============================================================================
 * CYCLONE TRACKING, PATH VISUALIZATION & RISK ASSESSMENT MODULE
 * ==============================================================================
 */

/**
 * Initializes the Cyclone Monitoring module page.
 */
async function initCycloneModule(mapController) {
    const selectEl = document.getElementById("cyclone-select");
    const refreshBtn = document.getElementById("refresh-cyclone-data-btn");

    async function loadCycloneOverview() {
        try {
            // 1. Fetch available storms and populate select if needed
            const stormsRes = await fetch("/api/cyclone/storms");
            if (stormsRes.ok) {
                const stormsData = await stormsRes.json();
                if (selectEl && stormsData.storms && stormsData.storms.length > 0) {
                    const currentVal = selectEl.value;
                    selectEl.innerHTML = stormsData.storms.map(s => `
                        <option value="${s.storm_id}" ${s.storm_id === currentVal ? "selected" : ""}>
                            ${s.name} (${s.basin}) - ${s.status}
                        </option>
                    `).join("");
                }
            }

            // 2. Fetch active storms telemetry
            const activeRes = await fetch("/api/cyclone/active");
            if (activeRes.ok) {
                const activeData = await activeRes.json();
                const systems = activeData.systems || [];
                const activeCountEl = document.getElementById("cyclone-active-count");
                const basinLabelEl = document.getElementById("cyclone-basin-label");

                if (activeCountEl) {
                    const activeOnly = systems.filter(s => s.is_active);
                    activeCountEl.textContent = activeOnly.length > 0 ? activeOnly.length : systems.length;
                }
                if (basinLabelEl && systems.length > 0) {
                    basinLabelEl.textContent = systems[0].basin;
                }

                // If a storm is selected or available, update telemetry cards
                const currentStormId = selectEl ? selectEl.value : (systems[0] ? systems[0].storm_id : null);
                const selectedSystem = systems.find(s => s.storm_id === currentStormId) || systems[0];
                if (selectedSystem) {
                    updateCycloneTelemetry(selectedSystem);
                }
            }

            // 3. Load selected storm track and render on map
            const targetId = selectEl ? selectEl.value : null;
            await loadAndRenderCycloneTrack(targetId, mapController);

            // 4. Load official advisories
            await loadCycloneAdvisories();
        } catch (err) {
            console.error("Error loading cyclone overview:", err);
        }
    }

    if (selectEl) {
        selectEl.addEventListener("change", async () => {
            const stormId = selectEl.value;
            // Update telemetry for selected storm
            const activeRes = await fetch("/api/cyclone/active");
            if (activeRes.ok) {
                const activeData = await activeRes.json();
                const match = (activeData.systems || []).find(s => s.storm_id === stormId);
                if (match) updateCycloneTelemetry(match);
            }
            await loadAndRenderCycloneTrack(stormId, mapController);
        });
    }

    if (refreshBtn) {
        refreshBtn.addEventListener("click", async () => {
            refreshBtn.classList.add("loading");
            await loadCycloneOverview();
            setTimeout(() => refreshBtn.classList.remove("loading"), 600);
        });
    }

    await loadCycloneOverview();
}

/**
 * Updates telemetry cards with data for the active/selected tropical cyclone.
 */
function updateCycloneTelemetry(system) {
    const peakWindEl = document.getElementById("cyclone-peak-wind");
    const windKnotsEl = document.getElementById("cyclone-wind-knots");
    const catBadgeEl = document.getElementById("cyclone-category-badge");
    const imdScaleEl = document.getElementById("cyclone-imd-scale-label");
    const minPressureEl = document.getElementById("cyclone-min-pressure");
    const trendLabelEl = document.getElementById("cyclone-trend-label");
    const coastDistEl = document.getElementById("cyclone-coast-dist");
    const coastTargetEl = document.getElementById("cyclone-coast-target");
    const forwardSpeedEl = document.getElementById("cyclone-forward-speed");
    const impactSectorEl = document.getElementById("cyclone-impact-sector");
    const impactTimingEl = document.getElementById("cyclone-impact-timing");

    if (peakWindEl) peakWindEl.textContent = `${system.max_sustained_wind_kmh} km/h`;
    if (windKnotsEl) windKnotsEl.textContent = `${system.max_sustained_wind_knots} knots (1-min sustained)`;
    if (catBadgeEl) catBadgeEl.textContent = system.category_saffir;
    if (imdScaleEl) imdScaleEl.textContent = `IMD Scale: ${system.category_imd}`;
    if (minPressureEl) minPressureEl.textContent = `${system.central_pressure_hpa} hPa`;
    if (trendLabelEl) trendLabelEl.textContent = `Trend: ${system.intensification_trend.replace("_", " ")}`;
    if (coastDistEl) coastDistEl.textContent = `${system.coastal_distance_km} km`;
    if (coastTargetEl) coastTargetEl.textContent = `Coast: ${system.nearest_coast_region}`;
    if (forwardSpeedEl) forwardSpeedEl.textContent = `Forward: ${system.movement_direction} at ${system.movement_speed_kmh} km/h`;
    if (impactSectorEl) impactSectorEl.textContent = `${system.nearest_coast_region}`;
    if (impactTimingEl) {
        const estHours = Math.max(1, Math.round(system.coastal_distance_km / Math.max(system.movement_speed_kmh, 1.0)));
        impactTimingEl.textContent = `Estimated landfall window: ~${estHours} hours at ${system.movement_speed_kmh} km/h forward speed`;
    }
}

/**
 * Loads track coordinates (observed & forecast) and renders Leaflet layers.
 */
async function loadAndRenderCycloneTrack(stormId, mapController) {
    if (!mapController || !mapController.map) return;

    try {
        const url = stormId ? `/api/cyclone/tracks?storm_id=${encodeURIComponent(stormId)}` : "/api/cyclone/tracks";
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        const data = json.data;

        mapController.markerGroup.clearLayers();
        const bounds = [];

        // 1. Render Forecast Uncertainty Cone (polygon)
        if (data.uncertainty_cone && data.uncertainty_cone.length >= 3) {
            const conePolygon = L.polygon(data.uncertainty_cone, {
                color: "#38bdf8",
                weight: 1.5,
                dashArray: "4, 4",
                fillColor: "#38bdf8",
                fillOpacity: 0.15
            });
            conePolygon.bindPopup(`
                <div class="popup-box">
                    <div class="popup-title">Official Forecast Uncertainty Cone</div>
                    <div class="popup-desc">NHC / IMD projected swath representing probable storm center path.</div>
                    <div class="popup-meta-item"><strong>Agency:</strong> ${data.issuing_agency}</div>
                </div>
            `);
            mapController.markerGroup.addLayer(conePolygon);
            data.uncertainty_cone.forEach(pt => bounds.push(pt));
        }

        // 2. Render Observed Historical Track Line
        const obsPoints = (data.observed_track || []).map(pt => [pt.latitude, pt.longitude]);
        if (obsPoints.length > 0) {
            const obsPolyline = L.polyline(obsPoints, {
                color: "#a855f7",
                weight: 3.5,
                opacity: 0.95
            });
            mapController.markerGroup.addLayer(obsPolyline);
            obsPoints.forEach(pt => bounds.push(pt));

            // Render individual observed eye markers
            data.observed_track.forEach((pt, idx) => {
                const isLatest = idx === data.observed_track.length - 1;
                const marker = L.circleMarker([pt.latitude, pt.longitude], {
                    radius: isLatest ? 8 : 5,
                    fillColor: isLatest ? "#ec4899" : "#a855f7",
                    color: "#ffffff",
                    weight: isLatest ? 2.5 : 1.5,
                    fillOpacity: 0.95
                });

                marker.bindPopup(`
                    <div class="popup-box">
                        <div class="popup-title">${data.storm_name} (Observed Eye)</div>
                        <div class="popup-desc">${pt.headline || ""}</div>
                        <div class="popup-meta-grid">
                            <div class="popup-meta-item"><strong>UTC Time:</strong> ${pt.timestamp_utc}</div>
                            <div class="popup-meta-item"><strong>Wind:</strong> ${pt.wind_kmh} km/h</div>
                            <div class="popup-meta-item"><strong>Pressure:</strong> ${pt.pressure_hpa} hPa</div>
                            <div class="popup-meta-item"><strong>Saffir:</strong> ${pt.category_saffir}</div>
                            <div class="popup-meta-item"><strong>IMD Scale:</strong> ${pt.category_imd}</div>
                        </div>
                    </div>
                `);
                mapController.markerGroup.addLayer(marker);

                // Add Gale/Hurricane wind radius circle around latest eye
                if (isLatest) {
                    const windCircle = L.circle([pt.latitude, pt.longitude], {
                        radius: 85000, // 85 km radius gale swath
                        color: "#ef4444",
                        weight: 1.5,
                        dashArray: "3, 3",
                        fillColor: "#ef4444",
                        fillOpacity: 0.12
                    });
                    windCircle.bindPopup(`<strong>Destructive Gale Wind Field (~85 km radius)</strong>`);
                    mapController.markerGroup.addLayer(windCircle);
                }
            });
        }

        // 3. Render Official Forecast Track Line (Dashed)
        const fcstPoints = (data.forecast_track || []).map(pt => [pt.latitude, pt.longitude]);
        if (fcstPoints.length > 0 && obsPoints.length > 0) {
            const combinedFcstLine = [obsPoints[obsPoints.length - 1], ...fcstPoints];
            const fcstPolyline = L.polyline(combinedFcstLine, {
                color: "#38bdf8",
                weight: 2.5,
                dashArray: "6, 6",
                opacity: 0.9
            });
            mapController.markerGroup.addLayer(fcstPolyline);
            fcstPoints.forEach(pt => bounds.push(pt));

            // Render forecast point markers
            data.forecast_track.forEach(fc => {
                const marker = L.circleMarker([fc.latitude, fc.longitude], {
                    radius: 5,
                    fillColor: "#0b152d",
                    color: "#38bdf8",
                    weight: 2,
                    fillOpacity: 0.85
                });
                marker.bindPopup(`
                    <div class="popup-box">
                        <div class="popup-title">${data.storm_name} (Official Forecast +${fc.forecast_hour}h)</div>
                        <div class="popup-desc">${fc.headline || "Official projected path"}</div>
                        <div class="popup-meta-grid">
                            <div class="popup-meta-item"><strong>Lead Time:</strong> +${fc.forecast_hour} Hours</div>
                            <div class="popup-meta-item"><strong>Projected Wind:</strong> ${fc.wind_kmh} km/h</div>
                            <div class="popup-meta-item"><strong>Pressure:</strong> ${fc.pressure_hpa} hPa</div>
                            <div class="popup-meta-item"><strong>Status:</strong> ${fc.category_saffir}</div>
                        </div>
                    </div>
                `);
                mapController.markerGroup.addLayer(marker);
            });
        }

        if (bounds.length > 0) {
            mapController.map.fitBounds(bounds, { padding: [50, 50], maxZoom: 8 });
        }
    } catch (err) {
        console.error("Error rendering cyclone track on map:", err);
    }
}

/**
 * Loads official tropical cyclone alerts & advisories into the feed.
 */
async function loadCycloneAdvisories() {
    const listEl = document.getElementById("cyclone-advisories-list");
    if (!listEl) return;

    try {
        const res = await fetch("/api/cyclone/advisories");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        const advisories = json.advisories || [];

        if (advisories.length === 0) {
            listEl.innerHTML = '<div style="padding:16px; color:var(--text-muted); font-size:0.85rem;">No active cyclone warnings currently issued.</div>';
            return;
        }

        listEl.innerHTML = advisories.map(adv => {
            let badgeBg = "rgba(56, 189, 248, 0.15)";
            let badgeColor = "#38bdf8";
            if (adv.warning_level_code === "RED") {
                badgeBg = "rgba(239, 68, 68, 0.2)";
                badgeColor = "#ef4444";
            } else if (adv.warning_level_code === "ORANGE") {
                badgeBg = "rgba(249, 115, 22, 0.2)";
                badgeColor = "#f97316";
            } else if (adv.warning_level_code === "YELLOW") {
                badgeBg = "rgba(234, 179, 8, 0.2)";
                badgeColor = "#eab308";
            }

            return `
                <div style="padding: 12px 16px; border-bottom: 1px solid var(--border-subtle); display:flex; flex-direction:column; gap:6px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="background:${badgeBg}; color:${badgeColor}; font-size:0.7rem; font-weight:700; padding:2px 8px; border-radius:4px; text-transform:uppercase;">
                            ${adv.warning_level}
                        </span>
                        <span style="font-size:0.72rem; color:var(--text-muted);">${adv.publication_time}</span>
                    </div>
                    <div style="font-size:0.88rem; font-weight:600; color:var(--text-primary); line-height:1.3;">
                        ${adv.headline}
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.75rem; color:var(--text-secondary); margin-top:2px;">
                        <span>Agency: <strong>${adv.issuing_agency}</strong></span>
                        <a href="${adv.advisory_url}" target="_blank" rel="noopener noreferrer" style="color:#38bdf8; text-decoration:none;">
                            View Official Bulletin &rarr;
                        </a>
                    </div>
                </div>
            `;
        }).join("");
    } catch (err) {
        console.error("Error loading cyclone advisories:", err);
        listEl.innerHTML = '<div style="padding:16px; color:var(--hazard-cyclone); font-size:0.85rem;">Failed to load official advisories.</div>';
    }
}

/**
 * Initializes the AI Cyclone Risk Simulator sliders and debounced prediction calls.
 */
function initCycloneRiskSimulator() {
    const sPressure = document.getElementById("cyclone-slider-pressure");
    const sWind = document.getElementById("cyclone-slider-wind");
    const sSst = document.getElementById("cyclone-slider-sst");
    const sSpeed = document.getElementById("cyclone-slider-speed");
    const sDist = document.getElementById("cyclone-slider-dist");

    const vPressure = document.getElementById("cyclone-val-pressure");
    const vWind = document.getElementById("cyclone-val-wind");
    const vSst = document.getElementById("cyclone-val-sst");
    const vSpeed = document.getElementById("cyclone-val-speed");
    const vDist = document.getElementById("cyclone-val-dist");

    if (!sPressure || !sWind || !sSst || !sSpeed || !sDist) return;

    let debounceTimer = null;

    function updateLabelsAndPredict() {
        const pressure = parseFloat(sPressure.value);
        const wind = parseFloat(sWind.value);
        const sst = parseFloat(sSst.value);
        const speed = parseFloat(sSpeed.value);
        const dist = parseFloat(sDist.value);

        if (vPressure) vPressure.textContent = `${pressure.toFixed(1)} hPa`;
        if (vWind) vWind.textContent = `${wind.toFixed(1)} km/h`;
        if (vSst) vSst.textContent = `${sst.toFixed(1)} °C`;
        if (vSpeed) vSpeed.textContent = `${speed.toFixed(1)} km/h`;
        if (vDist) vDist.textContent = `${dist.toFixed(1)} km`;

        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
            try {
                const res = await fetch("/api/risk/cyclone/predict", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        central_pressure_hpa: pressure,
                        max_sustained_wind_kmh: wind,
                        sea_surface_temp_c: sst,
                        storm_forward_speed_kmh: speed,
                        coastal_distance_km: dist
                    })
                });

                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const json = await res.json();
                if (json.status === "success" && json.data) {
                    renderCycloneRiskOutput(json.data);
                }
            } catch (err) {
                console.error("Cyclone risk simulator prediction error:", err);
            }
        }, 120);
    }

    [sPressure, sWind, sSst, sSpeed, sDist].forEach(slider => {
        slider.addEventListener("input", updateLabelsAndPredict);
    });

    // Run initial prediction
    updateLabelsAndPredict();
}

/**
 * Updates the risk score card, factor severity bars, and narrative for cyclone predictions.
 */
function renderCycloneRiskOutput(data) {
    const scoreEl = document.getElementById("cyclone-risk-score-display");
    const badgeEl = document.getElementById("cyclone-risk-category-badge");
    const saffirEl = document.getElementById("cyclone-saffir-output");
    const imdEl = document.getElementById("cyclone-imd-output");
    const uncertEl = document.getElementById("cyclone-uncertainty-display");
    const barsContainer = document.getElementById("cyclone-factor-bars-container");
    const explEl = document.getElementById("cyclone-risk-explanation-text");

    if (scoreEl) {
        scoreEl.textContent = `${data.risk_score.toFixed(1)} %`;
        if (data.risk_category === "HIGH") scoreEl.style.color = "#ef4444";
        else if (data.risk_category === "MEDIUM") scoreEl.style.color = "#f59e0b";
        else scoreEl.style.color = "#10b981";
    }

    if (badgeEl) {
        badgeEl.textContent = `${data.risk_category} RISK`;
        badgeEl.className = "risk-badge " + (data.risk_category ? data.risk_category.toLowerCase() : "low");
    }

    if (data.classifications) {
        if (saffirEl) saffirEl.textContent = data.classifications.saffir_simpson || "--";
        if (imdEl) imdEl.textContent = data.classifications.imd_scale || "--";
    }

    if (uncertEl) {
        uncertEl.textContent = `${data.uncertainty_pct.toFixed(1)} % (${data.uncertainty_level})`;
        if (data.uncertainty_level === "HIGH") uncertEl.style.color = "#ef4444";
        else if (data.uncertainty_level === "MODERATE") uncertEl.style.color = "#f59e0b";
        else uncertEl.style.color = "#38bdf8";
    }

    if (explEl) {
        explEl.textContent = data.explanation || "";
    }

    if (barsContainer && data.factor_contributions) {
        barsContainer.innerHTML = data.factor_contributions.map(f => {
            let barColor = "#10b981";
            if (f.impact === "CRITICAL" || f.impact === "HIGH RISK") barColor = "#ef4444";
            else if (f.impact === "MODERATE") barColor = "#f59e0b";

            return `
                <div class="factor-bar-row">
                    <div class="factor-bar-info">
                        <span class="factor-bar-name">${f.name}</span>
                        <span class="factor-bar-val" style="color:${barColor}; font-weight:600;">${f.value} (${f.impact})</span>
                    </div>
                    <div class="factor-bar-track">
                        <div class="factor-bar-fill" style="width: ${Math.min(100, f.severity_score)}%; background: ${barColor};"></div>
                    </div>
                </div>
            `;
        }).join("");
    }
}

/**
 * Fetches and displays Cyclone ML validation metrics.
 */
async function fetchCycloneRiskMetrics() {
    const strip = document.getElementById("cyclone-ml-metrics-strip");
    if (!strip) return;

    try {
        const res = await fetch("/api/risk/cyclone/metrics");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const m = data.metrics || {};

        const accEl = document.getElementById("cyclone-metric-accuracy-val");
        const recEl = document.getElementById("cyclone-metric-recall-val");
        const rocEl = document.getElementById("cyclone-metric-roc-val");

        if (accEl && m.accuracy) accEl.innerHTML = `Accuracy: <strong>${(m.accuracy * 100).toFixed(1)}%</strong>`;
        if (recEl && m.recall) recEl.innerHTML = `Recall: <strong>${(m.recall * 100).toFixed(1)}%</strong>`;
        if (rocEl && m.roc_auc) rocEl.innerHTML = `ROC-AUC: <strong>${m.roc_auc.toFixed(3)}</strong>`;
    } catch (err) {
        console.warn("Error fetching cyclone ML metrics:", err);
    }
}

/**
 * Fetches and populates proactive coastal & maritime sector risk cards.
 */
async function fetchMonitoredCycloneZones() {
    const container = document.getElementById("monitored-cyclone-zones-container");
    if (!container) return;

    try {
        const res = await fetch("/api/risk/cyclone/zones");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const zones = data.zones || [];

        if (zones.length === 0) {
            container.innerHTML = '<div style="font-size:0.8rem; color:var(--text-muted);">No monitored coastal sectors configured.</div>';
            return;
        }

        container.innerHTML = zones.map(z => {
            let badgeClass = "risk-badge low";
            if (z.risk_category === "HIGH") badgeClass = "risk-badge high";
            else if (z.risk_category === "MEDIUM") badgeClass = "risk-badge medium";

            const c = z.conditions;
            return `
                <div class="zone-risk-card">
                    <div class="zone-risk-header">
                        <span class="zone-risk-name">${z.zone_name}</span>
                        <span class="${badgeClass}" style="font-size:0.7rem; padding:3px 8px;">${z.risk_category} (${z.risk_score.toFixed(0)}%)</span>
                    </div>
                    <div class="zone-weather-pills">
                        <span>${c.central_pressure_hpa.toFixed(0)} hPa</span>
                        <span>${c.max_sustained_wind_kmh.toFixed(0)} km/h Wind</span>
                        <span>${c.sea_surface_temp_c.toFixed(1)}°C SST</span>
                        <span>${c.storm_forward_speed_kmh.toFixed(0)} km/h Speed</span>
                        <span>${c.coastal_distance_km.toFixed(0)} km Offshore</span>
                    </div>
                    <div style="font-size:0.75rem; color:var(--text-secondary); line-height:1.4;">
                        ${z.explanation}
                    </div>
                    <div style="font-size:0.68rem; color:var(--text-muted); display:flex; justify-content:space-between; margin-top:2px;">
                        <span>Coords: [${z.coordinates[0].toFixed(2)}, ${z.coordinates[1].toFixed(2)}] · ${z.basin}</span>
                        <span>Uncertainty: ${z.uncertainty_pct.toFixed(0)}%</span>
                    </div>
                </div>
            `;
        }).join("");
    } catch (err) {
        console.warn("Error fetching monitored cyclone zones:", err);
        container.innerHTML = '<div style="font-size:0.8rem; color:var(--hazard-cyclone);">Failed to load coastal sector assessments.</div>';
    }
}

/**
 * ==============================================================================
 * LIVE PUBLIC WEATHER INTEGRATION (OPEN-METEO 1-CLICK AUTO-FILL)
 * ==============================================================================
 */

/**
 * Initializes weather preset selectors, sync buttons, and map probe click listener.
 */
async function initWeatherAutoFill(mapController) {
    const selects = document.querySelectorAll(".weather-station-select");
    const syncBtns = document.querySelectorAll(".weather-sync-btn");

    try {
        const res = await fetch("/api/weather/presets");
        if (res.ok) {
            const data = await res.json();
            const presets = data.presets || [];

            selects.forEach(sel => {
                sel.innerHTML = '<option value="">Select Real-time Station...</option>' +
                    presets.map(p => `
                        <option value="${p.lat},${p.lon}">${p.name} (${p.region})</option>
                    `).join("");

                sel.addEventListener("change", async () => {
                    if (!sel.value) return;
                    const [lat, lon] = sel.value.split(",").map(Number);
                    await fetchAndApplyWeather(lat, lon, sel.closest(".weather-autofill-bar"));
                });
            });
        }
    } catch (err) {
        console.warn("Could not load weather presets:", err);
    }

    syncBtns.forEach(btn => {
        btn.addEventListener("click", async () => {
            const bar = btn.closest(".weather-autofill-bar");
            const sel = bar ? bar.querySelector(".weather-station-select") : null;
            let lat = 22.24;
            let lon = 68.96;
            if (sel && sel.value) {
                [lat, lon] = sel.value.split(",").map(Number);
            }
            btn.classList.add("loading");
            await fetchAndApplyWeather(lat, lon, bar);
            setTimeout(() => btn.classList.remove("loading"), 500);
        });
    });

    // Add interactive click listener on the Leaflet map to probe weather anywhere
    if (mapController && mapController.map) {
        const map = mapController.map;
        map.on("click", (e) => {
            const lat = e.latlng.lat;
            const lon = e.latlng.lng;

            const popup = L.popup()
                .setLatLng([lat, lon])
                .setContent(`
                    <div class="popup-box" style="min-width: 220px;">
                        <div class="popup-title">📍 Live Meteorological Probe</div>
                        <div class="popup-desc" style="margin-bottom: 6px;">Query real-time atmospheric data for this point.</div>
                        <div class="popup-meta-item"><strong>GPS:</strong> [${lat.toFixed(3)}, ${lon.toFixed(3)}]</div>
                        <button id="map-probe-weather-btn" class="btn btn-outline" style="margin-top: 8px; width: 100%; font-size: 0.75rem; padding: 5px; color: #38bdf8; border-color: #38bdf8; cursor: pointer;">
                            ⚡ Auto-Fill Simulators With Live Weather
                        </button>
                    </div>
                `)
                .openOn(map);

            setTimeout(() => {
                const probeBtn = document.getElementById("map-probe-weather-btn");
                if (probeBtn) {
                    probeBtn.addEventListener("click", async () => {
                        probeBtn.textContent = "Fetching Live Weather...";
                        await fetchAndApplyWeather(lat, lon, null);
                        map.closePopup();
                    });
                }
            }, 50);
        });
    }
}

/**
 * Fetches live weather for coordinates and applies them to whatever simulator sliders exist on the page.
 */
async function fetchAndApplyWeather(lat, lon, barEl) {
    try {
        const res = await fetch(`/api/weather/live?lat=${lat}&lon=${lon}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const inputs = data.simulator_inputs || {};

        // 1. Fire Simulator Sliders
        const sTemp = document.getElementById("slider-temp");
        const sHum = document.getElementById("slider-humidity");
        const sWind = document.getElementById("slider-wind");
        const sRain = document.getElementById("slider-rain");
        const sNdvi = document.getElementById("slider-ndvi");

        if (sTemp && inputs.fire) {
            sTemp.value = inputs.fire.temperature_c;
            sTemp.dispatchEvent(new Event("input"));
            if (sHum) { sHum.value = inputs.fire.relative_humidity_pct; sHum.dispatchEvent(new Event("input")); }
            if (sWind) { sWind.value = inputs.fire.wind_speed_kmh; sWind.dispatchEvent(new Event("input")); }
            if (sRain) { sRain.value = inputs.fire.rainfall_mm; sRain.dispatchEvent(new Event("input")); }
            if (sNdvi) { sNdvi.value = inputs.fire.vegetation_ndvi; sNdvi.dispatchEvent(new Event("input")); }
        }

        // 2. Cyclone Simulator Sliders
        const cPress = document.getElementById("cyclone-slider-pressure");
        const cWind = document.getElementById("cyclone-slider-wind");
        const cSst = document.getElementById("cyclone-slider-sst");
        const cSpeed = document.getElementById("cyclone-slider-speed");
        const cDist = document.getElementById("cyclone-slider-dist");

        if (cPress && inputs.cyclone) {
            cPress.value = inputs.cyclone.central_pressure_hpa;
            cPress.dispatchEvent(new Event("input"));
            if (cWind) { cWind.value = inputs.cyclone.max_sustained_wind_kmh; cWind.dispatchEvent(new Event("input")); }
            if (cSst) { cSst.value = inputs.cyclone.sea_surface_temp_c; cSst.dispatchEvent(new Event("input")); }
            if (cSpeed) { cSpeed.value = inputs.cyclone.storm_forward_speed_kmh; cSpeed.dispatchEvent(new Event("input")); }
            if (cDist) { cDist.value = inputs.cyclone.coastal_distance_km; cDist.dispatchEvent(new Event("input")); }
        }

        // 3. Flood Simulator Sliders
        const fRain = document.getElementById("flood-slider-rain");
        const fSoil = document.getElementById("flood-slider-soil");
        const fRadar = document.getElementById("flood-slider-radar");

        if (fRain && inputs.flood) {
            fRain.value = inputs.flood.precipitation_24h_mm;
            fRain.dispatchEvent(new Event("input"));
            if (fSoil) { fSoil.value = inputs.flood.soil_moisture_pct; fSoil.dispatchEvent(new Event("input")); }
            if (fRadar) { fRadar.value = inputs.flood.radar_backscatter_drop_db; fRadar.dispatchEvent(new Event("input")); }
        }

        // 4. Drought Simulator Sliders
        const dTemp = document.getElementById("drought-slider-temp");
        const dDef = document.getElementById("drought-slider-deficit");

        if (dTemp && inputs.drought) {
            dTemp.value = inputs.drought.soil_temperature_c;
            dTemp.dispatchEvent(new Event("input"));
            if (dDef) { dDef.value = inputs.drought.precipitation_deficit_pct; dDef.dispatchEvent(new Event("input")); }
        }

        // Visual flash highlight on auto-fill bar to confirm real-time data ingestion
        if (barEl) {
            barEl.style.transition = "background 0.3s ease, border-color 0.3s ease";
            barEl.style.background = "rgba(16, 185, 129, 0.18)";
            barEl.style.borderColor = "#10b981";
            setTimeout(() => {
                barEl.style.background = "rgba(56, 189, 248, 0.08)";
                barEl.style.borderColor = "rgba(56, 189, 248, 0.25)";
            }, 1200);
        }
    } catch (err) {
        console.error("Error applying live weather:", err);
    }
}



/* ==============================================================================
   EMERGENCY RESPONSE MODULE — Frontend Functions
   ============================================================================== */

// ── Global response module state ──
let _respMapController = null;
let _respOrgMarkers = [];
let _respIncidentMarkers = [];
let _respDistanceLines = [];
let _respAutoRefreshTimer = null;

function initResponseModule(mapController) {
    _respMapController = mapController;
    fetchResponseDashboardStats();
    fetchEmergencyRequests();
    loadIncidentSelector();
    loadOrgCategoryFilter();
    loadOrgDirectory();

    // Bind filter events
    const statusFilter = document.getElementById("resp-filter-status");
    const disasterFilter = document.getElementById("resp-filter-disaster");
    const priorityFilter = document.getElementById("resp-filter-priority");
    const refreshTableBtn = document.getElementById("resp-refresh-table-btn");
    const refreshMapBtn = document.getElementById("resp-refresh-map-btn");
    const incidentSelect = document.getElementById("resp-incident-select");
    const orgCategoryFilter = document.getElementById("resp-org-category-filter");

    if (statusFilter) statusFilter.addEventListener("change", () => fetchEmergencyRequests());
    if (disasterFilter) disasterFilter.addEventListener("change", () => fetchEmergencyRequests());
    if (priorityFilter) priorityFilter.addEventListener("change", () => fetchEmergencyRequests());
    if (refreshTableBtn) refreshTableBtn.addEventListener("click", () => {
        fetchResponseDashboardStats();
        fetchEmergencyRequests();
    });
    if (refreshMapBtn) refreshMapBtn.addEventListener("click", () => {
        const sel = document.getElementById("resp-incident-select");
        if (sel && sel.value) fetchNearbyOrganizations(sel.value);
    });
    if (incidentSelect) incidentSelect.addEventListener("change", (e) => {
        if (e.target.value) {
            fetchNearbyOrganizations(e.target.value);
        } else {
            clearNearbyOrgs();
            loadOrgDirectory();
        }
    });
    if (orgCategoryFilter) orgCategoryFilter.addEventListener("change", () => loadOrgDirectory());

    // History modal close buttons
    const histCloseBtn = document.getElementById("resp-history-close-btn");
    const histDismissBtn = document.getElementById("resp-history-dismiss-btn");
    if (histCloseBtn) histCloseBtn.addEventListener("click", () => {
        document.getElementById("resp-history-modal").style.display = "none";
    });
    if (histDismissBtn) histDismissBtn.addEventListener("click", () => {
        document.getElementById("resp-history-modal").style.display = "none";
    });

    // Auto-refresh every 15 seconds
    _respAutoRefreshTimer = setInterval(() => {
        fetchResponseDashboardStats();
        fetchEmergencyRequests();
    }, 15000);
}

function fetchResponseDashboardStats() {
    fetch("/api/response/stats")
        .then(r => r.json())
        .then(data => {
            if (data.status !== "success") return;
            const s = data.stats || data;
            const setTxt = (id, val) => {
                const el = document.getElementById(id);
                if (el) el.textContent = val;
            };
            setTxt("resp-stat-total", s.total_contacted ?? s.total_requests ?? 0);
            setTxt("resp-stat-pending", s.pending_responses ?? s.pending ?? 0);
            setTxt("resp-stat-dispatched", s.teams_dispatched ?? s.dispatched ?? 0);
            setTxt("resp-stat-completed", s.completed_operations ?? s.completed ?? 0);
            setTxt("resp-stat-acknowledged-sub", "Acknowledged: " + (s.acknowledged_requests ?? s.acknowledged ?? 0));
            setTxt("resp-stat-inprogress-sub", "Assisting: " + (s.assistance_in_progress ?? 0));
            setTxt("resp-stat-rejected-sub", "Rejected: " + (s.rejected_requests ?? s.rejected ?? 0));
        })
        .catch(err => console.error("Stats fetch error:", err));
}

function fetchEmergencyRequests() {
    const params = new URLSearchParams();
    const statusVal = document.getElementById("resp-filter-status");
    const disasterVal = document.getElementById("resp-filter-disaster");
    const priorityVal = document.getElementById("resp-filter-priority");

    if (statusVal && statusVal.value) params.append("status", statusVal.value);
    if (disasterVal && disasterVal.value) params.append("disaster_type", disasterVal.value);
    if (priorityVal && priorityVal.value) params.append("priority", priorityVal.value);

    fetch("/api/response/requests?" + params.toString())
        .then(r => r.json())
        .then(data => {
            const tbody = document.getElementById("response-tracking-table-body");
            if (!tbody) return;
            if (data.status !== "success" || !data.requests || data.requests.length === 0) {
                tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:24px; color:var(--text-muted);">No emergency requests found.</td></tr>';
                return;
            }
            tbody.innerHTML = data.requests.map(req => {
                const statusClass = getStatusCssClass(req.current_status);
                const priorityBadge = getPriorityBadgeHtml(req.priority_level);
                const reqTime = req.created_at ? new Date(req.created_at).toLocaleString() : "--";
                const updatedTime = req.updated_at ? new Date(req.updated_at).toLocaleString() : "--";
                const distance = req.distance_km != null ? req.distance_km.toFixed(1) + " km" : "--";
                return `<tr>
                    <td style="font-family:var(--font-mono); font-size:0.78rem;">REQ-${String(req.id).padStart(3,'0')}</td>
                    <td>${req.incident_uid || ("INC-" + req.incident_id)}</td>
                    <td>${priorityBadge} ${req.disaster_type || "--"}</td>
                    <td style="font-size:0.82rem;">${req.org_name || "--"}</td>
                    <td style="font-family:var(--font-mono); font-size:0.78rem;">${distance}</td>
                    <td style="font-size:0.75rem;">${reqTime}</td>
                    <td><span class="resp-status-badge ${statusClass}">${req.current_status}</span></td>
                    <td style="font-size:0.75rem;">${updatedTime}</td>
                    <td>
                        <button class="resp-action-btn" onclick="showRequestHistory(${req.id})" title="View audit trail">History</button>
                    </td>
                </tr>`;
            }).join("");
        })
        .catch(err => {
            console.error("Requests fetch error:", err);
        });
}

function getStatusCssClass(status) {
    if (!status) return "";
    const map = {
        "Pending": "status-pending",
        "Acknowledged": "status-acknowledged",
        "Dispatched": "status-dispatched",
        "On The Way": "status-on-the-way",
        "Arrived": "status-arrived",
        "Assistance In Progress": "status-assistance-in-progress",
        "Completed": "status-completed",
        "Rejected": "status-rejected",
        "Cancelled": "status-cancelled"
    };
    return map[status] || "";
}

function getPriorityBadgeHtml(priority) {
    if (!priority) return "";
    const colors = {
        "CRITICAL": "background:rgba(239,68,68,0.2);color:#f87171",
        "HIGH": "background:rgba(245,158,11,0.2);color:#fbbf24",
        "MEDIUM": "background:rgba(59,130,246,0.2);color:#60a5fa",
        "LOW": "background:rgba(100,116,139,0.2);color:#94a3b8"
    };
    return `<span class="badge" style="${colors[priority] || ""};font-size:0.65rem;padding:2px 6px;">${priority}</span>`;
}

function loadIncidentSelector() {
    fetch("/api/incidents")
        .then(r => r.json())
        .then(data => {
            const sel = document.getElementById("resp-incident-select");
            if (!sel) return;
            const incidents = data.incidents || data.data || [];
            incidents.forEach(inc => {
                const opt = document.createElement("option");
                opt.value = inc.id;
                opt.textContent = (inc.incident_uid || ("INC-" + inc.id)) + " — " + (inc.disaster_type || "") + " (" + (inc.priority_level || "") + ")";
                sel.appendChild(opt);
            });
        })
        .catch(err => console.error("Incident selector error:", err));
}

function loadOrgCategoryFilter() {
    fetch("/api/response/categories")
        .then(r => r.json())
        .then(data => {
            const sel = document.getElementById("resp-org-category-filter");
            if (!sel || !data.categories) return;
            data.categories.forEach(cat => {
                const opt = document.createElement("option");
                opt.value = cat;
                opt.textContent = cat.replace(/_/g, " ");
                sel.appendChild(opt);
            });
        })
        .catch(err => console.error("Category filter error:", err));
}

function loadOrgDirectory() {
    const catFilter = document.getElementById("resp-org-category-filter");
    const params = new URLSearchParams();
    if (catFilter && catFilter.value) params.append("category", catFilter.value);

    fetch("/api/response/organizations?" + params.toString())
        .then(r => r.json())
        .then(data => {
            const container = document.getElementById("resp-org-directory-container");
            if (!container) return;
            if (data.status !== "success" || !data.organizations || data.organizations.length === 0) {
                container.innerHTML = '<div style="padding:16px; color:var(--text-muted); font-size:0.85rem;">No organizations found.</div>';
                return;
            }
            container.innerHTML = data.organizations.map(org => {
                const avail = org.availability_status === "AVAILABLE"
                    ? '<span style="color:#10b981;font-size:0.7rem;">● Available</span>'
                    : '<span style="color:#f59e0b;font-size:0.7rem;">● ' + (org.availability_status || "Unknown") + '</span>';
                return `<div class="resp-org-card">
                    <div class="resp-org-info">
                        <div class="resp-org-name">${org.name}</div>
                        <div class="resp-org-category">${(org.category || "").replace(/_/g, " ")}</div>
                        <div class="resp-org-meta">
                            ${avail}
                            <span>${org.city || ""}, ${org.state || ""}</span>
                            ${org.emergency_hotline ? '<span>📞 ' + org.emergency_hotline + '</span>' : ''}
                        </div>
                    </div>
                    ${org.is_verified ? '<span class="badge badge-success" style="font-size:0.6rem;">VERIFIED</span>' : '<span class="badge" style="font-size:0.6rem;background:rgba(100,116,139,0.2);color:#94a3b8;">DEMO</span>'}
                </div>`;
            }).join("");
        })
        .catch(err => console.error("Org directory error:", err));
}

function fetchNearbyOrganizations(incidentId) {
    fetch("/api/response/nearby?incident_id=" + incidentId + "&limit=20")
        .then(r => r.json())
        .then(data => {
            const container = document.getElementById("resp-nearby-orgs-container");
            if (!container) return;

            if (data.status !== "success" || !data.organizations || data.organizations.length === 0) {
                container.innerHTML = '<div style="padding:16px; color:var(--text-muted); font-size:0.85rem;">No nearby organizations found for this incident.</div>';
                return;
            }

            // Show organizations on map
            renderOrgsOnMap(data.organizations, data.incident);

            container.innerHTML = data.organizations.map(org => {
                const tierClass = org.proximity_tier === "IMMEDIATE_RESPONSE" ? "tier-immediate"
                    : org.proximity_tier === "REGIONAL_SUPPORT" ? "tier-regional" : "tier-strategic";
                return `<div class="resp-org-card">
                    <div class="resp-org-info">
                        <div class="resp-org-name">${org.name}</div>
                        <div class="resp-org-category">${(org.category || "").replace(/_/g, " ")}</div>
                        <div class="resp-org-meta">
                            <span>${org.city || ""}, ${org.state || ""}</span>
                            ${org.emergency_hotline ? '<span>📞 ' + org.emergency_hotline + '</span>' : ''}
                        </div>
                    </div>
                    <div class="resp-org-actions">
                        <div class="resp-org-distance ${tierClass}">${org.distance_km.toFixed(1)} km</div>
                        <button class="btn-dispatch" onclick="dispatchRequest(${incidentId}, ${org.id})">
                            ⚡ Dispatch
                        </button>
                    </div>
                </div>`;
            }).join("");
        })
        .catch(err => console.error("Nearby orgs error:", err));
}

function renderOrgsOnMap(organizations, incident) {
    if (!_respMapController || !_respMapController.map) return;
    const map = _respMapController.map;

    // Clear previous markers
    _respOrgMarkers.forEach(m => map.removeLayer(m));
    _respIncidentMarkers.forEach(m => map.removeLayer(m));
    _respDistanceLines.forEach(l => map.removeLayer(l));
    _respOrgMarkers = [];
    _respIncidentMarkers = [];
    _respDistanceLines = [];

    // Add incident marker
    if (incident && incident.latitude && incident.longitude) {
        const incMarker = L.circleMarker([incident.latitude, incident.longitude], {
            radius: 10,
            color: "#ef4444",
            fillColor: "#ef4444",
            fillOpacity: 0.7,
            weight: 2
        }).addTo(map).bindPopup(
            `<b>Incident: ${incident.incident_uid || "INC-" + incident.id}</b><br>` +
            `Type: ${incident.disaster_type || "--"}<br>` +
            `Priority: ${incident.priority_level || "--"}`
        );
        _respIncidentMarkers.push(incMarker);
    }

    // Add org markers
    organizations.forEach(org => {
        if (!org.latitude || !org.longitude) return;
        const tierColor = org.proximity_tier === "IMMEDIATE_RESPONSE" ? "#10b981"
            : org.proximity_tier === "REGIONAL_SUPPORT" ? "#f59e0b" : "#ef4444";

        const orgMarker = L.circleMarker([org.latitude, org.longitude], {
            radius: 7,
            color: tierColor,
            fillColor: tierColor,
            fillOpacity: 0.6,
            weight: 2
        }).addTo(map).bindPopup(
            `<b>${org.name}</b><br>` +
            `Category: ${(org.category || "").replace(/_/g, " ")}<br>` +
            `Distance: ${org.distance_km.toFixed(1)} km<br>` +
            `Tier: ${(org.proximity_tier || "").replace(/_/g, " ")}<br>` +
            `${org.emergency_hotline ? "Hotline: " + org.emergency_hotline : ""}`
        );
        _respOrgMarkers.push(orgMarker);

        // Draw distance line from incident to org
        if (incident && incident.latitude && incident.longitude) {
            const line = L.polyline(
                [[incident.latitude, incident.longitude], [org.latitude, org.longitude]],
                { color: tierColor, weight: 1, opacity: 0.4, dashArray: "5, 8" }
            ).addTo(map);
            _respDistanceLines.push(line);
        }
    });

    // Fit bounds to show all markers
    const allCoords = [];
    if (incident && incident.latitude) allCoords.push([incident.latitude, incident.longitude]);
    organizations.forEach(o => { if (o.latitude) allCoords.push([o.latitude, o.longitude]); });
    if (allCoords.length > 0) {
        map.fitBounds(L.latLngBounds(allCoords).pad(0.15));
    }
}

function clearNearbyOrgs() {
    if (_respMapController && _respMapController.map) {
        _respOrgMarkers.forEach(m => _respMapController.map.removeLayer(m));
        _respIncidentMarkers.forEach(m => _respMapController.map.removeLayer(m));
        _respDistanceLines.forEach(l => _respMapController.map.removeLayer(l));
    }
    _respOrgMarkers = [];
    _respIncidentMarkers = [];
    _respDistanceLines = [];
    const container = document.getElementById("resp-nearby-orgs-container");
    if (container) container.innerHTML = '<div style="padding:16px; color:var(--text-muted); font-size:0.85rem;">Select an incident to view nearby organizations.</div>';
}

function dispatchRequest(incidentId, orgId) {
    if (!confirm("Send an emergency dispatch request to this organization?")) return;

    fetch("/api/response/requests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            incident_id: incidentId,
            organization_id: orgId,
            requester_name: "Control Center Operator",
            requester_contact: "command@disaster-intel.local"
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === "success") {
            alert("Emergency request dispatched successfully! Request ID: " + data.request_id);
            fetchResponseDashboardStats();
            fetchEmergencyRequests();
        } else {
            alert("Dispatch failed: " + (data.message || "Unknown error"));
        }
    })
    .catch(err => {
        console.error("Dispatch error:", err);
        alert("Failed to dispatch request. Check console for details.");
    });
}

function showRequestHistory(requestId) {
    const modal = document.getElementById("resp-history-modal");
    const body = document.getElementById("resp-history-modal-body");
    const subtitle = document.getElementById("resp-history-modal-sub");

    if (!modal || !body) return;
    modal.style.display = "flex";
    body.innerHTML = '<div class="loading-spinner">Loading audit trail...</div>';
    if (subtitle) subtitle.textContent = "Request #REQ-" + String(requestId).padStart(3, "0");

    fetch("/api/response/requests/" + requestId + "/history")
        .then(r => r.json())
        .then(data => {
            if (data.status !== "success" || !data.history || data.history.length === 0) {
                body.innerHTML = '<div style="padding:16px; color:var(--text-muted);">No audit history available.</div>';
                return;
            }
            body.innerHTML = data.history.map(h => {
                const dotColor = getStatusDotColor(h.new_status);
                const ts = h.timestamp ? new Date(h.timestamp).toLocaleString() : "--";
                return `<div class="resp-history-item">
                    <div class="resp-history-dot" style="background:${dotColor};"></div>
                    <div class="resp-history-content">
                        <div><strong>${h.previous_status || "—"}</strong> → <strong>${h.new_status}</strong></div>
                        ${h.updated_by_name ? '<div style="font-size:0.75rem; color:var(--text-secondary);">By: ' + h.updated_by_name + '</div>' : ''}
                        ${h.remarks ? '<div style="font-size:0.75rem; color:var(--text-secondary); font-style:italic;">"' + h.remarks + '"</div>' : ''}
                        <div class="resp-history-time">${ts}</div>
                    </div>
                </div>`;
            }).join("");
        })
        .catch(err => {
            body.innerHTML = '<div style="padding:16px; color:#f87171;">Error loading history.</div>';
            console.error("History fetch error:", err);
        });
}

function getStatusDotColor(status) {
    const map = {
        "Pending": "#f59e0b",
        "Acknowledged": "#3b82f6",
        "Dispatched": "#8b5cf6",
        "On The Way": "#f97316",
        "Arrived": "#06b6d4",
        "Assistance In Progress": "#10b981",
        "Completed": "#10b981",
        "Rejected": "#ef4444",
        "Cancelled": "#64748b"
    };
    return map[status] || "#64748b";
}


/* ==============================================================================
   ORGANIZATION PORTAL — Frontend Functions
   ============================================================================== */

let _orgAuthToken = null;
let _orgUserId = null;
let _orgOrgId = null;
let _orgRefreshTimer = null;

function initOrgPortal() {
    // Check if already logged in (session)
    checkOrgSession();

    const loginForm = document.getElementById("org-login-form");
    if (loginForm) {
        loginForm.addEventListener("submit", handleOrgLogin);
    }

    const logoutBtn = document.getElementById("org-logout-btn");
    if (logoutBtn) logoutBtn.addEventListener("click", handleOrgLogout);

    const updateForm = document.getElementById("org-status-update-form");
    if (updateForm) updateForm.addEventListener("submit", handleOrgStatusUpdate);

    const cancelUpdateBtn = document.getElementById("org-update-cancel-btn");
    if (cancelUpdateBtn) cancelUpdateBtn.addEventListener("click", () => {
        document.getElementById("org-status-update-panel").style.display = "none";
    });
}

function checkOrgSession() {
    const savedToken = sessionStorage.getItem("org_auth_token");
    if (!savedToken) return;

    fetch("/api/response/auth/me", {
        headers: { "Authorization": "Bearer " + savedToken }
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === "success" && data.user) {
            _orgAuthToken = savedToken;
            _orgUserId = data.user.id;
            _orgOrgId = data.user.org_id;
            showOrgDashboard(data.user);
        }
    })
    .catch(() => {});
}

function handleOrgLogin(e) {
    e.preventDefault();
    const username = document.getElementById("org-login-username").value.trim();
    const password = document.getElementById("org-login-password").value;
    const errorDiv = document.getElementById("org-login-error");

    if (!username || !password) {
        errorDiv.textContent = "Please enter username and password.";
        errorDiv.style.display = "block";
        return;
    }

    fetch("/api/response/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === "success" && data.token) {
            _orgAuthToken = data.token;
            _orgUserId = data.user.id;
            _orgOrgId = data.user.org_id;
            sessionStorage.setItem("org_auth_token", data.token);
            errorDiv.style.display = "none";
            showOrgDashboard(data.user);
        } else {
            errorDiv.textContent = data.message || "Invalid credentials.";
            errorDiv.style.display = "block";
        }
    })
    .catch(err => {
        errorDiv.textContent = "Login failed. Check your connection.";
        errorDiv.style.display = "block";
        console.error("Login error:", err);
    });
}

function handleOrgLogout() {
    fetch("/api/response/auth/logout", {
        method: "POST",
        headers: _orgAuthToken ? { "Authorization": "Bearer " + _orgAuthToken } : {}
    }).catch(() => {});

    _orgAuthToken = null;
    _orgUserId = null;
    _orgOrgId = null;
    sessionStorage.removeItem("org_auth_token");
    if (_orgRefreshTimer) clearInterval(_orgRefreshTimer);

    document.getElementById("org-login-panel").style.display = "block";
    document.getElementById("org-dashboard-panel").style.display = "none";
}

function showOrgDashboard(user) {
    document.getElementById("org-login-panel").style.display = "none";
    document.getElementById("org-dashboard-panel").style.display = "block";

    const setTxt = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    setTxt("org-portal-user-name", user.full_name || user.username);
    setTxt("org-portal-org-name", user.org_name || ("Organization #" + user.org_id));
    setTxt("org-portal-role-badge", user.role || "RESPONDER");

    fetchOrgRequests();
    fetchOrgNotifications();
    fetchOrgStats();

    // Auto-refresh every 10 seconds
    _orgRefreshTimer = setInterval(() => {
        fetchOrgRequests();
        fetchOrgNotifications();
        fetchOrgStats();
    }, 10000);
}

function fetchOrgRequests() {
    if (!_orgOrgId) return;
    fetch("/api/response/requests?org_id=" + _orgOrgId)
        .then(r => r.json())
        .then(data => {
            const tbody = document.getElementById("org-requests-table-body");
            if (!tbody) return;
            if (data.status !== "success" || !data.requests || data.requests.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:24px;color:var(--text-muted);">No requests for your organization.</td></tr>';
                updateOrgStatCounters([]);
                return;
            }
            updateOrgStatCounters(data.requests);
            tbody.innerHTML = data.requests.map(req => {
                const statusClass = getStatusCssClass(req.current_status);
                const priorityBadge = getPriorityBadgeHtml(req.priority_level);
                const reqTime = req.created_at ? new Date(req.created_at).toLocaleString() : "--";
                const distance = req.distance_km != null ? req.distance_km.toFixed(1) + " km" : "--";
                let actionHtml = "";

                if (req.current_status === "Pending") {
                    actionHtml = `
                        <button class="resp-action-btn accept" onclick="orgActionRequest(${req.id}, 'ACCEPT')">✓ Accept</button>
                        <button class="resp-action-btn reject" onclick="orgActionRequest(${req.id}, 'REJECT')">✗ Reject</button>
                    `;
                } else if (["Acknowledged", "Dispatched", "On The Way", "Arrived", "Assistance In Progress"].includes(req.current_status)) {
                    actionHtml = `<button class="resp-action-btn" onclick="showOrgStatusUpdate(${req.id}, '${req.current_status}')">Update Status</button>`;
                } else {
                    actionHtml = '<span style="font-size:0.7rem;color:var(--text-muted);">Final</span>';
                }

                return `<tr>
                    <td style="font-family:var(--font-mono);font-size:0.78rem;">REQ-${String(req.id).padStart(3,'0')}</td>
                    <td>${req.incident_uid || ("INC-" + req.incident_id)}</td>
                    <td>${req.disaster_type || "--"}</td>
                    <td>${priorityBadge}</td>
                    <td style="font-family:var(--font-mono);font-size:0.78rem;">${distance}</td>
                    <td><span class="resp-status-badge ${statusClass}">${req.current_status}</span></td>
                    <td style="font-size:0.75rem;">${reqTime}</td>
                    <td style="white-space:nowrap;">${actionHtml}</td>
                </tr>`;
            }).join("");
        })
        .catch(err => console.error("Org requests error:", err));
}

function updateOrgStatCounters(requests) {
    const incoming = requests.filter(r => r.current_status === "Pending").length;
    const active = requests.filter(r => ["Acknowledged", "Dispatched", "On The Way", "Arrived", "Assistance In Progress"].includes(r.current_status)).length;
    const completed = requests.filter(r => r.current_status === "Completed").length;

    const setTxt = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    setTxt("org-stat-incoming", incoming);
    setTxt("org-stat-active", active);
    setTxt("org-stat-completed", completed);
}

function fetchOrgNotifications() {
    if (!_orgAuthToken) return;
    fetch("/api/response/notifications", {
        headers: { "Authorization": "Bearer " + _orgAuthToken }
    })
    .then(r => r.json())
    .then(data => {
        const container = document.getElementById("org-notifications-container");
        const badge = document.getElementById("org-notif-count-badge");
        if (!container) return;

        if (data.status !== "success" || !data.notifications || data.notifications.length === 0) {
            container.innerHTML = '<div style="padding:16px;color:var(--text-muted);font-size:0.85rem;">No notifications.</div>';
            if (badge) badge.textContent = "0 new";
            return;
        }

        const unreadCount = data.notifications.filter(n => !n.is_read).length;
        if (badge) badge.textContent = unreadCount + " new";

        container.innerHTML = data.notifications.slice(0, 20).map(n => {
            const ts = n.created_at ? new Date(n.created_at).toLocaleString() : "--";
            return `<div class="resp-notif-item ${n.is_read ? '' : 'unread'}">
                <div class="resp-notif-title">${n.title || "Notification"}</div>
                <div class="resp-notif-message">${n.message || ""}</div>
                <div class="resp-notif-time">${ts}</div>
            </div>`;
        }).join("");
    })
    .catch(err => console.error("Notifications error:", err));
}

function fetchOrgStats() {
    // Uses the same stats endpoint for KPIs — org-specific stats come from the requests
}

function orgActionRequest(requestId, action) {
    const verb = action === "ACCEPT" ? "accept" : "reject";
    if (!confirm("Are you sure you want to " + verb + " this request?")) return;

    fetch("/api/response/requests/" + requestId + "/action", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + _orgAuthToken
        },
        body: JSON.stringify({ action: action })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === "success") {
            fetchOrgRequests();
            fetchOrgNotifications();
        } else {
            alert("Action failed: " + (data.message || "Unknown error"));
        }
    })
    .catch(err => {
        console.error("Action error:", err);
        alert("Failed to " + verb + " request.");
    });
}

function showOrgStatusUpdate(requestId, currentStatus) {
    const panel = document.getElementById("org-status-update-panel");
    const reqIdField = document.getElementById("org-update-request-id");
    if (!panel || !reqIdField) return;

    reqIdField.value = requestId;
    panel.style.display = "block";
    panel.scrollIntoView({ behavior: "smooth", block: "center" });

    // Set the status dropdown to the next logical status
    const statusSelect = document.getElementById("org-update-status");
    if (statusSelect) {
        const nextMap = {
            "Acknowledged": "Dispatched",
            "Dispatched": "On The Way",
            "On The Way": "Arrived",
            "Arrived": "Assistance In Progress",
            "Assistance In Progress": "Completed"
        };
        statusSelect.value = nextMap[currentStatus] || "Dispatched";
    }
}

function handleOrgStatusUpdate(e) {
    e.preventDefault();
    const requestId = document.getElementById("org-update-request-id").value;
    const newStatus = document.getElementById("org-update-status").value;
    const remarks = document.getElementById("org-update-remarks").value.trim();

    if (!requestId || !newStatus) return;

    fetch("/api/response/requests/" + requestId + "/status", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + _orgAuthToken
        },
        body: JSON.stringify({
            new_status: newStatus,
            remarks: remarks || undefined
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === "success") {
            document.getElementById("org-status-update-panel").style.display = "none";
            document.getElementById("org-update-remarks").value = "";
            fetchOrgRequests();
        } else {
            alert("Status update failed: " + (data.message || "Unknown error"));
        }
    })
    .catch(err => {
        console.error("Status update error:", err);
        alert("Failed to update status.");
    });
}


/* ==============================================================================
   PHASE 4: SMART EVACUATION & SAFE ROUTE PLANNER — Frontend Functions
   ============================================================================== */

let _evacMapController = null;
let _evacCurrentIncident = null;
let _evacNearbyShelters = [];
let _evacNearbyHospitals = [];
let _evacSelectedDestination = null;
let _evacPrimaryPolyline = null;
let _evacAltPolyline = null;
let _evacOriginMarker = null;
let _evacDestMarker = null;
let _evacHazardLayerGroup = null;
let _evacShowAlternative = false;
let _evacCurrentCalculatedRoutes = null;

function initEvacuationModule(mapController) {
    _evacMapController = mapController;
    if (_evacMapController && _evacMapController.map) {
        _evacHazardLayerGroup = L.layerGroup().addTo(_evacMapController.map);
    }

    fetchEvacuationStats();
    loadEvacuationIncidents();
    loadEvacuationSheltersTable();
    loadEvacuationHazardLayers();

    // Event Bindings
    const incSelect = document.getElementById("evac-incident-select");
    if (incSelect) {
        incSelect.addEventListener("change", (e) => {
            const incId = e.target.value;
            if (incId) {
                handleEvacuationIncidentSelected(incId);
            } else {
                clearEvacuationRoutes();
            }
        });
    }

    const tabShelters = document.getElementById("evac-tab-shelters");
    const tabHospitals = document.getElementById("evac-tab-hospitals");
    if (tabShelters && tabHospitals) {
        tabShelters.addEventListener("click", () => {
            tabShelters.classList.add("active");
            tabShelters.style.background = "rgba(56, 189, 248, 0.15)";
            tabShelters.style.borderColor = "#38bdf8";
            tabShelters.style.color = "#38bdf8";

            tabHospitals.classList.remove("active");
            tabHospitals.style.background = "transparent";
            tabHospitals.style.borderColor = "var(--border-subtle)";
            tabHospitals.style.color = "var(--text-secondary)";
            renderEvacuationDestinationsList("SHELTERS");
        });

        tabHospitals.addEventListener("click", () => {
            tabHospitals.classList.add("active");
            tabHospitals.style.background = "rgba(6, 182, 212, 0.15)";
            tabHospitals.style.borderColor = "#06b6d4";
            tabHospitals.style.color = "#06b6d4";

            tabShelters.classList.remove("active");
            tabShelters.style.background = "transparent";
            tabShelters.style.borderColor = "var(--border-subtle)";
            tabShelters.style.color = "var(--text-secondary)";
            renderEvacuationDestinationsList("HOSPITALS");
        });
    }

    const toggleAltBtn = document.getElementById("evac-toggle-alt-btn");
    if (toggleAltBtn) {
        toggleAltBtn.addEventListener("click", toggleAlternativeEvacuationRoute);
    }

    const refreshHazardsBtn = document.getElementById("evac-refresh-hazards-btn");
    if (refreshHazardsBtn) {
        refreshHazardsBtn.addEventListener("click", () => {
            loadEvacuationHazardLayers();
            if (_evacCurrentIncident && _evacSelectedDestination) {
                requestEvacuationRouteCalculation(
                    _evacCurrentIncident.centroid_lat, _evacCurrentIncident.centroid_lon,
                    _evacSelectedDestination.latitude, _evacSelectedDestination.longitude,
                    _evacCurrentIncident.id
                );
            }
        });
    }

    // Shelter Occupancy Modal Events
    const modalCloseBtn = document.getElementById("evac-modal-close-btn");
    const modalCancelBtn = document.getElementById("evac-modal-cancel-btn");
    const occForm = document.getElementById("evac-occupancy-form");
    if (modalCloseBtn) modalCloseBtn.addEventListener("click", closeShelterOccupancyModal);
    if (modalCancelBtn) modalCancelBtn.addEventListener("click", closeShelterOccupancyModal);
    if (occForm) occForm.addEventListener("submit", handleShelterOccupancySubmit);
}

function fetchEvacuationStats() {
    fetch("/api/evacuation/stats")
        .then(r => r.json())
        .then(data => {
            if (data.status !== "success") return;
            const setTxt = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
            setTxt("evac-stat-shelters", data.total_shelters || 0);
            setTxt("evac-stat-capacity", (data.available_capacity || 0).toLocaleString() + " beds");
            setTxt("evac-stat-occ-rate", "Occupancy rate: " + (data.occupancy_rate_pct || 0) + "%");
            setTxt("evac-stat-total-cap", "Total capacity: " + (data.total_capacity || 0).toLocaleString() + " beds");
            setTxt("evac-stat-hospitals", data.operating_hospitals || 0);
            setTxt("evac-stat-beds", "Available triage beds: " + (data.available_beds || 0));
            setTxt("evac-stat-hazards", data.active_road_closures || 0);
        })
        .catch(err => console.error("Error fetching evacuation stats:", err));
}

function loadEvacuationIncidents() {
    fetch("/api/incidents")
        .then(r => r.json())
        .then(data => {
            const sel = document.getElementById("evac-incident-select");
            if (!sel) return;
            const incidents = data.incidents || data.data || [];
            sel.innerHTML = '<option value="">Choose an active disaster incident...</option>';
            incidents.forEach(inc => {
                const opt = document.createElement("option");
                opt.value = inc.id;
                opt.textContent = `${inc.incident_uid || ("INC-" + inc.id)} — ${inc.hazard_type} (${inc.priority_level}) ${inc.title || ''}`;
                sel.appendChild(opt);
            });
            // Auto-select first incident if available
            if (incidents.length > 0) {
                sel.value = incidents[0].id;
                handleEvacuationIncidentSelected(incidents[0].id);
            }
        })
        .catch(err => console.error("Error loading incidents:", err));
}

function handleEvacuationIncidentSelected(incidentId) {
    fetch("/api/evacuation/nearby?incident_id=" + incidentId + "&limit=12")
        .then(r => r.json())
        .then(data => {
            if (data.status !== "success") return;
            _evacCurrentIncident = data.incident;
            _evacNearbyShelters = data.shelters || [];
            _evacNearbyHospitals = data.hospitals || [];

            // Update Origin Box
            const coordsEl = document.getElementById("evac-origin-coords");
            const titleEl = document.getElementById("evac-origin-title");
            const badgeEl = document.getElementById("evac-origin-hazard-badge");
            const sCountEl = document.getElementById("evac-shelters-count");
            const hCountEl = document.getElementById("evac-hospitals-count");

            if (coordsEl) coordsEl.textContent = `Lat: ${_evacCurrentIncident.centroid_lat.toFixed(4)}, Lon: ${_evacCurrentIncident.centroid_lon.toFixed(4)}`;
            if (titleEl) titleEl.textContent = `${_evacCurrentIncident.title} (${_evacCurrentIncident.hazard_type})`;
            if (badgeEl) {
                badgeEl.textContent = _evacCurrentIncident.hazard_type + " • " + _evacCurrentIncident.priority_level;
                badgeEl.style.background = "rgba(239, 68, 68, 0.25)";
                badgeEl.style.color = "#f87171";
            }
            if (sCountEl) sCountEl.textContent = _evacNearbyShelters.length;
            if (hCountEl) hCountEl.textContent = _evacNearbyHospitals.length;

            renderEvacuationDestinationsList("SHELTERS");

            // Auto-select nearest shelter and compute route
            if (_evacNearbyShelters.length > 0) {
                selectEvacuationDestination(_evacNearbyShelters[0]);
            }
        })
        .catch(err => console.error("Error fetching nearby destinations:", err));
}

function renderEvacuationDestinationsList(type) {
    const container = document.getElementById("evac-destinations-container");
    if (!container) return;

    const list = (type === "HOSPITALS") ? _evacNearbyHospitals : _evacNearbyShelters;
    if (!list || list.length === 0) {
        container.innerHTML = `<div style="padding:16px; text-align:center; color:var(--text-muted); font-size:0.8rem;">No nearby ${type.toLowerCase()} found within proximity radius.</div>`;
        return;
    }

    container.innerHTML = list.map((item, idx) => {
        const isShelter = (type !== "HOSPITALS");
        const isSelected = _evacSelectedDestination && _evacSelectedDestination.id === item.id && _evacSelectedDestination.destination_type === item.destination_type;
        const occPct = isShelter ? (item.occupancy_pct || 0) : null;
        const occClass = occPct > 85 ? "full" : occPct > 60 ? "mid" : "low";

        return `
            <div class="evac-dest-card ${isSelected ? 'selected' : ''}" onclick="onDestinationCardClick('${type}', ${idx})">
                <div class="evac-dest-header">
                    <span class="evac-dest-name">${item.name}</span>
                    <span class="evac-dest-dist">${item.distance_km.toFixed(1)} km</span>
                </div>
                <div class="evac-dest-meta">
                    <span>${item.city || item.address || ''}</span>
                    <span>~${item.estimated_drive_minutes} min convoy</span>
                </div>
                ${isShelter ? `
                    <div style="display:flex; justify-content:space-between; font-size:0.7rem; color:var(--text-secondary); margin-top:4px;">
                        <span>Available: <strong>${item.available_capacity} / ${item.capacity}</strong></span>
                        <span>${occPct}% full</span>
                    </div>
                    <div class="evac-occ-track">
                        <div class="evac-occ-fill ${occClass}" style="width: ${Math.min(100, occPct)}%;"></div>
                    </div>
                ` : `
                    <div style="font-size:0.7rem; color:#06b6d4; margin-top:4px;">
                        Triage Beds: <strong>${item.available_beds || '--'}</strong> • Hotline: ${item.emergency_hotline || '108'}
                    </div>
                `}
            </div>
        `;
    }).join("");
}

function onDestinationCardClick(type, index) {
    const list = (type === "HOSPITALS") ? _evacNearbyHospitals : _evacNearbyShelters;
    if (list && list[index]) {
        selectEvacuationDestination(list[index]);
    }
}

function selectEvacuationDestination(destination) {
    _evacSelectedDestination = destination;

    // Highlight selected card in DOM
    const cards = document.querySelectorAll(".evac-dest-card");
    cards.forEach(c => c.classList.remove("selected"));

    // Update Right Panel Target Details
    const nameEl = document.getElementById("evac-target-name");
    const addrEl = document.getElementById("evac-target-address");
    const capEl = document.getElementById("evac-target-capacity");

    if (nameEl) nameEl.textContent = destination.name;
    if (addrEl) addrEl.textContent = `${destination.address || ''}, ${destination.city || ''} (📞 ${destination.contact_phone || destination.phone || '108'})`;
    if (capEl) {
        if (destination.destination_type === "SHELTER") {
            capEl.textContent = `Available Capacity: ${destination.available_capacity} / ${destination.capacity} beds (${destination.operating_status || 'OPEN'})`;
        } else {
            capEl.textContent = `Available Triage Beds: ${destination.available_beds} (Trauma Level: ${destination.trauma_care_level || '1'})`;
        }
    }

    if (_evacCurrentIncident) {
        requestEvacuationRouteCalculation(
            _evacCurrentIncident.centroid_lat, _evacCurrentIncident.centroid_lon,
            destination.latitude, destination.longitude,
            _evacCurrentIncident.id
        );
    }
}

function requestEvacuationRouteCalculation(originLat, originLon, destLat, destLon, incidentId) {
    const riskBadge = document.getElementById("evac-risk-badge-display");
    if (riskBadge) {
        riskBadge.textContent = "CALCULATING SAFETY ROUTE...";
        riskBadge.style.color = "#38bdf8";
    }

    fetch("/api/evacuation/route", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            origin_lat: originLat,
            origin_lon: originLon,
            dest_lat: destLat,
            dest_lon: destLon,
            incident_id: incidentId
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status !== "success") return;
        _evacCurrentCalculatedRoutes = data;
        renderEvacuationRoutesOnMap(data);
        renderRouteSafetyScorecard(data.primary_route, data.routing_engine);
    })
    .catch(err => console.error("Error calculating evacuation route:", err));
}

function renderEvacuationRoutesOnMap(routesData) {
    if (!_evacMapController || !_evacMapController.map) return;
    const map = _evacMapController.map;

    // Clear existing route polylines & markers
    if (_evacPrimaryPolyline) map.removeLayer(_evacPrimaryPolyline);
    if (_evacAltPolyline) map.removeLayer(_evacAltPolyline);
    if (_evacOriginMarker) map.removeLayer(_evacOriginMarker);
    if (_evacDestMarker) map.removeLayer(_evacDestMarker);

    const primary = routesData.primary_route;
    const alternative = routesData.alternative_route;
    const risk = primary.risk_assessment;

    // 1. Determine Primary Route Color by Evaluated Risk
    let routeColor = "#10b981"; // SAFE
    if (risk.risk_level === "HIGH_RISK") routeColor = "#ef4444";
    else if (risk.risk_level === "CAUTION") routeColor = "#f59e0b";
    else if (risk.risk_level === "UNVERIFIED") routeColor = "#94a3b8";

    // 2. Draw Primary Route
    _evacPrimaryPolyline = L.polyline(primary.coordinates, {
        color: routeColor,
        weight: 5,
        opacity: 0.9,
        lineCap: "round",
        lineJoin: "round"
    }).addTo(map);

    // 3. Draw Alternative Route (dashed cyan) if enabled
    if (alternative && alternative.coordinates && _evacShowAlternative) {
        _evacAltPolyline = L.polyline(alternative.coordinates, {
            color: "#38bdf8",
            weight: 4,
            opacity: 0.7,
            dashArray: "6, 10",
            lineCap: "round"
        }).addTo(map).bindPopup("<b>Alternative Bypass Route</b><br>" + alternative.distance_km + " km (" + alternative.duration_minutes + " min)");
    }

    // 4. Origin Marker (Red Epicenter)
    _evacOriginMarker = L.circleMarker([routesData.origin[0], routesData.origin[1]], {
        radius: 11,
        color: "#ef4444",
        fillColor: "#ef4444",
        fillOpacity: 0.85,
        weight: 3
    }).addTo(map).bindPopup(`<b>Hazard Epicenter (Origin)</b><br>Lat: ${routesData.origin[0]}<br>Lon: ${routesData.origin[1]}`);

    // 5. Destination Marker
    const isShelter = _evacSelectedDestination && _evacSelectedDestination.destination_type === "SHELTER";
    const destColor = isShelter ? "#10b981" : "#06b6d4";

    _evacDestMarker = L.circleMarker([routesData.destination[0], routesData.destination[1]], {
        radius: 11,
        color: destColor,
        fillColor: destColor,
        fillOpacity: 0.85,
        weight: 3
    }).addTo(map).bindPopup(`<b>${_evacSelectedDestination ? _evacSelectedDestination.name : 'Destination'}</b><br>Safe Evacuation Point`);

    // 6. Fit Bounds
    map.fitBounds(_evacPrimaryPolyline.getBounds().pad(0.18));
}

function renderRouteSafetyScorecard(primaryRoute, routingEngine) {
    const risk = primaryRoute.risk_assessment;
    const distEl = document.getElementById("evac-route-dist");
    const durEl = document.getElementById("evac-route-duration");
    const badgeEl = document.getElementById("evac-risk-badge-display");
    const engineEl = document.getElementById("evac-risk-engine-label");
    const fireEl = document.getElementById("evac-hazard-fire-dist");
    const floodEl = document.getElementById("evac-hazard-flood-dist");
    const closuresEl = document.getElementById("evac-hazard-closures");
    const warningsContainer = document.getElementById("evac-warnings-list");
    const tsEl = document.getElementById("evac-data-timestamp");

    if (distEl) distEl.textContent = primaryRoute.distance_km + " km";
    if (durEl) durEl.textContent = Math.round(primaryRoute.duration_minutes) + " min";
    if (engineEl) engineEl.textContent = "Routing Engine: " + routingEngine;
    if (tsEl) tsEl.textContent = risk.data_freshness || "--";

    if (badgeEl) {
        badgeEl.textContent = risk.risk_level.replace(/_/g, " ");
        if (risk.risk_level === "SAFE") badgeEl.style.color = "#10b981";
        else if (risk.risk_level === "CAUTION") badgeEl.style.color = "#fbbf24";
        else if (risk.risk_level === "HIGH_RISK") badgeEl.style.color = "#ef4444";
        else badgeEl.style.color = "#94a3b8";
    }

    if (fireEl) fireEl.textContent = risk.min_fire_proximity_km !== null ? (risk.min_fire_proximity_km + " km clearance") : "None in Area";
    if (floodEl) floodEl.textContent = risk.min_flood_proximity_km !== null ? (risk.min_flood_proximity_km + " km clearance") : "None in Area";
    if (closuresEl) closuresEl.textContent = risk.active_road_closures_count || 0;

    if (warningsContainer) {
        if (risk.warnings && risk.warnings.length > 0) {
            warningsContainer.innerHTML = risk.warnings.map(w => `
                <div style="background: rgba(0,0,0,0.25); border-left: 3px solid ${risk.risk_level === 'SAFE' ? '#10b981' : '#f59e0b'}; padding: 5px 8px; border-radius: 3px;">
                    ${w}
                </div>
            `).join("");
        } else {
            warningsContainer.innerHTML = '<div style="color:#10b981;">No active hazard conflicts detected on path.</div>';
        }
    }
}

function toggleAlternativeEvacuationRoute() {
    _evacShowAlternative = !_evacShowAlternative;
    const btn = document.getElementById("evac-toggle-alt-btn");
    if (btn) {
        btn.textContent = _evacShowAlternative ? "Hide Alternative Route" : "Show Alternative Route";
        btn.style.background = _evacShowAlternative ? "rgba(56, 189, 248, 0.2)" : "transparent";
    }
    if (_evacCurrentCalculatedRoutes) {
        renderEvacuationRoutesOnMap(_evacCurrentCalculatedRoutes);
    }
}

function loadEvacuationHazardLayers() {
    if (!_evacMapController || !_evacMapController.map || !_evacHazardLayerGroup) return;
    _evacHazardLayerGroup.clearLayers();

    fetch("/api/evacuation/hazards")
        .then(r => r.json())
        .then(geojson => {
            if (!geojson || !geojson.features) return;
            geojson.features.forEach(f => {
                const geom = f.geometry;
                const props = f.properties;
                if (!geom || !geom.coordinates) return;
                const lat = geom.coordinates[1];
                const lon = geom.coordinates[0];

                if (props.layer_type === "ROAD_HAZARD") {
                    L.circleMarker([lat, lon], {
                        radius: 7,
                        color: "#f59e0b",
                        fillColor: "#f59e0b",
                        fillOpacity: 0.8,
                        weight: 2
                    }).addTo(_evacHazardLayerGroup).bindPopup(`<b>Obstruction: ${props.hazard_type}</b><br>${props.description}`);

                    // Danger buffer circle
                    L.circle([lat, lon], {
                        radius: (props.radius_km || 1.5) * 1000,
                        color: "rgba(245, 158, 11, 0.4)",
                        fillColor: "rgba(245, 158, 11, 0.15)",
                        weight: 1
                    }).addTo(_evacHazardLayerGroup);
                } else if (props.layer_type === "SATELLITE_HAZARD") {
                    const color = props.hazard_type === "FIRE" ? "#ff4d4f" : "#00d2ff";
                    L.circleMarker([lat, lon], {
                        radius: 5,
                        color: color,
                        fillColor: color,
                        fillOpacity: 0.6,
                        weight: 1
                    }).addTo(_evacHazardLayerGroup).bindPopup(`<b>${props.hazard_type} Hazard</b><br>Intensity: ${props.intensity || '--'}`);
                }
            });
        })
        .catch(err => console.error("Error loading hazard layers:", err));
}

function loadEvacuationSheltersTable() {
    fetch("/api/evacuation/shelters")
        .then(r => r.json())
        .then(data => {
            const tbody = document.getElementById("evac-shelters-table-body");
            if (!tbody) return;
            if (data.status !== "success" || !data.shelters || data.shelters.length === 0) {
                tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:20px; color:var(--text-muted);">No shelters registered.</td></tr>';
                return;
            }
            tbody.innerHTML = data.shelters.map(s => {
                const occPct = s.occupancy_pct || 0;
                const occClass = occPct > 85 ? "badge-danger" : occPct > 60 ? "badge-warning" : "badge-success";
                return `
                    <tr>
                        <td style="font-family:var(--font-mono); font-size:0.75rem;">${s.shelter_uid}</td>
                        <td style="font-weight:600;">${s.name}</td>
                        <td style="font-size:0.75rem;">${s.category.replace(/_/g, ' ')}</td>
                        <td style="font-size:0.75rem;">${s.city || ''}, ${s.state || ''}</td>
                        <td style="font-family:var(--font-mono);">${s.capacity}</td>
                        <td style="font-family:var(--font-mono);">${s.current_occupancy}</td>
                        <td><span class="badge ${occClass}">${s.available_capacity} free (${occPct}%)</span></td>
                        <td><span class="badge ${s.operating_status === 'OPEN' ? 'badge-success' : 'badge-danger'}">${s.operating_status}</span></td>
                        <td>
                            <button class="btn btn-outline" style="font-size:0.7rem; padding:3px 8px;" onclick="openShelterOccupancyModal(${s.id}, '${s.name}', ${s.capacity}, ${s.current_occupancy})">
                                Adjust Headroom
                            </button>
                        </td>
                    </tr>
                `;
            }).join("");
        })
        .catch(err => console.error("Error loading shelters table:", err));
}

function openShelterOccupancyModal(id, name, capacity, occupancy) {
    const modal = document.getElementById("evac-occupancy-modal");
    if (!modal) return;
    document.getElementById("evac-modal-shelter-id").value = id;
    document.getElementById("evac-modal-shelter-name").textContent = name;
    document.getElementById("evac-modal-capacity").value = capacity + " Beds";
    document.getElementById("evac-modal-new-occ").value = occupancy;
    document.getElementById("evac-modal-new-occ").max = capacity;
    document.getElementById("evac-modal-error").style.display = "none";
    modal.style.display = "flex";
}

function closeShelterOccupancyModal() {
    const modal = document.getElementById("evac-occupancy-modal");
    if (modal) modal.style.display = "none";
}

function handleShelterOccupancySubmit(e) {
    e.preventDefault();
    const shelterId = document.getElementById("evac-modal-shelter-id").value;
    const newOcc = parseInt(document.getElementById("evac-modal-new-occ").value, 10);
    const officer = document.getElementById("evac-modal-officer").value.trim();
    const remarks = document.getElementById("evac-modal-remarks").value.trim();
    const errorEl = document.getElementById("evac-modal-error");

    fetch(`/api/evacuation/shelters/${shelterId}/occupancy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            new_occupancy: newOcc,
            updated_by: officer,
            remarks: remarks
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === "success") {
            closeShelterOccupancyModal();
            fetchEvacuationStats();
            loadEvacuationSheltersTable();
            if (_evacCurrentIncident) {
                handleEvacuationIncidentSelected(_evacCurrentIncident.id);
            }
        } else {
            if (errorEl) {
                errorEl.textContent = data.message || "Failed to update occupancy.";
                errorEl.style.display = "block";
            }
        }
    })
    .catch(err => {
        if (errorEl) {
            errorEl.textContent = "Error saving shelter occupancy.";
            errorEl.style.display = "block";
        }
    });
}
