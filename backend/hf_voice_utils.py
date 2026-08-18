"""
backend/hf_voice_utils.py
==========================
HuggingFace Inference API — Speech-to-Text and Text-to-Speech for SwasthyaSetu AI.

Models used:
  STT : openai/whisper-large-v3
        Multilingual Whisper — handles all major Indian languages natively.
        Accepts raw audio bytes; returns JSON with transcribed text.

  TTS : facebook/mms-tts-{lang}
        Facebook MMS (Massively Multilingual Speech) TTS.
        Separate per-language model endpoint; returns WAV audio bytes.
        Covers all 10 supported Indian languages + English.

API:  HuggingFace Inference API (cloud hosted, no GPU required locally)
Auth: Bearer token from HUGGINGFACE_API_KEY in .env
Free: ~30,000 API calls/month on free tier
Docs: https://huggingface.co/docs/api-inference/quicktour

Graceful degradation:
  All calls are wrapped in try/except. If the HuggingFace API is unavailable
  or the token is missing, functions return None — the frontend silently falls
  back to text-only mode without crashing.

  Common failure reasons:
    - HF model is loading ("cold start") → returns 503 with estimated wait time
    - Free tier rate limit exceeded
    - Audio format unsupported (always send WAV/PCM for best compatibility)
"""

from __future__ import annotations

import base64
import logging
import sys
import time
from pathlib import Path
from typing import Optional

import httpx

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from config import (
    HUGGINGFACE_API_KEY,
    HF_INFERENCE_URL,
    HF_STT_MODEL,
    HF_TTS_MODEL_PREFIX,
)

logger = logging.getLogger(__name__)

# Request timeout in seconds — HuggingFace cold-starts can take ~20s
REQUEST_TIMEOUT = 40.0

# ── Language code → MMS-TTS model suffix mapping ─────────────────────────────
# Maps ISO-639-1 codes (used internally) to the ISO-639-3 codes used by MMS.
# Full list: https://huggingface.co/facebook/mms-tts
MMS_LANG_MAP: dict[str, str] = {
    "hi": "hin",    # Hindi
    "ta": "tam",    # Tamil
    "te": "tel",    # Telugu
    "bn": "ben",    # Bengali
    "mr": "mar",    # Marathi
    "gu": "guj",    # Gujarati
    "kn": "kan",    # Kannada
    "ml": "mal",    # Malayalam
    "pa": "pan",    # Punjabi (Gurmukhi)
    "ur": "urd",    # Urdu
    "or": "ory",    # Odia
    "en": "eng",    # English
}

# Whisper language hints (optional — improves accuracy, ISO-639-1)
WHISPER_LANG_HINTS: dict[str, str] = {
    "hi": "hindi", "ta": "tamil", "te": "telugu", "bn": "bengali",
    "mr": "marathi", "gu": "gujarati", "kn": "kannada", "ml": "malayalam",
    "pa": "punjabi", "ur": "urdu", "en": "english",
}


def _hf_headers() -> dict[str, str]:
    """Build HuggingFace Authorization headers."""
    return {
        "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
        "Content-Type": "application/json",
    }


def _hf_audio_headers() -> dict[str, str]:
    """Build headers for sending raw audio binary to HuggingFace."""
    return {
        "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
        "Content-Type": "audio/wav",
    }


# ── Speech-to-Text (Whisper large-v3) ────────────────────────────────────────

def speech_to_text(audio_base64: str, language: str = "hi") -> Optional[str]:
    """
    Transcribe base64-encoded audio to text using Whisper large-v3 on HuggingFace.

    Args:
        audio_base64: Audio data encoded as base64 string (WAV recommended).
        language:     Source language ISO-639-1 code (e.g. 'hi', 'ta', 'en').
                      Used as a hint to Whisper to improve accuracy.

    Returns:
        Transcribed text string, or None if the API call fails.
        Returning None triggers graceful text-mode fallback in the frontend.

    HuggingFace Inference API:
        POST https://api-inference.huggingface.co/models/openai/whisper-large-v3
        Headers: Authorization: Bearer <token>, Content-Type: audio/wav
        Body:    raw audio bytes
        Returns: {"text": "transcribed text"}
    """
    if not HUGGINGFACE_API_KEY:
        logger.warning(
            "HUGGINGFACE_API_KEY not set — STT unavailable. "
            "Add it to .env (get free at https://huggingface.co/settings/tokens)."
        )
        return None

    try:
        # Decode base64 → raw audio bytes
        audio_bytes = base64.b64decode(audio_base64)

        url = f"{HF_INFERENCE_URL}/{HF_STT_MODEL}"
        headers = _hf_audio_headers()

        # Optional: pass language hint as query parameter
        lang_hint = WHISPER_LANG_HINTS.get(language, "")
        params = {"language": lang_hint} if lang_hint else {}

        logger.info("Calling HuggingFace Whisper STT (lang=%s)...", language)

        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            response = client.post(url, content=audio_bytes, headers=headers, params=params)

            # Handle 503 "model loading" — HuggingFace cold-start
            if response.status_code == 503:
                estimated_wait = response.json().get("estimated_time", 20)
                logger.warning(
                    "Whisper model is loading (estimated wait: %.0fs). "
                    "Retrying once after short delay...", estimated_wait
                )
                time.sleep(min(estimated_wait, 15))  # Wait max 15s then retry once
                response = client.post(url, content=audio_bytes, headers=headers, params=params)

            response.raise_for_status()

        result = response.json()
        transcription = result.get("text", "").strip()

        if transcription:
            logger.info("STT transcription: '%s...'", transcription[:60])
            return transcription
        else:
            logger.warning("Whisper returned empty transcription.")
            return None

    except httpx.TimeoutException:
        logger.warning(
            "HuggingFace STT request timed out. The model may be cold-starting. "
            "Voice input unavailable — user can type instead."
        )
        return None
    except httpx.HTTPStatusError as e:
        logger.warning("HuggingFace STT HTTP error %s: %s", e.response.status_code, e.response.text[:200])
        return None
    except Exception as e:
        logger.warning("HuggingFace STT failed: %s", e)
        return None


