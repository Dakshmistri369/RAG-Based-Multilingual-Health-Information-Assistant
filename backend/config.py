"""
backend/config.py
=================
Centralised configuration and environment variable loading for SwasthyaSetu AI.
Uses python-dotenv so developers only need a .env file in the project root.

All other backend modules should import constants from here rather than
reading os.environ directly — keeps configuration in one place.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Locate and load .env ──────────────────────────────────────────────────────
# Walk up from this file's directory to find the .env file (handles running
# the app from different working directories during development).
_HERE = Path(__file__).resolve().parent          # backend/
_ROOT = _HERE.parent                             # swasthya-setu-ai/

# Try loading from project root first, then backend directory
_env_path = _ROOT / ".env"
if not _env_path.exists():
    _env_path = _HERE / ".env"

load_dotenv(dotenv_path=_env_path, override=False)

# ── LLM (Mistral via HuggingFace) ─────────────────────────────────────────────
HF_LLM_MODEL: str = "mistralai/Mistral-7B-Instruct-v0.2"

# ── HuggingFace (Speech-to-Text + Text-to-Speech) ────────────────────────────
# Get a free token at: https://huggingface.co/settings/tokens
# Used for:
#   STT → openai/whisper-large-v3  (multilingual, excellent Hindi/Tamil/Bengali)
#   TTS → facebook/mms-tts-{lang}  (MMS: Massively Multilingual Speech,
#                                    covers 22+ Indian languages)
HUGGINGFACE_API_KEY: str = os.getenv("HUGGINGFACE_API_KEY", "")

# HuggingFace Inference API base URL
HF_INFERENCE_URL: str = "https://api-inference.huggingface.co/models"

# STT model — Whisper large-v3 handles all Indian languages well
HF_STT_MODEL: str = "openai/whisper-large-v3"

# TTS model prefix — Facebook MMS-TTS per language
# Usage: HF_TTS_MODEL_PREFIX + "-" + lang_code (e.g. "facebook/mms-tts-hin")
HF_TTS_MODEL_PREFIX: str = "facebook/mms-tts"

# ── ChromaDB ─────────────────────────────────────────────────────────────────
CHROMA_PERSIST_DIR: str = os.getenv(
    "CHROMA_PERSIST_DIR",
    str(_HERE / "chroma_db"),   # Default: backend/chroma_db/
)
CHROMA_COLLECTION_NAME: str = os.getenv(
    "CHROMA_COLLECTION_NAME", "health_knowledge"
)

# ── Embedding Model ───────────────────────────────────────────────────────────
# BGE-M3 is a multilingual model from BAAI.
# It allows cross-lingual retrieval: a Hindi query can retrieve English chunks
# without needing a separate translation step, because both are embedded into
# the same multilingual vector space.
EMBEDDING_MODEL_NAME: str = "BAAI/bge-m3"

# ── Data Paths ────────────────────────────────────────────────────────────────
DATA_DIR: Path = _ROOT / "data"
RAW_SOURCES_DIR: Path = DATA_DIR / "raw_sources"
PROCESSED_DIR: Path = DATA_DIR / "processed"
CHUNKS_JSON_PATH: Path = PROCESSED_DIR / "chunks.json"

# ── FastText Language Detection Model ─────────────────────────────────────────
# Download the model from: https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz
# Place it at: backend/lid.176.ftz   OR set FASTTEXT_MODEL_PATH env variable.
FASTTEXT_MODEL_PATH: str = os.getenv(
    "FASTTEXT_MODEL_PATH",
    str(_HERE / "lid.176.ftz"),
)

# ── Text Splitter Settings ────────────────────────────────────────────────────
CHUNK_SIZE: int = 700
CHUNK_OVERLAP: int = 120

# ── Retriever Settings ────────────────────────────────────────────────────────
DEFAULT_TOP_K: int = 5

# ── Conversation Memory ───────────────────────────────────────────────────────
MAX_HISTORY_TURNS: int = 10  # Keep last N turns in memory per session

# ── Server ────────────────────────────────────────────────────────────────────
PORT: int = int(os.getenv("PORT", "8000"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ── Validation helper ─────────────────────────────────────────────────────────
def validate_config() -> list[str]:
    """
    Check that critical environment variables are set.
    Returns a list of warning messages (empty list means all OK).
    Called on startup so issues are surfaced immediately.
    """
    warnings: list[str] = []

    if not HUGGINGFACE_API_KEY:
        warnings.append(
            "HUGGINGFACE_API_KEY is not set. The /ask endpoint (Mistral LLM) and "
            "voice features (STT/TTS) will not work. Add it to your .env file."
        )
    if not Path(FASTTEXT_MODEL_PATH).exists():
        warnings.append(
            f"FastText model not found at '{FASTTEXT_MODEL_PATH}'. "
            "Download lid.176.ftz from https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz "
            "and place it in the backend/ directory. langdetect will be used as fallback."
        )

    return warnings


if __name__ == "__main__":
    issues = validate_config()
    if issues:
        print("\n[CONFIG WARNINGS]")
        for w in issues:
            print(f"  ⚠  {w}")
    else:
        print("[CONFIG] All required environment variables are set. ✓")
    print(f"\n  LLM_MODEL          : {HF_LLM_MODEL}")
    print(f"  EMBEDDING_MODEL    : {EMBEDDING_MODEL_NAME}")
    print(f"  CHROMA_DIR         : {CHROMA_PERSIST_DIR}")
    print(f"  USE_MOCK_BHASHINI  : {USE_MOCK_BHASHINI}")
    print(f"  FASTTEXT_MODEL     : {FASTTEXT_MODEL_PATH}")
