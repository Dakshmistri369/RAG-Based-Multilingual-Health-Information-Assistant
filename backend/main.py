"""
backend/main.py
================
FastAPI application for SwasthyaSetu AI.

Endpoints:
  GET  /                          Health check + disclaimer
  POST /ask                       Main RAG query endpoint
  POST /speech-to-text            HuggingFace Whisper large-v3 ASR
  POST /text-to-speech            HuggingFace MMS-TTS (Indian languages)
  POST /nearest-hospital          Hospital/PHC finder
  POST /clear-session/{session_id} Clear conversation memory

PRODUCTION NOTES:
-----------------
1. CORS: Currently allows all origins (allow_origins=["*"]) for the hackathon
   demo. In production, restrict to your specific frontend domain(s).
2. Authentication: No auth is implemented. In production, add JWT or API key
   authentication, especially for rate-limited external APIs like Bhashini.
3. Rate limiting: Add slowapi or similar middleware before going live.
4. Session IDs: Currently generated/managed by the frontend. In production,
   use server-side session management tied to user identity.
"""

from __future__ import annotations

import logging
import sys
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

# ── Path setup ────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from config import validate_config, LOG_LEVEL
from rag_chain import generate_health_response
from hf_voice_utils import speech_to_text, text_to_speech
from hospital_finder import find_nearest_hospitals
from conversation_memory import clear_history

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="SwasthyaSetu AI API",
    description=(
        "RAG-based Multilingual Health Information Assistant for Indian citizens. "
        "Provides general health INFORMATION only — not medical diagnosis. "
        "For emergencies call 108."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS middleware ───────────────────────────────────────────────────────────
# PRODUCTION: Replace ["*"] with specific allowed origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Allow all origins (restrict in production)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Startup validation ────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Run configuration checks on server startup and log warnings."""
    logger.info("=" * 60)
    logger.info("SwasthyaSetu AI — Starting up")
    logger.info("=" * 60)

    warnings = validate_config()
    if warnings:
        for w in warnings:
            logger.warning("CONFIG: %s", w)
    else:
        logger.info("Configuration validated successfully.")

    logger.info(
        "API docs available at: http://localhost:8000/docs"
    )


# ============================================================
# Pydantic request/response schemas
# ============================================================

class AskRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The health question to ask (in any supported Indian language or English).",
        example="What are the symptoms of dengue fever?",
    )
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Session identifier for conversation continuity. Auto-generated if not provided.",
        example="user-session-abc123",
    )
    category_filter: Optional[str] = Field(
        default=None,
        description=(
            "Optional metadata filter to restrict retrieval to a specific "
            "knowledge category. Valid values: 'symptoms', 'prevention', "
            "'treatment_general', 'emergency', 'scheme_info', 'mental_health', "
            "'maternal_child_health', 'general'."
        ),
    )

    @validator("question")
    def strip_question(cls, v: str) -> str:
        return v.strip()


class SourceCitation(BaseModel):
    source: str
    category: str
    page: Optional[int] = None


class AskResponse(BaseModel):
    answer: str = Field(..., description="The health information response.")
    is_emergency: bool = Field(
        ..., description="True if emergency keywords were detected in the query."
    )
    emergency_category: Optional[str] = Field(
        None, description="Emergency category if is_emergency is True."
    )
    sources: list[SourceCitation] = Field(
        default_factory=list,
        description="Source documents used to generate the response.",
    )
    detected_language: str = Field(
        ..., description="ISO 639-1 code of the detected query language."
    )
    language_name: str = Field(
        ..., description="Human-readable name of the detected language."
    )
    helpline: Optional[str] = Field(
        None,
        description="Emergency helpline number (populated only when is_emergency=True).",
    )
    helpline_name: Optional[str] = Field(
        None, description="Name of the emergency helpline service."
    )
    session_id: str = Field(
        ..., description="The session ID used for this query."
    )


