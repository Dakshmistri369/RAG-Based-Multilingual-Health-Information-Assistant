/**
 * frontend/js/languageSelector.js
 * =================================
 * Language selector UI component for SwasthyaSetu AI.
 *
 * Provides a dropdown that lets the user manually override the auto-detected
 * language. The selected language is passed to the /ask endpoint as a hint
 * (via the detected language override) and is used by voice.js for
 * speech-to-text and text-to-speech language selection.
 *
 * Note: The backend auto-detects language from query text, so this selector
 * acts as a USER PREFERENCE OVERRIDE, not a requirement. If the user selects
 * Hindi but types in English, the backend may still detect English — and the
 * LLM will respond accordingly. The selector is most useful for:
 *   1. Ensuring TTS speaks in the correct language
 *   2. Pre-filtering results when the user's script/keyboard input might
 *      produce ambiguous language signals (e.g. typing Hinglish in English script)
 */

import { SUPPORTED_LANGUAGES } from "./config.js";
import { showToast } from "./utils.js";

/** Currently selected language (ISO code). Updated on user selection. */
let _selectedLanguage = "auto";

/** Callbacks to notify when language changes */
const _listeners = new Set();

/**
 * Get the currently selected language code.
 * @returns {string} ISO code like 'hi', 'en', or 'auto'
 */
export function getSelectedLanguage() {
    return _selectedLanguage;
}

/**
 * Programmatically update the selected language (e.g., from auto-detection result).
 * @param {string} langCode - ISO language code
 */
export function setSelectedLanguage(langCode) {
    _selectedLanguage = langCode;
    const select = document.getElementById("language-select");
    if (select && select.value !== langCode) {
        // Try to set the value; if the code isn't in the list, keep 'auto'
        const exists = [...select.options].some(o => o.value === langCode);
        select.value = exists ? langCode : "auto";
    }
    _listeners.forEach(cb => cb(langCode));
}

/**
 * Register a callback to be called when language changes.
 * @param {function} callback - Called with (langCode: string)
 */
export function onLanguageChange(callback) {
    _listeners.add(callback);
}

/**
 * Initialise the language selector dropdown.
 * Populates the <select> element with supported languages and binds events.
 *
 * @param {string} [selectElementId] - ID of the <select> element to populate
 */
export function initLanguageSelector(selectElementId = "language-select") {
    const select = document.getElementById(selectElementId);
    if (!select) {
        console.warn(`Language selector element #${selectElementId} not found.`);
        return;
    }

    // Clear existing options (in case of re-init)
    select.innerHTML = "";

    // Add "Auto-detect" as first option
    const autoOption = document.createElement("option");
    autoOption.value = "auto";
    autoOption.textContent = "🌐 Auto-detect";
    select.appendChild(autoOption);

    // Add each supported language
    for (const lang of SUPPORTED_LANGUAGES) {
        const option = document.createElement("option");
        option.value = lang.code;
        option.textContent = lang.name;
        select.appendChild(option);
    }

    // Event handler
    select.addEventListener("change", (e) => {
        const newLang = e.target.value;
        _selectedLanguage = newLang;

        const langName = newLang === "auto"
            ? "Auto-detect"
            : SUPPORTED_LANGUAGES.find(l => l.code === newLang)?.name || newLang;

        showToast(`Language set to: ${langName}`);
        _listeners.forEach(cb => cb(newLang));
    });

    // Set initial value
    select.value = _selectedLanguage;
}

/**
 * Get the language code to send to the backend.
 * If 'auto', returns null (backend will detect from query text).
 * Otherwise returns the user's explicit selection.
 *
 * @returns {string|null}
 */
export function getLanguageForRequest() {
    return _selectedLanguage === "auto" ? null : _selectedLanguage;
}

/**
 * Get the display name of the currently selected language.
 * @returns {string}
 */
export function getSelectedLanguageName() {
    if (_selectedLanguage === "auto") return "Auto-detect";
    return SUPPORTED_LANGUAGES.find(l => l.code === _selectedLanguage)?.name || _selectedLanguage;
}
