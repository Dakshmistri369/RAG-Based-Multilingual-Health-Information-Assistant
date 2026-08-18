"""
backend/language_utils.py
==========================
Language detection wrapper for SwasthyaSetu AI.

Primary detector  : fasttext lid.176.ftz  (176 languages, very fast)
Fallback detector : langdetect            (slower but no model file required)
Safe default      : ('en', 'English')      (returned on any failure)

Design note on code-mixed input (Hinglish):
------------------------------------------
Queries like "mujhe chest mein dard ho raha hai" (mixed Hindi grammar +
English words) are a KNOWN hard case for language detectors.  The detected
code may be 'hi', 'en', or wrong entirely.  We pass the raw detected code
to the LLM prompt but ALSO instruct the LLM to handle code-mixed input
gracefully regardless of the label — so even if the detector is wrong, the
LLM will still produce a sensible response in the dominant language the user
appears to be writing in.
"""

import logging
from typing import Tuple

from config import FASTTEXT_MODEL_PATH

logger = logging.getLogger(__name__)

# ── Language name look-up table ───────────────────────────────────────────────
# ISO 639-1 / fasttext code → human-readable name
# Used by the frontend to display the detected language to the user.
LANGUAGE_NAMES: dict[str, str] = {
    "hi": "Hindi",
    "en": "English",
    "ta": "Tamil",
    "te": "Telugu",
    "bn": "Bengali",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "ur": "Urdu",
    "or": "Odia",
    "as": "Assamese",
    "sa": "Sanskrit",
    "sd": "Sindhi",
    "ne": "Nepali",
    "bo": "Bodo",
    "kok": "Konkani",
}

# ── Lazy-loaded fasttext model ────────────────────────────────────────────────
_ft_model = None  # Loaded once on first call to avoid startup cost


def _load_fasttext_model():
    """Load the fasttext model lazily (only when first needed)."""
    global _ft_model
    if _ft_model is not None:
        return _ft_model

    try:
        import fasttext                          # type: ignore
        import os

        if not os.path.exists(FASTTEXT_MODEL_PATH):
            logger.warning(
                "FastText model not found at '%s'. "
                "Download from https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz",
                FASTTEXT_MODEL_PATH,
            )
            return None

        # Suppress fasttext's own verbose output
        fasttext.FastText.eprint = lambda *args, **kwargs: None
        _ft_model = fasttext.load_model(FASTTEXT_MODEL_PATH)
        logger.info("FastText language detection model loaded successfully.")
        return _ft_model

    except ImportError:
        logger.warning(
            "fasttext package not installed. Install with: pip install fasttext-wheel"
        )
        return None
    except Exception as exc:
        logger.warning("Failed to load fasttext model: %s", exc)
        return None


def _detect_with_fasttext(text: str) -> Tuple[str, float]:
    """
    Attempt language detection with fasttext.
    Returns (iso_code, confidence) or raises an exception.
    """
    model = _load_fasttext_model()
    if model is None:
        raise RuntimeError("FastText model unavailable")

    # fasttext expects single-line input
    clean_text = text.replace("\n", " ").strip()
    labels, probabilities = model.predict(clean_text, k=1)

    # labels look like '__label__hi' — strip prefix
    lang_code = labels[0].replace("__label__", "")
    confidence = float(probabilities[0])
    return lang_code, confidence


def _detect_with_langdetect(text: str) -> Tuple[str, float]:
    """
    Attempt language detection with langdetect (fallback).
    Returns (iso_code, 0.8 as nominal confidence) or raises.
    """
    from langdetect import detect, detect_langs  # type: ignore

    # detect_langs returns a list of Language objects with prob
    results = detect_langs(text)
    if not results:
        raise RuntimeError("langdetect returned empty result")

    top = results[0]
    return top.lang, float(top.prob)


def detect_language(text: str, min_confidence: float = 0.5) -> Tuple[str, str]:
    """
    Detect the language of *text*.

    Args:
        text:           The input string to analyse.
        min_confidence: FastText confidence threshold below which we fall back
                        to langdetect (default 0.5).

    Returns:
        Tuple of (iso_code, language_name), e.g. ('hi', 'Hindi').
        Falls back to ('en', 'English') if both detectors fail.

    Note on code-mixed (Hinglish) input:
        Hybrid queries are a known limitation of n-gram based detectors.
        Downstream, the LLM prompt includes an explicit instruction to handle
        code-mixed input gracefully, so detection errors here don't critically
        break the response — they only affect the *response language*.
    """
    if not text or not text.strip():
        return ("en", "English")

    lang_code = "en"
    confidence = 0.0

    # ── Step 1: Try fasttext (primary) ────────────────────────────────────────
    try:
        lang_code, confidence = _detect_with_fasttext(text)
        logger.debug(
            "FastText detected: %s (confidence=%.2f)", lang_code, confidence
        )

        if confidence >= min_confidence:
            lang_name = LANGUAGE_NAMES.get(lang_code, lang_code.upper())
            return (lang_code, lang_name)
        else:
            logger.debug(
                "FastText confidence %.2f < threshold %.2f — trying langdetect",
                confidence, min_confidence,
            )
    except Exception as ft_err:
        logger.debug("FastText detection failed: %s", ft_err)

    # ── Step 2: Fall back to langdetect ───────────────────────────────────────
    try:
        lang_code, confidence = _detect_with_langdetect(text)
        logger.debug(
            "langdetect detected: %s (confidence=%.2f)", lang_code, confidence
        )
        lang_name = LANGUAGE_NAMES.get(lang_code, lang_code.upper())
        return (lang_code, lang_name)

    except Exception as ld_err:
        logger.warning(
            "Both language detectors failed (fasttext: skipped/failed, "
            "langdetect: %s). Defaulting to English.",
            ld_err,
        )

    # ── Step 3: Safe default ──────────────────────────────────────────────────
    return ("en", "English")


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    test_cases = [
        ("Hello, I have a headache and fever since two days.", "Expected: en"),
        ("मुझे बुखार और सिरदर्द है, क्या करूं?", "Expected: hi"),
        ("நான் மருந்து எப்படி எடுக்கணும்?", "Expected: ta"),
        ("আমার পেটে ব্যথা হচ্ছে।", "Expected: bn"),
        ("Mujhe chest mein dard ho raha hai.", "Expected: en/hi (Hinglish)"),
        ("Aayushman Bharat yojana mein register kaise karein?", "Expected: en/hi"),
        ("ডায়াবেটিস রোগীদের জন্য কী খাওয়া উচিত?", "Expected: bn"),
        ("High fever in infant 2 months old, very worried", "Expected: en"),
    ]

    print("=" * 60)
    print("Language Detection Test Results")
    print("=" * 60)
    for text, note in test_cases:
        code, name = detect_language(text)
        print(f"\nText   : {text[:60]}{'...' if len(text) > 60 else ''}")
        print(f"Result : {code} → {name}  |  {note}")
    print("\n" + "=" * 60)
