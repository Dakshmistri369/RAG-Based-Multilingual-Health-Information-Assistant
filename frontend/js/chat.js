/**
 * frontend/js/chat.js
 * ====================
 * Core chat functionality for SwasthyaSetu AI.
 *
 * Responsibilities:
 * - Send messages to the /ask endpoint
 * - Render user messages, bot responses, source citations
 * - Render EMERGENCY responses with prominent UI treatment
 * - Show/hide typing indicator
 * - Manage session state
 * - Update the detected language display
 */

import { API_BASE_URL, SLOW_RESPONSE_THRESHOLD_MS, CATEGORY_OPTIONS } from "./config.js";
import { sanitizeInput, formatTimestamp, generateSessionId, scrollToBottom, renderMarkdownLite, showToast } from "./utils.js";
import { setSelectedLanguage } from "./languageSelector.js";
import { speakText } from "./voice.js";

// ── Session state ─────────────────────────────────────────────
let _sessionId = generateSessionId();
let _isLoading = false;
let _selectedCategory = "";

// ── DOM references (populated on init) ───────────────────────
let _messagesArea = null;
let _textarea = null;
let _sendBtn = null;
let _typingIndicator = null;
let _welcomeScreen = null;
let _detectedLangDisplay = null;

/**
 * Initialise the chat module.
 * Must be called after DOM is ready.
 */
export function initChat() {
    _messagesArea = document.getElementById("messages-area");
    _textarea = document.getElementById("chat-textarea");
    _sendBtn = document.getElementById("send-btn");
    _typingIndicator = document.getElementById("typing-indicator");
    _welcomeScreen = document.getElementById("welcome-screen");
    _detectedLangDisplay = document.getElementById("detected-language");

    if (!_messagesArea || !_textarea || !_sendBtn) {
        console.error("Chat: required DOM elements not found.");
        return;
    }

    // Auto-resize textarea as user types
    _textarea.addEventListener("input", _autoResizeTextarea);

    // Send on Enter (Shift+Enter for newline)
    _textarea.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Send button click
    _sendBtn.addEventListener("click", sendMessage);

    // Category filter (sidebar)
    document.getElementById("category-select")?.addEventListener("change", (e) => {
        _selectedCategory = e.target.value;
    });

    // Clear session button
    document.getElementById("clear-chat-btn")?.addEventListener("click", clearSession);

    // Prompt chips on welcome screen
    document.querySelectorAll(".prompt-chip").forEach((chip) => {
        chip.addEventListener("click", () => {
            const promptText = chip.dataset.prompt;
            if (promptText && _textarea) {
                _textarea.value = promptText;
                _autoResizeTextarea();
                sendMessage();
            }
        });
    });
}

/**
 * Set the text in the input textarea (called from voice.js after transcription).
 * @param {string} text
 */
export function setInputText(text) {
    if (_textarea) {
        _textarea.value = text;
        _autoResizeTextarea();
        _textarea.focus();
    }
}

/**
 * Send the current textarea content as a message.
 */
export async function sendMessage() {
    if (_isLoading || !_textarea) return;

    const question = _textarea.value.trim();
    if (!question) return;

    // Clear input
    _textarea.value = "";
    _autoResizeTextarea();

    // Hide welcome screen on first message
    if (_welcomeScreen && !_welcomeScreen.classList.contains("hidden")) {
        _welcomeScreen.classList.add("hidden");
    }

    // Render user message
    _renderUserMessage(question);
    scrollToBottom(_messagesArea);

    // Show typing indicator
    _setLoading(true);

    // Slow response warning
    const slowTimer = setTimeout(() => {
        showToast("Still processing… The knowledge base may be loading for the first time.");
    }, SLOW_RESPONSE_THRESHOLD_MS);

    try {
        const response = await fetch(`${API_BASE_URL}/ask`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question,
                session_id: _sessionId,
                category_filter: _selectedCategory || null,
            }),
        });

        clearTimeout(slowTimer);

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `Server error: ${response.status}`);
        }

        const data = await response.json();

        // Update detected language display
        if (_detectedLangDisplay && data.language_name) {
            _detectedLangDisplay.textContent = data.language_name;
            setSelectedLanguage(data.detected_language);
        }

        // Render bot response (emergency or normal)
        if (data.is_emergency) {
            _renderEmergencyMessage(data);
        } else {
            _renderBotMessage(data);
        }

        scrollToBottom(_messagesArea);

    } catch (err) {
        clearTimeout(slowTimer);
        console.error("Chat error:", err);

        _renderErrorMessage(
            err.message === "Failed to fetch"
                ? "Cannot reach the server. Please make sure the backend is running (uvicorn main:app --reload)."
                : err.message || "An unexpected error occurred. Please try again."
        );
        scrollToBottom(_messagesArea);
    } finally {
        _setLoading(false);
    }
}

/**
 * Clear the current session (conversation history).
 */
export async function clearSession() {
    try {
        await fetch(`${API_BASE_URL}/clear-session/${_sessionId}`, {
            method: "POST",
        });
    } catch (_) { /* Silent fail — session will just reset locally */ }

    // Generate a new session ID
    _sessionId = generateSessionId();

    // Clear messages UI
    if (_messagesArea) {
        _messagesArea.innerHTML = "";
    }

    // Show welcome screen again
    if (_welcomeScreen) {
        _welcomeScreen.classList.remove("hidden");
    }

    showToast("Conversation cleared. Starting fresh!");
}

