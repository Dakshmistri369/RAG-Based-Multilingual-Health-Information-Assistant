/**
 * frontend/js/utils.js
 * =====================
 * Shared utility functions for SwasthyaSetu AI frontend.
 */

/**
 * Debounce a function — delays execution until 'wait' ms have passed
 * since the last call. Useful for search inputs and resize handlers.
 *
 * @param {Function} fn - Function to debounce
 * @param {number} wait - Delay in milliseconds
 * @returns {Function} Debounced function
 */
export function debounce(fn, wait = 300) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), wait);
    };
}

/**
 * Sanitize user input to prevent XSS.
 * Encodes HTML special characters before inserting into the DOM.
 *
 * @param {string} input - Raw user input
 * @returns {string} HTML-encoded safe string
 */
export function sanitizeInput(input) {
    const div = document.createElement("div");
    div.textContent = String(input);
    return div.innerHTML;
}

/**
 * Format a timestamp as a localised time string.
 *
 * @param {Date} [date] - Date to format (defaults to now)
 * @param {string} [locale] - Locale string e.g. 'hi-IN', 'en-IN'
 * @returns {string} Formatted time string like "10:34 AM"
 */
export function formatTimestamp(date = new Date(), locale = "en-IN") {
    return date.toLocaleTimeString(locale, {
        hour: "2-digit",
        minute: "2-digit",
        hour12: true,
    });
}

/**
 * Generate a simple unique session ID.
 * Uses crypto.randomUUID() if available, falls back to timestamp-based ID.
 *
 * @returns {string} UUID-like session identifier
 */
export function generateSessionId() {
    if (typeof crypto !== "undefined" && crypto.randomUUID) {
        return crypto.randomUUID();
    }
    // Fallback for older browsers
    return "session-" + Date.now().toString(36) + Math.random().toString(36).slice(2);
}

/**
 * Convert audio Blob to base64 string.
 *
 * @param {Blob} blob - Audio blob from MediaRecorder
 * @returns {Promise<string>} Base64 encoded audio data (without data URL prefix)
 */
export function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            // Remove "data:audio/...;base64," prefix
            const base64 = reader.result.split(",")[1];
            resolve(base64);
        };
        reader.onerror = reject;
        reader.readAsDataURL(blob);
    });
}

/**
 * Play base64-encoded audio in the browser.
 *
 * @param {string} audioBase64 - Base64 WAV audio data
 * @returns {Promise<void>}
 */
export async function playBase64Audio(audioBase64) {
    try {
        const binary = atob(audioBase64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }
        const blob = new Blob([bytes], { type: "audio/wav" });
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        await audio.play();
        audio.onended = () => URL.revokeObjectURL(url);
    } catch (err) {
        console.warn("Audio playback failed:", err);
    }
}

/**
 * Smooth-scroll the messages area to the bottom.
 *
 * @param {HTMLElement} container - Scrollable container element
 * @param {boolean} [instant] - If true, jump immediately instead of smooth scroll
 */
export function scrollToBottom(container, instant = false) {
    if (!container) return;
    container.scrollTo({
        top: container.scrollHeight,
        behavior: instant ? "instant" : "smooth",
    });
}

/**
 * Show a temporary toast notification.
 *
 * @param {string} message - Toast message text
 * @param {number} [duration] - Duration in ms before auto-dismiss (default 3000)
 */
export function showToast(message, duration = 3000) {
    let container = document.getElementById("toast-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "toast-container";
        container.className = "toast-container";
        document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transition = "opacity 0.3s ease";
        setTimeout(() => toast.remove(), 350);
    }, duration);
}

/**
 * Render markdown-like formatting for bot responses.
 * Handles: **bold**, newlines, bullet points.
 * Does NOT use a full markdown library to keep the bundle tiny.
 *
 * @param {string} text - Raw response text
 * @returns {string} HTML string (safe for innerHTML since we control the source)
 */
export function renderMarkdownLite(text) {
    if (!text) return "";
    return text
        // Bold
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        // Line breaks
        .replace(/\n/g, "<br>")
        // Bullet points (• or -)
        .replace(/^[•\-] (.+)/gm, "<li>$1</li>")
        // Wrap list items
        .replace(/(<li>.+<\/li>)+/g, (match) => `<ul>${match}</ul>`);
}

/**
 * Truncate text to a given length, adding ellipsis if needed.
 *
 * @param {string} text
 * @param {number} maxLength
 * @returns {string}
 */
export function truncate(text, maxLength = 80) {
    if (!text || text.length <= maxLength) return text;
    return text.slice(0, maxLength).trimEnd() + "…";
}
