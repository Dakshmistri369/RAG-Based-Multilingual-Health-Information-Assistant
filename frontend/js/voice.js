/**
 * frontend/js/voice.js
 * =====================
 * Voice input (STT) and output (TTS) functionality for SwasthyaSetu AI.
 *
 * Uses the browser's MediaRecorder API to capture microphone audio,
 * then sends it to the backend /speech-to-text endpoint which calls
 * openai/whisper-large-v3 via HuggingFace Inference API.
 *
 * For TTS, sends the response text to /text-to-speech which calls
 * facebook/mms-tts-{lang} (MMS — Massively Multilingual Speech) via
 * HuggingFace, and plays the returned WAV audio.
 *
 * Graceful degradation:
 * - If microphone permission is denied: shows a friendly message, falls back to text
 * - If HuggingFace STT/TTS fails or model is cold-starting: shows toast, falls back
 * - If recording times out (MAX_RECORDING_SECONDS): auto-stops and sends
 */

import { API_BASE_URL, MAX_RECORDING_SECONDS } from "./config.js";
import { blobToBase64, playBase64Audio, showToast } from "./utils.js";
import { getSelectedLanguage } from "./languageSelector.js";

let _mediaRecorder = null;
let _audioChunks = [];
let _isRecording = false;
let _recordingTimeout = null;

/** Callback to call when a transcription is received */
let _onTranscriptionCallback = null;

/**
 * Register a callback to be called when speech-to-text returns a result.
 * @param {function} callback - Called with (transcribedText: string)
 */
export function onTranscription(callback) {
    _onTranscriptionCallback = callback;
}

/**
 * Check if the browser supports MediaRecorder.
 * @returns {boolean}
 */
export function isVoiceSupported() {
    return (
        typeof navigator !== "undefined" &&
        typeof navigator.mediaDevices !== "undefined" &&
        typeof MediaRecorder !== "undefined"
    );
}

/**
 * Start recording audio from the microphone.
 * Returns a Promise that resolves when recording starts successfully.
 *
 * @param {HTMLButtonElement} micBtn - The mic button element (for UI state)
 * @returns {Promise<boolean>} True if recording started, false on failure
 */
export async function startRecording(micBtn) {
    if (!isVoiceSupported()) {
        showToast("Voice input not supported in this browser. Please type your question.");
        return false;
    }

    if (_isRecording) {
        stopRecording(micBtn);
        return false;
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                channelCount: 1,
                sampleRate: 16000,    // Preferred by Bhashini ASR
                echoCancellation: true,
                noiseSuppression: true,
            },
        });

        _audioChunks = [];
        _mediaRecorder = new MediaRecorder(stream, {
            mimeType: getSupportedMimeType(),
        });

        _mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                _audioChunks.push(event.data);
            }
        };

        _mediaRecorder.onstop = async () => {
            // Stop all tracks to release microphone
            stream.getTracks().forEach(t => t.stop());
            await _processAudioChunks();
        };

        _mediaRecorder.start(100);  // Collect data every 100ms
        _isRecording = true;

        // Update mic button UI to recording state
        if (micBtn) {
            micBtn.classList.add("recording");
            micBtn.setAttribute("aria-label", "Stop recording");
            micBtn.title = "Click to stop recording";
        }

        // Auto-stop after MAX_RECORDING_SECONDS
        _recordingTimeout = setTimeout(() => {
            if (_isRecording) {
                showToast(`Recording stopped (${MAX_RECORDING_SECONDS}s limit).`);
                stopRecording(micBtn);
            }
        }, MAX_RECORDING_SECONDS * 1000);

        return true;

    } catch (err) {
        if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
            showToast("🎤 Microphone permission denied. Please allow microphone access and try again.");
        } else {
            showToast("Could not start recording. Please type your question instead.");
            console.warn("Recording error:", err);
        }
        return false;
    }
}

/**
 * Stop the current recording.
 * @param {HTMLButtonElement} micBtn - The mic button element
 */