// ── Private rendering functions ───────────────────────────────

function _renderUserMessage(text) {
    const wrapper = document.createElement("div");
    wrapper.className = "message-wrapper user-wrapper";
    wrapper.innerHTML = `
        <div class="message-avatar" aria-hidden="true">👤</div>
        <div>
            <div class="message-bubble" role="article">
                ${sanitizeInput(text)}
            </div>
            <div class="message-meta">
                <span>${formatTimestamp()}</span>
            </div>
        </div>
    `;
    _messagesArea.appendChild(wrapper);
}

function _renderBotMessage(data) {
    const wrapper = document.createElement("div");
    wrapper.className = "message-wrapper bot-wrapper";

    const sourcesHtml = _buildSourcesHtml(data.sources);
    const safeAnswer = renderMarkdownLite(sanitizeInput(data.answer));
    const langBadge = data.language_name
        ? `<span style="background:var(--color-primary-100);color:var(--color-primary-700);
                        padding:2px 8px;border-radius:9999px;font-size:0.7rem;font-weight:600;">
               ${sanitizeInput(data.language_name)}</span>`
        : "";

    wrapper.innerHTML = `
        <div class="message-avatar" aria-hidden="true">🩺</div>
        <div style="max-width:100%">
            <div class="message-bubble" role="article" aria-live="polite">
                <div>${safeAnswer}</div>
                ${sourcesHtml}
                <button class="tts-btn"
                        id="tts-btn-${Date.now()}"
                        aria-label="Listen to this response">
                    🔊 Listen
                </button>
            </div>
            <div class="message-meta">
                ${langBadge}
                <span>${formatTimestamp()}</span>
            </div>
        </div>
    `;

    _messagesArea.appendChild(wrapper);

    // Bind TTS button
    const ttsBtn = wrapper.querySelector(".tts-btn");
    if (ttsBtn) {
        ttsBtn.addEventListener("click", () => {
            speakText(data.answer, data.detected_language, ttsBtn);
        });
    }
}

function _renderEmergencyMessage(data) {
    const wrapper = document.createElement("div");
    wrapper.className = "emergency-message-wrapper";
    wrapper.setAttribute("role", "alert");
    wrapper.setAttribute("aria-live", "assertive");  // Screen readers announce immediately

    const helplineHref = `tel:${data.helpline}`;
    const safeMessage = renderMarkdownLite(sanitizeInput(data.answer));

    wrapper.innerHTML = `
        <div class="emergency-bubble">
            <div class="emergency-header">
                <div class="emergency-icon-large" aria-hidden="true">🚨</div>
                <div>
                    <div class="emergency-title">Emergency Alert</div>
                    <div class="emergency-subtitle">${sanitizeInput(data.helpline_name || "Emergency Services")}</div>
                </div>
            </div>

            <div class="emergency-message-text">${safeMessage}</div>

            <a href="${helplineHref}"
               class="helpline-btn"
               id="helpline-call-btn"
               aria-label="Call ${data.helpline_name || 'emergency services'} at ${data.helpline}">
                <span class="phone-icon" aria-hidden="true">📞</span>
                <div>
                    <div>${sanitizeInput(data.helpline)}</div>
                    <div class="helpline-name">${sanitizeInput(data.helpline_name || "")}</div>
                </div>
            </a>

            <div style="margin-top:12px;font-size:0.75rem;color:var(--color-emergency-600)">
                ⏰ Tap the button above to call immediately from your phone.
            </div>
        </div>
        <div class="message-meta" style="margin-top:8px;padding-left:8px">
            <span>${formatTimestamp()}</span>
        </div>
    `;

    _messagesArea.appendChild(wrapper);
}

function _renderErrorMessage(errorText) {
    const wrapper = document.createElement("div");
    wrapper.className = "message-wrapper bot-wrapper";
    wrapper.innerHTML = `
        <div class="message-avatar" aria-hidden="true">⚠️</div>
        <div>
            <div class="message-bubble" style="border-color:var(--color-warning-400);background:var(--color-warning-100);">
                <strong>Error:</strong> ${sanitizeInput(errorText)}
            </div>
            <div class="message-meta">${formatTimestamp()}</div>
        </div>
    `;
    _messagesArea.appendChild(wrapper);
}

function _buildSourcesHtml(sources) {
    if (!sources || sources.length === 0) return "";

    const tags = sources.map(s => `
        <span class="source-tag" title="Category: ${sanitizeInput(s.category)}">
            📄 ${sanitizeInput(s.source)}${s.page != null ? ` p.${s.page}` : ""}
        </span>
    `).join("");

    return `
        <div class="source-citations">
            <div class="source-citations-label">Sources</div>
            <div>${tags}</div>
        </div>
    `;
}

function _setLoading(loading) {
    _isLoading = loading;

    if (_sendBtn) _sendBtn.disabled = loading;
    if (_textarea) _textarea.disabled = loading;

    if (_typingIndicator) {
        if (loading) {
            _typingIndicator.classList.remove("hidden");
            scrollToBottom(_messagesArea);
        } else {
            _typingIndicator.classList.add("hidden");
        }
    }
}

function _autoResizeTextarea() {
    if (!_textarea) return;
    _textarea.style.height = "auto";
    _textarea.style.height = Math.min(_textarea.scrollHeight, 140) + "px";
}
