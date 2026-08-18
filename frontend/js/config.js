/**
 * frontend/js/config.js
 * ======================
 * Central configuration for the SwasthyaSetu AI frontend.
 *
 * Change API_BASE_URL to point to your deployed backend in production.
 */

export const API_BASE_URL = "https://swasthya-setu-backend-production-32a1.up.railway.app";

/** Default language to use when detection hasn't run yet */
export const DEFAULT_LANGUAGE = "en";

/** How long to wait before showing "still working..." message (ms) */
export const SLOW_RESPONSE_THRESHOLD_MS = 8000;

/** Max recording duration in seconds (Bhashini ASR limit) */
export const MAX_RECORDING_SECONDS = 30;

/** Supported languages for the manual override dropdown */
export const SUPPORTED_LANGUAGES = [
    { code: "hi", name: "हिंदी (Hindi)", script: "Devanagari" },
    { code: "en", name: "English", script: "Latin" },
    { code: "ta", name: "தமிழ் (Tamil)", script: "Tamil" },
    { code: "te", name: "తెలుగు (Telugu)", script: "Telugu" },
    { code: "bn", name: "বাংলা (Bengali)", script: "Bengali" },
    { code: "mr", name: "मराठी (Marathi)", script: "Devanagari" },
    { code: "gu", name: "ગુજરાતી (Gujarati)", script: "Gujarati" },
    { code: "kn", name: "ಕನ್ನಡ (Kannada)", script: "Kannada" },
    { code: "ml", name: "മലയാളം (Malayalam)", script: "Malayalam" },
    { code: "pa", name: "ਪੰਜਾਬੀ (Punjabi)", script: "Gurmukhi" },
];

/** Category filter options for the sidebar */
export const CATEGORY_OPTIONS = [
    { value: "", label: "All Topics" },
    { value: "symptoms", label: "🤒 Symptoms" },
    { value: "prevention", label: "🛡️ Prevention" },
    { value: "treatment_general", label: "💊 Treatment Info" },
    { value: "scheme_info", label: "🏥 Government Schemes" },
    { value: "mental_health", label: "🧠 Mental Health" },
    { value: "maternal_child_health", label: "👶 Maternal & Child Health" },
];