# ── Text-to-Speech (Facebook MMS-TTS) ────────────────────────────────────────

def text_to_speech(
    text: str,
    language: str = "hi",
    gender: str = "female",  # Kept for API compatibility; MMS-TTS is single-voice
) -> Optional[str]:
    """
    Convert text to speech using Facebook MMS-TTS on HuggingFace.

    MMS-TTS has a dedicated model per language (e.g. facebook/mms-tts-hin for Hindi).
    Each model returns raw WAV audio bytes.

    Args:
        text:     Text to convert to speech (max ~500 chars for quality results).
        language: Target language ISO-639-1 code (e.g. 'hi', 'ta', 'en').
        gender:   Kept for API compatibility with the original Bhashini interface.
                  MMS-TTS models are single-voice — this parameter is ignored.

    Returns:
        Base64-encoded WAV audio string, or None on failure.

    HuggingFace Inference API:
        POST https://api-inference.huggingface.co/models/facebook/mms-tts-hin
        Headers: Authorization: Bearer <token>
        Body:    {"inputs": "text to speak"}
        Returns: raw WAV audio bytes
    """
    if not HUGGINGFACE_API_KEY:
        logger.warning(
            "HUGGINGFACE_API_KEY not set — TTS unavailable. "
            "Add it to .env (get free at https://huggingface.co/settings/tokens)."
        )
        return None

    # Map ISO-639-1 → MMS-TTS language suffix
    mms_lang = MMS_LANG_MAP.get(language, "hin")   # Fallback to Hindi
    model_id = f"{HF_TTS_MODEL_PREFIX}-{mms_lang}"
    url = f"{HF_INFERENCE_URL}/{model_id}"

    # Truncate to ~500 chars to avoid model limits and keep latency reasonable
    text_input = text[:500].strip()
    if not text_input:
        return None

    try:
        logger.info("Calling HuggingFace MMS-TTS (model=%s)...", model_id)

        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            response = client.post(
                url,
                json={"inputs": text_input},
                headers={
                    "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
                    "Accept": "audio/wav",
                },
            )

            # Handle 503 cold-start
            if response.status_code == 503:
                estimated_wait = response.json().get("estimated_time", 20)
                logger.warning(
                    "MMS-TTS model loading (estimated wait: %.0fs). "
                    "Retrying once...", estimated_wait
                )
                time.sleep(min(estimated_wait, 15))
                response = client.post(
                    url,
                    json={"inputs": text_input},
                    headers={
                        "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
                        "Accept": "audio/wav",
                    },
                )

            response.raise_for_status()

        # Response is raw WAV bytes — encode to base64 for JSON transport
        audio_bytes = response.content
        if not audio_bytes or len(audio_bytes) < 100:
            logger.warning("TTS returned empty or suspiciously small audio (%d bytes).", len(audio_bytes))
            return None

        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
        logger.info("TTS successful — %d bytes of audio returned.", len(audio_bytes))
        return audio_base64

    except httpx.TimeoutException:
        logger.warning(
            "HuggingFace TTS request timed out. "
            "Text response is still shown to the user."
        )
        return None
    except httpx.HTTPStatusError as e:
        logger.warning(
            "HuggingFace TTS HTTP error %s for model '%s': %s",
            e.response.status_code, model_id, e.response.text[:200],
        )
        return None
    except Exception as e:
        logger.warning("HuggingFace TTS failed: %s", e)
        return None


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("HuggingFace Voice Utils Test")
    print(f"  STT model : {HF_STT_MODEL}")
    print(f"  TTS prefix: {HF_TTS_MODEL_PREFIX}")
    print(f"  API key   : {'SET ✓' if HUGGINGFACE_API_KEY else 'NOT SET ✗'}")
    print("=" * 60)

    if not HUGGINGFACE_API_KEY:
        print("\n⚠ HUGGINGFACE_API_KEY not set in .env — skipping live API tests.")
        print("  Add your token from https://huggingface.co/settings/tokens")
    else:
        # Test TTS (Hindi)
        print("\n[TTS Test] Hindi: 'आपको बुखार के लिए डॉक्टर से सलाह लेनी चाहिए।'")
        audio = text_to_speech("आपको बुखार के लिए डॉक्टर से सलाह लेनी चाहिए।", "hi")
        print(f"  Result: {'Got audio (' + str(len(audio)) + ' base64 chars)' if audio else 'None (API unavailable)'}")

        # Test TTS (Tamil)
        print("\n[TTS Test] Tamil: 'நீங்கள் மருத்துவரை அணுகவும்.'")
        audio_ta = text_to_speech("நீங்கள் மருத்துவரை அணுகவும்.", "ta")
        print(f"  Result: {'Got audio' if audio_ta else 'None'}")

        # Test TTS (English)
        print("\n[TTS Test] English: 'Please consult a doctor for your symptoms.'")
        audio_en = text_to_speech("Please consult a doctor for your symptoms.", "en")
        print(f"  Result: {'Got audio' if audio_en else 'None'}")

        # Note: STT test requires real audio bytes — skipped in standalone mode
        print("\n[STT Test] Skipped in standalone mode (requires real audio input).")
        print("  STT is tested via the /speech-to-text endpoint in main.py.")

    print("\n" + "=" * 60)
