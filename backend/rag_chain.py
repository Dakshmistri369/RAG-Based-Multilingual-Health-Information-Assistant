"""
backend/rag_chain.py
=====================
Core RAG pipeline for SwasthyaSetu AI.

Pipeline (in exact execution order for every query):
  1. Language detection (language_utils)
  2. Emergency check (emergency_detector) — if flagged, return IMMEDIATELY,
     skipping retrieval and LLM entirely (fastest possible safety path)
  3. Retrieve relevant chunks (vectorstore)
  4. If no chunks: return "I don't know" message without calling the LLM
     (prevents hallucination on out-of-scope queries)
  5. Build prompt from safety template + context + conversation history
  6. Call Mistral-7B via HuggingFace Inference API
  7. Return answer + source citations + detected language

Key safety constraints enforced by SAFETY_PROMPT_TEMPLATE:
  - Respond ONLY in detected/specified language
  - Use ONLY the retrieved context (no outside knowledge)
  - NEVER give specific medication dosages
  - NEVER attempt diagnosis
  - Always recommend professional consultation
  - End with a brief disclaimer
  - Cite source document names
  - Acknowledge when context is insufficient
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

from langchain_huggingface import HuggingFaceEndpoint
from langchain.prompts import PromptTemplate
from langchain.schema import Document

# ── Path setup ────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from config import HUGGINGFACE_API_KEY, HF_LLM_MODEL
from language_utils import detect_language, LANGUAGE_NAMES
from emergency_detector import check_emergency, EmergencyResult
from vectorstore import get_retriever
from conversation_memory import get_history, update_history

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── Safety-focused prompt template ────────────────────────────────────────────
# This template is the central safety enforcement mechanism.
# All constraints are listed explicitly so the LLM cannot ignore them.
# Written in English (the LLM understands English instructions) but explicitly
# instructs the LLM to respond in the user's detected language.

SAFETY_PROMPT_TEMPLATE_STR = """You are SwasthyaSetu AI, a multilingual health INFORMATION assistant for Indian citizens.

CRITICAL RULES — you MUST follow ALL of these without exception:
1. LANGUAGE: Respond ONLY in {language_name} ({language_code}). If the user wrote in Hinglish or a mix, respond in the dominant language they appear to be using. Never respond in a different language than specified.
2. KNOWLEDGE BOUNDARY: Use ONLY the information in the CONTEXT section below. Do NOT use outside knowledge, internet information, or training data not present in the context.
3. NEVER DIAGNOSE: You are an INFORMATION tool, not a doctor. Never tell the user they have a specific disease. Describe general information about conditions and symptoms only.
4. NEVER PRESCRIBE DOSES: Do NOT state specific medication dosages, drug names with quantities, or treatment schedules. Always say "consult a qualified doctor or pharmacist for correct dosage."
5. RECOMMEND PROFESSIONAL CARE: For anything that sounds serious or if the user is unwell, recommend they consult a doctor via eSanjeevani (free telemedicine) or visit their nearest PHC/hospital.
6. DISCLAIMER: End EVERY response with a brief 1-sentence disclaimer reminding the user this is general information, not a medical diagnosis.
7. HONESTY ABOUT LIMITS: If the context below does not contain sufficient information to answer the question, say clearly: "I don't have enough information in my knowledge base to answer this. Please consult a qualified health professional." Do NOT guess or invent information.
8. SIMPLE LANGUAGE: Use plain, clear language. Avoid medical jargon. If a technical term is necessary, explain it in simple words.
9. CITE SOURCES: After your answer, briefly mention the source document name(s) from the context in a line starting with "📄 Source:".
10. HOLISTIC APPROACH: Where relevant, mention relevant government health schemes (Ayushman Bharat, PMJAY, eSanjeevani, Jan Aushadhi) that could help the user.

---
CONVERSATION HISTORY (last few turns for context):
{conversation_history}

---
CONTEXT (retrieved from trusted health knowledge base):
{context}

---
USER QUESTION: {question}

