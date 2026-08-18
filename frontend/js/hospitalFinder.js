/**
 * frontend/js/hospitalFinder.js
 * ==============================
 * Hospital/PHC finder UI component for SwasthyaSetu AI.
 *
 * Uses the browser's Geolocation API to get the user's GPS coordinates,
 * then calls the backend /nearest-hospital endpoint to find nearby facilities.
 * Displays results as a card list in the sidebar.
 */

import { API_BASE_URL } from "./config.js";
import { showToast } from "./utils.js";

/**
 * Request the user's location and find nearby hospitals.
 * Displays results in the element matching resultsContainerId.
 *
 * @param {string} [resultsContainerId] - ID of the results container element
 */
export async function findNearestHospitals(resultsContainerId = "hospital-results") {
    const container = document.getElementById(resultsContainerId);
    const btn = document.getElementById("find-hospitals-btn");

    if (!container) {
        console.warn(`Hospital results container #${resultsContainerId} not found.`);
        return;
    }

    // Check geolocation support
    if (!navigator.geolocation) {
        container.innerHTML = `
            <div class="hospital-result-card">
                <p class="hospital-meta">📍 Location services are not available in this browser.</p>
            </div>`;
        return;
    }

    // Show loading state
    container.innerHTML = `
        <div style="display:flex;align-items:center;gap:8px;padding:12px;color:var(--color-text-secondary)">
            <div class="spinner"></div>
            <span>Getting your location…</span>
        </div>`;

    if (btn) {
        btn.disabled = true;
        btn.textContent = "Locating…";
    }

    try {
        const position = await _getGeolocation();
        const { latitude, longitude } = position.coords;

        // Fetch from backend
        const response = await fetch(`${API_BASE_URL}/nearest-hospital`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                latitude,
                longitude,
                top_n: 3,
            }),
        });

        if (!response.ok) {
            throw new Error(`Server returned ${response.status}`);
        }

        const data = await response.json();
        renderHospitalResults(data.hospitals, container);

    } catch (err) {
        console.warn("Hospital finder error:", err);

        let errorMessage = "Could not find nearby hospitals. Please try again.";

        if (err.code === GeolocationPositionError?.PERMISSION_DENIED || err.message?.includes("permission")) {
            errorMessage = "📍 Location access was denied. Please enable location in your browser settings.";
        } else if (err.code === GeolocationPositionError?.TIMEOUT) {
            errorMessage = "📍 Location request timed out. Please ensure you're in an area with GPS signal.";
        }

        container.innerHTML = `
            <div class="hospital-result-card">
                <p class="hospital-meta" style="color:var(--color-warning-600)">${errorMessage}</p>
            </div>`;

        showToast(errorMessage);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = "📍 Find Nearest Hospital";
        }
    }
}

/**
 * Render hospital results as HTML cards.
 *
 * @param {Array} hospitals - Array of hospital objects from the API
 * @param {HTMLElement} container - Container element to render into
 */
function renderHospitalResults(hospitals, container) {
    if (!hospitals || hospitals.length === 0) {
        container.innerHTML = `
            <div class="hospital-result-card">
                <p class="hospital-meta">No facilities found near your location.</p>
            </div>`;
        return;
    }

    const html = hospitals.map((hospital, index) => `
        <div class="hospital-result-card" role="article" aria-label="${hospital.name}">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px">
                <div class="hospital-name">${escapeHtml(hospital.name)}</div>
                <span class="hospital-type-badge">${escapeHtml(hospital.type)}</span>
            </div>
            <div class="hospital-meta">
                📍 ${escapeHtml(hospital.city)}, ${escapeHtml(hospital.state)}
            </div>
            <div class="hospital-meta" style="margin-top:4px">
                ${escapeHtml(hospital.address)}
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px">
                <div class="hospital-distance">🗺️ ${hospital.distance_km} km away</div>
                <a href="tel:${escapeHtml(hospital.phone)}"
                   style="display:inline-flex;align-items:center;gap:4px;
                          background:var(--color-success-600);color:white;
                          padding:4px 10px;border-radius:9999px;font-size:0.75rem;
                          font-weight:600;text-decoration:none;"
                   aria-label="Call ${hospital.name}">
                    📞 ${escapeHtml(hospital.phone)}
                </a>
            </div>
        </div>
    `).join("");

    container.innerHTML = html;
}

/**
 * Promise wrapper around navigator.geolocation.getCurrentPosition
 *
 * @returns {Promise<GeolocationPosition>}
 */
function _getGeolocation() {
    return new Promise((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(
            resolve,
            reject,
            {
                enableHighAccuracy: true,
                timeout: 15000,
                maximumAge: 60000,   // Accept cached position up to 1 minute old
            }
        );
    });
}

/**
 * Simple HTML escaping to prevent XSS in hospital data.
 * @param {string} str
 * @returns {string}
 */
function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = String(str ?? "");
    return div.innerHTML;
}