export function stopRecording(micBtn) {
    if (!_isRecording) return;

    clearTimeout(_recordingTimeout);
    _isRecording = false;

    if (_mediaRecorder && _mediaRecorder.state !== "inactive") {
        _mediaRecorder.stop();
    }

    // Reset mic button UI
    if (micBtn) {
        micBtn.classList.remove("recording");
        micBtn.setAttribute("aria-label", "Start voice input");
        micBtn.title = "Click to speak your question";
    }
}

/**
 * Check if currently recording.
 * @returns {boolean}
 */
export function isRecording() {
    return _isRecording;
}

/**
 * Process the recorded audio chunks, send to backend ASR, and call the
 * transcription callback with the result.
 *
 * @private
 */
async function _processAudioChunks() {
    if (_audioChunks.length === 0) {
        showToast("No audio recorded. Please try again.");
        return;
    }

    const mimeType = getSupportedMimeType();
    const blob = new Blob(_audioChunks, { type: mimeType });

    // Must be at least ~0.5 seconds of audio
    if (blob.size < 4000) {
        showToast("Recording too short. Please speak clearly and try again.");
        return;
    }

    try {
        const base64Audio = await blobToBase64(blob);
        const lang = getSelectedLanguage();
        const langCode = lang === "auto" ? "hi" : lang;

        // Show loading state
        showToast("🎤 Transcribing with Whisper AI…");

        const response = await fetch(`${API_BASE_URL}/speech-to-text`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                audio_base64: base64Audio,
                language: langCode,
            }),
        });

        if (!response.ok) throw new Error(`STT API returned ${response.status}`);

        const data = await response.json();

        if (data.success && data.transcribed_text) {
            if (_onTranscriptionCallback) {
                _onTranscriptionCallback(data.transcribed_text);
            }
        } else {
            showToast(data.message || "Voice transcription failed. Please type your question.");
        }
    } catch (err) {
        console.warn("STT request failed:", err);
        showToast("Voice service unavailable. Please type your question.");
    }
}

/**
 * Request text-to-speech for a given text.
 * Plays the audio if successful; silently skips if TTS fails.
 *
 * @param {string} text - Text to speak
 * @param {string} [langCode] - Language code (default: currently selected)
 * @param {HTMLButtonElement} [ttsBtn] - TTS button to show loading state
 */
export async function speakText(text, langCode, ttsBtn) {
    const lang = langCode || (getSelectedLanguage() === "auto" ? "hi" : getSelectedLanguage());

    // Truncate to avoid very long TTS requests
    const truncatedText = text.slice(0, 500);

    if (ttsBtn) {
        ttsBtn.disabled = true;
        ttsBtn.textContent = "🔊 ...";
    }

    try {
        const response = await fetch(`${API_BASE_URL}/text-to-speech`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                text: truncatedText,
                language: lang,
                gender: "female",
            }),
        });

        if (!response.ok) throw new Error(`TTS API returned ${response.status}`);

        const data = await response.json();

        if (data.success && data.audio_base64) {
            await playBase64Audio(data.audio_base64);
        } else {
            // Silent fail — user still has the text
            console.info("TTS not available:", data.message);
        }
    } catch (err) {
        console.warn("TTS request failed:", err);
        // No toast here — silent degradation is preferable for TTS
    } finally {
        if (ttsBtn) {
            ttsBtn.disabled = false;
            ttsBtn.textContent = "🔊 Listen";
        }
    }
}

/**
 * Get the best supported MIME type for audio recording.
 * Tries WebM (Chromium) then OGG (Firefox) then MP4 (Safari).
 *
 * @returns {string} MIME type string
 */
function getSupportedMimeType() {
    const types = [
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/ogg;codecs=opus",
        "audio/ogg",
        "audio/mp4",
    ];
    for (const type of types) {
        if (MediaRecorder.isTypeSupported(type)) return type;
    }
    return "";  // Let browser choose
}