---
YOUR RESPONSE (in {language_name}):"""

SAFETY_PROMPT_TEMPLATE = PromptTemplate(
    input_variables=[
        "language_name",
        "language_code",
        "conversation_history",
        "context",
        "question",
    ],
    template=SAFETY_PROMPT_TEMPLATE_STR,
)

# ── LLM setup ─────────────────────────────────────────────────────────────────
_llm: Optional[HuggingFaceEndpoint] = None


def _get_llm() -> HuggingFaceEndpoint:
    """Lazily initialise the Mistral LLM via HuggingFace."""
    global _llm
    if _llm is None:
        if not HUGGINGFACE_API_KEY:
            raise ValueError(
                "HUGGINGFACE_API_KEY is not set. Add it to your .env file. "
                "Get a free key at https://huggingface.co/settings/tokens"
            )
        _llm = HuggingFaceEndpoint(
            repo_id=HF_LLM_MODEL,
            task="text-generation",
            huggingfacehub_api_token=HUGGINGFACE_API_KEY,
            temperature=0.2,        # Low temperature = more factual, less creative
            max_new_tokens=1024,
            return_full_text=False, # Don't return the prompt in the output
        )
        logger.info("HuggingFace LLM initialised: %s", HF_LLM_MODEL)
    return _llm


# ── Helper functions ──────────────────────────────────────────────────────────

def _format_conversation_history(history: list[dict]) -> str:
    """Format conversation history into a readable string for the prompt."""
    if not history:
        return "No previous conversation."
    lines = []
    for turn in history[-5:]:  # Include only the last 5 turns to save tokens
        lines.append(f"User: {turn['question']}")
        lines.append(f"Assistant: {turn['answer'][:300]}{'...' if len(turn['answer']) > 300 else ''}")
    return "\n".join(lines)


def _format_context(docs: list[Document]) -> str:
    """Format retrieved documents into a context string for the prompt."""
    if not docs:
        return "No relevant context found."
    sections = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source_file", "unknown source")
        page = doc.metadata.get("page", "")
        page_info = f" (page {page})" if page else ""
        sections.append(
            f"[Document {i} — {source}{page_info}]\n{doc.page_content}"
        )
    return "\n\n---\n\n".join(sections)


def _extract_source_citations(docs: list[Document]) -> list[dict]:
    """Extract source metadata from retrieved documents for the API response."""
    seen = set()
    citations = []
    for doc in docs:
        source = doc.metadata.get("source_file", "unknown")
        category = doc.metadata.get("category", "general")
        page = doc.metadata.get("page", None)
        key = (source, page)
        if key not in seen:
            seen.add(key)
            citation = {"source": source, "category": category}
            if page is not None:
                citation["page"] = page
            citations.append(citation)
    return citations


def _get_fallback_message(language_code: str, language_name: str) -> str:
    """
    Return a 'no information found' message in the user's detected language.
    Uses a small lookup table for common Indian languages; defaults to English.
    This avoids calling the LLM just to produce a "don't know" message.
    """
    messages = {
        "hi": (
            "मुझे इस प्रश्न का उत्तर देने के लिए पर्याप्त जानकारी नहीं मिली। "
            "कृपया किसी योग्य डॉक्टर से सलाह लें या eSanjeevani (esanjeevaniopd.in) "
            "पर निःशुल्क टेलीकंसल्टेशन प्राप्त करें। "
            "⚠️ यह उत्तर सामान्य स्वास्थ्य जानकारी है, चिकित्सा निदान नहीं।"
        ),
        "ta": (
            "இந்த கேள்விக்கு பதிலளிக்க போதுமான தகவல் இல்லை. "
            "தகுதியான மருத்துவரை அணுகவும் அல்லது eSanjeevani மூலம் இலவச "
            "டெலிகன்சல்டேஷன் பெறவும். "
            "⚠️ இது பொது சுகாதார தகவல் மட்டுமே, மருத்துவ நோயறிதல் அல்ல।"
        ),
        "te": (
            "ఈ ప్రశ్నకు సమాధానం ఇవ్వడానికి సరిపోయిన సమాచారం నా దగ్గర లేదు. "
            "దయచేసి అర్హత కలిగిన వైద్యుడిని సంప్రదించండి. "
            "⚠️ ఇది సాధారణ ఆరోగ్య సమాచారం మాత్రమే, వైద్య నిర్ధారణ కాదు।"
        ),
        "bn": (
            "এই প্রশ্নের উত্তর দেওয়ার জন্য আমার কাছে যথেষ্ট তথ্য নেই। "
            "অনুগ্রহ করে একজন যোগ্য ডাক্তারের পরামর্শ নিন। "
            "⚠️ এটি শুধুমাত্র সাধারণ স্বাস্থ্য তথ্য, চিকিৎসা নির্ণয় নয়।"
        ),
        "mr": (
            "या प्रश्नाचे उत्तर देण्यासाठी माझ्याकडे पुरेशी माहिती नाही. "
            "कृपया पात्र डॉक्टरांचा सल्ला घ्या. "
            "⚠️ ही सामान्य आरोग्य माहिती आहे, वैद्यकीय निदान नाही।"
        ),
        "gu": (
            "આ પ્રશ્નનો જવાબ આપવા માટે મારી પાસે પૂરતી માહિતી નથી. "
            "કૃપા કરીને લાયક ડૉક્ટરની સલાહ લો. "
            "⚠️ આ સામાન્ય સ્વાસ્થ્ય માહિતી છે, તબીબી નિદાન નહીં।"
        ),
    }
    fallback_en = (
        "I don't have enough information in my knowledge base to answer this question. "
        "Please consult a qualified health professional or get a free teleconsultation "
        "through eSanjeevani at esanjeevaniopd.in. "
        "⚠️ Note: This is a general health information tool, not a medical diagnostic system."
    )
    return messages.get(language_code, fallback_en)


# ── Main generation function ───────────────────────────────────────────────────

def generate_health_response(
    question: str,
    session_id: str = "default",
    category_filter: Optional[str] = None,
) -> dict:
    """
    Generate a health information response for the given question.

    Execution order (IMPORTANT — do not reorder):
      1. Detect language
      2. Check for emergency → return immediately if detected (no LLM call)
      3. Retrieve relevant chunks from vector store
      4. If no chunks → return fallback message (no LLM call)
      5. Build prompt → call Gemini → return structured response

    Args:
        question:        The user's query text.
        session_id:      Session identifier for conversation memory.
        category_filter: Optional metadata filter to constrain retrieval
                         (e.g. 'scheme_info' for government scheme queries).

    Returns:
        dict with keys:
          - answer (str)
          - is_emergency (bool)
          - emergency_category (str | None)
          - sources (list[dict])
          - detected_language (str)   — ISO code
          - language_name (str)
          - helpline (str | None)
          - helpline_name (str | None)
    """
    logger.info("Processing query (session=%s): '%s...'", session_id, question[:60])

    # ── Step 1: Language detection ────────────────────────────────────────────
    lang_code, lang_name = detect_language(question)
    logger.info("Detected language: %s (%s)", lang_code, lang_name)

    # ── Step 2: Emergency check (DETERMINISTIC — before any LLM call) ─────────
    emergency_result = check_emergency(question, lang_code)

    if emergency_result.is_emergency:
        logger.warning(
            "EMERGENCY DETECTED (session=%s): category='%s'",
            session_id, emergency_result.category,
        )
        # Do NOT call the LLM or retriever for emergency queries.
        # The deterministic message is faster and safer than LLM output.
        return {
            "answer": emergency_result.message,
            "is_emergency": True,
            "emergency_category": emergency_result.category,
            "sources": [],
            "detected_language": lang_code,
            "language_name": lang_name,
            "helpline": emergency_result.helpline,
            "helpline_name": emergency_result.helpline_name,
        }

    # ── Step 3: Retrieve relevant chunks ──────────────────────────────────────
    try:
        retriever = get_retriever(category_filter=category_filter)
        retrieved_docs = retriever.invoke(question)
        logger.info("Retrieved %d chunk(s) for query.", len(retrieved_docs))
    except FileNotFoundError as e:
        logger.error("Vector store not found: %s", e)
        fallback = _get_fallback_message(lang_code, lang_name)
        return {
            "answer": fallback + "\n\n(Technical note: Knowledge base not found. "
                      "Run ingest.py and vectorstore.py to build it.)",
            "is_emergency": False,
            "emergency_category": None,
            "sources": [],
            "detected_language": lang_code,
            "language_name": lang_name,
            "helpline": None,
            "helpline_name": None,
        }

    # ── Step 4: No chunks found → return fallback without calling LLM ─────────
    if not retrieved_docs:
        logger.info("No relevant chunks found — returning fallback message.")
        fallback = _get_fallback_message(lang_code, lang_name)
        return {
            "answer": fallback,
            "is_emergency": False,
            "emergency_category": None,
            "sources": [],
            "detected_language": lang_code,
            "language_name": lang_name,
            "helpline": None,
            "helpline_name": None,
        }

    # ── Step 5: Build prompt and call LLM ────────────────────────────────────
    history = get_history(session_id)
    conversation_history_str = _format_conversation_history(history)
    context_str = _format_context(retrieved_docs)
    sources = _extract_source_citations(retrieved_docs)

    prompt_text = SAFETY_PROMPT_TEMPLATE.format(
        language_name=lang_name,
        language_code=lang_code,
        conversation_history=conversation_history_str,
        context=context_str,
        question=question,
    )

    try:
        llm = _get_llm()
        logger.info("Calling HuggingFace LLM (Mistral)...")
        # Ensure we just get the text content. HuggingFaceEndpoint returns a string, 
        # but invoke() might return a string directly or an AIMessage depending on LangChain version.
        response = llm.invoke(prompt_text)
        answer = response if isinstance(response, str) else response.content
        answer = answer.strip()
        logger.info("LLM response received (%d chars).", len(answer))
    except Exception as exc:
        logger.error("LLM call failed: %s", exc)
        fallback = _get_fallback_message(lang_code, lang_name)
        return {
            "answer": fallback + f"\n\n(Technical error: {str(exc)[:100]})",
            "is_emergency": False,
            "emergency_category": None,
            "sources": sources,
            "detected_language": lang_code,
            "language_name": lang_name,
            "helpline": None,
            "helpline_name": None,
        }

    # ── Update conversation memory ────────────────────────────────────────────
    update_history(session_id, question, answer)

    return {
        "answer": answer,
        "is_emergency": False,
        "emergency_category": None,
        "sources": sources,
        "detected_language": lang_code,
        "language_name": lang_name,
        "helpline": None,
        "helpline_name": None,
    }


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json

    print("=" * 70)
    print("SwasthyaSetu AI — RAG Chain Test")
    print("=" * 70)

    test_cases = [
        {
            "name": "Normal health query (English)",
            "question": "What are the symptoms of dengue fever and how can I prevent it?",
            "session_id": "test-session-1",
        },
        {
            "name": "Emergency query (English)",
            "question": "I have severe chest pain and my left arm hurts",
            "session_id": "test-session-2",
        },
        {
            "name": "Hindi query",
            "question": "डेंगू बुखार के क्या लक्षण हैं?",
            "session_id": "test-session-3",
        },
        {
            "name": "Out-of-scope query",
            "question": "What is the price of iPhone 15 in India?",
            "session_id": "test-session-4",
        },
    ]

    for tc in test_cases:
        print(f"\n{'─' * 70}")
        print(f"Test: {tc['name']}")
        print(f"Query: {tc['question']}")
        print("─" * 70)

        result = generate_health_response(
            question=tc["question"],
            session_id=tc["session_id"],
        )

        print(f"Language  : {result['language_name']} ({result['detected_language']})")
        print(f"Emergency : {result['is_emergency']}")
        if result["is_emergency"]:
            print(f"Category  : {result['emergency_category']}")
            print(f"Helpline  : {result['helpline']} ({result['helpline_name']})")
        print(f"Sources   : {result['sources']}")
        print(f"\nAnswer:\n{result['answer'][:500]}{'...' if len(result['answer']) > 500 else ''}")

    print("\n" + "=" * 70)
    print("Tests complete.")