class SpeechToTextRequest(BaseModel):
    audio_base64: str = Field(
        ...,
        description="Base64-encoded audio data (WAV or MP3 format, 16kHz recommended).",
    )
    language: str = Field(
        default="hi",
        description="ISO 639-1 language code for the spoken audio.",
        example="hi",
    )


class SpeechToTextResponse(BaseModel):
    transcribed_text: Optional[str] = Field(
        None,
        description="Transcribed text, or null if transcription failed.",
    )
    success: bool
    message: str = ""


class TextToSpeechRequest(BaseModel):
    text: str = Field(
        ...,
        max_length=1000,
        description="Text to convert to speech.",
    )
    language: str = Field(
        default="hi",
        description="ISO 639-1 language code for the output audio.",
        example="hi",
    )
    gender: str = Field(
        default="female",
        description="Voice gender: 'female' or 'male'.",
    )


class TextToSpeechResponse(BaseModel):
    audio_base64: Optional[str] = Field(
        None,
        description="Base64-encoded audio content (WAV), or null if TTS failed.",
    )
    success: bool
    message: str = ""


class NearestHospitalRequest(BaseModel):
    latitude: float = Field(
        ...,
        ge=-90, le=90,
        description="User's latitude from browser geolocation.",
        example=28.6139,
    )
    longitude: float = Field(
        ...,
        ge=-180, le=180,
        description="User's longitude from browser geolocation.",
        example=77.2090,
    )
    top_n: int = Field(
        default=3,
        ge=1, le=10,
        description="Number of nearest facilities to return.",
    )


class HospitalResult(BaseModel):
    name: str
    lat: float
    lon: float
    city: str
    state: str
    type: str
    phone: str
    address: str
    distance_km: float


class NearestHospitalResponse(BaseModel):
    hospitals: list[HospitalResult]
    count: int


class HealthCheckResponse(BaseModel):
    status: str
    version: str
    disclaimer: str
    emergency_number: str


# ============================================================
# Endpoints
# ============================================================

@app.get("/", response_model=HealthCheckResponse, tags=["System"])
async def health_check():
    """
    Health check endpoint.
    Also returns the mandatory disclaimer text for display in client applications.
    """
    return HealthCheckResponse(
        status="healthy",
        version="1.0.0",
        disclaimer=(
            "SwasthyaSetu AI provides general health INFORMATION only and is NOT "
            "a substitute for professional medical advice, diagnosis, or treatment. "
            "Always seek the advice of your physician or other qualified health "
            "provider with any questions you may have regarding a medical condition. "
            "This system is intended for informational and educational purposes only."
        ),
        emergency_number="108",
    )


@app.post("/ask", response_model=AskResponse, tags=["Chat"])
async def ask_question(request: AskRequest):
    """
    Main RAG endpoint — send a health question and receive an informed response.

    Pipeline:
    1. Detects language of the query
    2. Checks for emergency keywords (deterministic, no LLM)
    3. Retrieves relevant health information from the knowledge base
    4. Generates a safety-constrained response using Gemini 1.5 Flash
    5. Updates conversation memory for multi-turn context

    For emergencies, returns immediately with helpline information without
    calling the LLM (fastest possible safety path).
    """
    try:
        result = generate_health_response(
            question=request.question,
            session_id=request.session_id,
            category_filter=request.category_filter,
        )

        # Parse source citations into Pydantic models
        source_citations = [
            SourceCitation(**src) for src in result.get("sources", [])
        ]

        return AskResponse(
            answer=result["answer"],
            is_emergency=result["is_emergency"],
            emergency_category=result.get("emergency_category"),
            sources=source_citations,
            detected_language=result["detected_language"],
            language_name=result["language_name"],
            helpline=result.get("helpline"),
            helpline_name=result.get("helpline_name"),
            session_id=request.session_id,
        )

    except Exception as exc:
        logger.error("Unhandled error in /ask endpoint: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=(
                "An internal error occurred while processing your question. "
                "Please try again. If this persists, the knowledge base may not "
                "be built yet — run ingest.py and vectorstore.py first."
            ),
        )


@app.post("/speech-to-text", response_model=SpeechToTextResponse, tags=["Voice"])
async def speech_to_text_endpoint(request: SpeechToTextRequest):
    """
    Convert base64-encoded audio to text using Bhashini ASR.

    Supported languages: hi, ta, te, bn, mr, gu, kn, ml, pa, en
    Audio format: WAV (16kHz mono recommended).
    Model: openai/whisper-large-v3 via HuggingFace Inference API.

    Returns null transcription on API failure — the frontend
    gracefully degrades to text input mode in this case.
    """
    try:
        transcribed = speech_to_text(request.audio_base64, request.language)
        if transcribed:
            return SpeechToTextResponse(
                transcribed_text=transcribed,
                success=True,
                message="Transcription successful.",
            )
        else:
            return SpeechToTextResponse(
                transcribed_text=None,
                success=False,
                message=(
                    "Speech transcription failed or timed out. "
                    "Please type your question instead."
                ),
            )
    except Exception as exc:
        logger.error("Error in /speech-to-text: %s", exc)
        return SpeechToTextResponse(
            transcribed_text=None,
            success=False,
            message="Voice service temporarily unavailable. Please type your question.",
        )


@app.post("/text-to-speech", response_model=TextToSpeechResponse, tags=["Voice"])
async def text_to_speech_endpoint(request: TextToSpeechRequest):
    """
    Convert text to speech using Bhashini TTS.

    Supported languages: hi, ta, te, bn, mr, gu, kn, ml, pa, en
    Model: facebook/mms-tts-{lang} (MMS-TTS) via HuggingFace Inference API.
    Returns base64-encoded WAV audio, or null if TTS service is unavailable.
    Note: MMS-TTS is single-voice per language; the gender parameter is accepted
    for API compatibility but has no effect on the output.
    """
    try:
        audio = text_to_speech(request.text, request.language, request.gender)
        if audio:
            return TextToSpeechResponse(
                audio_base64=audio,
                success=True,
                message="Audio generated successfully.",
            )
        else:
            return TextToSpeechResponse(
                audio_base64=None,
                success=False,
                message="Text-to-speech service temporarily unavailable.",
            )
    except Exception as exc:
        logger.error("Error in /text-to-speech: %s", exc)
        return TextToSpeechResponse(
            audio_base64=None,
            success=False,
            message="Audio generation failed. Please read the text response.",
        )


@app.post("/nearest-hospital", response_model=NearestHospitalResponse, tags=["Facilities"])
async def nearest_hospital(request: NearestHospitalRequest):
    """
    Find the nearest hospitals, PHCs, and CHCs to the user's GPS location.

    Uses Haversine formula on a static dataset of 15 Indian health facilities.
    In production, this would query the ABDM facility registry or Google Places.

    Returns facilities sorted by distance (nearest first).
    """
    try:
        hospitals = find_nearest_hospitals(
            user_lat=request.latitude,
            user_lon=request.longitude,
            top_n=request.top_n,
        )
        return NearestHospitalResponse(
            hospitals=[HospitalResult(**h) for h in hospitals],
            count=len(hospitals),
        )
    except Exception as exc:
        logger.error("Error in /nearest-hospital: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Failed to find nearest hospitals. Please try again.",
        )


@app.post("/clear-session/{session_id}", tags=["Session"])
async def clear_session(session_id: str):
    """
    Clear the conversation history for a given session ID.

    Use this when the user starts a new conversation or wants to reset context.
    """
    was_cleared = clear_history(session_id)
    return {
        "success": True,
        "session_id": session_id,
        "message": (
            "Session cleared successfully."
            if was_cleared
            else "Session not found (may have already expired)."
        ),
    }


# ── Global exception handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception for %s %s: %s",
        request.method, request.url, exc, exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred. Please try again.",
            "type": type(exc).__name__,
        },
    )


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    from config import PORT

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        reload=True,
        log_level=LOG_LEVEL.lower(),
    )
