"""
backend/ingest.py
==================
Document ingestion pipeline for SwasthyaSetu AI.

Pipeline:
  1. Recursively load all PDFs from /data/raw_sources/ subfolders
  2. Split into chunks (700 chars, 120 overlap)
  3. Auto-tag each chunk with a health category via keyword matching
  4. Save chunks to /data/processed/chunks.json
  5. Return LangChain Document objects for direct handoff to vectorstore.py

Usage (standalone):
    cd backend/
    python ingest.py

Or import in vectorstore.py:
    from ingest import run_ingest
    documents = run_ingest()
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from tqdm import tqdm

# ── Path setup (allows running as standalone or imported) ─────────────────────
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from config import (
    RAW_SOURCES_DIR,
    PROCESSED_DIR,
    CHUNKS_JSON_PATH,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── Category keyword definitions ──────────────────────────────────────────────
# Each category has keyword lists in English AND Hindi (sometimes Tamil/Bengali)
# because some NHP India source documents are already partially in Hindi.
# Matching is done via case-insensitive substring search on the chunk text.
# Priority order matters: earlier categories take precedence on ambiguous chunks.

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "emergency": [
        # English
        "emergency", "urgent", "immediately", "life-threatening", "ambulance",
        "first aid", "critical", "severe reaction", "call 108", "hospital immediately",
        "anaphylaxis", "cardiac arrest", "seizure", "unconscious", "not breathing",
        # Hindi
        "आपातकाल", "तुरंत", "अस्पताल जाएं", "108 पर कॉल", "जानलेवा",
        "बेहोश", "दौरा",
    ],

    "symptoms": [
        # English
        "symptom", "symptoms", "sign of", "signs of", "presents with",
        "characterized by", "manifestation", "clinical feature", "complaint",
        "patient reports", "presenting complaint", "headache", "fever", "cough",
        "fatigue", "nausea", "vomiting", "diarrhea", "diarrhoea", "rash",
        "pain", "swelling", "breathlessness", "palpitation",
        # Hindi
        "लक्षण", "बुखार", "खांसी", "दर्द", "उल्टी", "दस्त", "थकान", "सूजन",
        "सिरदर्द", "मितली",
        # Tamil
        "அறிகுறி", "காய்ச்சல்",
        # Bengali
        "উপসর্গ", "জ্বর",
    ],

    "prevention": [
        # English
        "prevention", "prevent", "preventive", "prophylaxis", "vaccination",
        "immunisation", "immunization", "vaccine", "hygiene", "sanitation",
        "hand washing", "handwashing", "safe water", "vector control",
        "mosquito net", "protective measures", "screening", "health check-up",
        "lifestyle change", "avoid", "reduce risk",
        # Hindi
        "बचाव", "रोकथाम", "टीका", "टीकाकरण", "टीके", "स्वच्छता",
        "हाथ धोना", "सुरक्षा उपाय",
    ],

    "treatment_general": [
        # English
        "treatment", "therapy", "medication", "medicine", "drug", "antibiotic",
        "antiviral", "management of", "clinical management", "guideline",
        "protocol", "regimen", "dose", "dosage", "prescription", "pharmacological",
        "non-pharmacological", "recovery", "rehabilitation", "oral rehydration",
        "ORS", "wound care", "physiotherapy",
        # Hindi
        "उपचार", "दवा", "दवाई", "इलाज", "चिकित्सा", "एंटीबायोटिक", "रिकवरी",
        # Bengali
        "চিকিৎসা", "ওষুধ",
    ],

    "scheme_info": [
        # English
        "Ayushman Bharat", "PMJAY", "PM-JAY", "Pradhan Mantri",
        "eSanjeevani", "e-Sanjeevani", "National Health Mission", "NHM",
        "RSBY", "ABHA", "health ID", "digital health", "Jan Aushadhi",
        "Pradhan Mantri Bhartiya Janaushadhi", "government scheme",
        "health insurance", "beneficiary", "empanelled hospital",
        "telemedicine scheme", "PHC", "CHC", "ASHA worker", "ANM",
        "National Digital Health Mission", "NDHM", "ABDM",
        # Hindi
        "आयुष्मान भारत", "प्रधानमंत्री", "सरकारी योजना", "स्वास्थ्य बीमा",
        "ई-संजीवनी", "आभा", "जन औषधि", "लाभार्थी",
    ],

    "mental_health": [
        # English
        "mental health", "depression", "anxiety", "stress", "psychological",
        "psychiatric", "counselling", "counseling", "mental illness",
        "schizophrenia", "bipolar", "phobia", "panic attack", "PTSD",
        "trauma", "emotional wellbeing", "sleep disorder", "insomnia",
        "KIRAN helpline", "suicide prevention", "self-harm",
        "emotional support", "mindfulness", "cognitive",
        # Hindi
        "मानसिक स्वास्थ्य", "तनाव", "चिंता", "अवसाद", "मानसिक बीमारी",
        "मनोरोग", "काउंसलिंग", "नींद की समस्या",
    ],

    "maternal_child_health": [
        # English
        "pregnancy", "prenatal", "antenatal", "postnatal", "maternal",
        "newborn", "infant", "breastfeeding", "breast feeding",
        "child health", "paediatric", "pediatric", "vaccination schedule",
        "immunisation schedule", "growth monitoring", "malnutrition",
        "SAM", "MAM", "complementary feeding", "NICU", "birth",
        "labour", "labor", "delivery", "caesarean", "midwife",
        "reproductive health", "contraception", "family planning",
        # Hindi
        "गर्भावस्था", "मातृत्व", "शिशु", "स्तनपान", "बच्चे का स्वास्थ्य",
        "प्रसव", "नवजात", "टीकाकरण कार्यक्रम", "पोषण",
        # Tamil
        "கர்ப்பம்", "குழந்தை",
        # Bengali
        "গর্ভাবস্থা", "শিশু স্বাস্থ্য",
    ],

    # "general" is the catch-all — no keywords needed, applied last
    "general": [],
}


def auto_tag_category(text: str) -> str:
    """
    Assign a category to a text chunk using keyword matching.

    Checks categories in the order defined in CATEGORY_KEYWORDS.
    Returns the first category whose keywords match, or 'general' if none match.

    Args:
        text: The raw chunk text to classify.

    Returns:
        Category string, e.g. 'symptoms', 'scheme_info', 'general'.
    """
    text_lower = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if category == "general":
            continue  # Skip catch-all; applied below
        for kw in keywords:
            if kw.lower() in text_lower:
                return category
    return "general"


def load_documents_from_directory() -> list[Document]:
    """
    Recursively load all PDF files from /data/raw_sources/ and its subfolders.

    Uses LangChain's DirectoryLoader with PyPDFLoader per file.
    Returns raw (un-split) LangChain Document objects.
    """
    if not RAW_SOURCES_DIR.exists():
        logger.error(
            "Source directory not found: %s\n"
            "Create the directory and add PDFs before running ingest.",
            RAW_SOURCES_DIR,
        )
        return []

    # Find all subfolders with PDFs and TXTs
    pdf_files = list(RAW_SOURCES_DIR.rglob("*.pdf"))
    txt_files = list(RAW_SOURCES_DIR.rglob("*.txt"))
    all_files = pdf_files + txt_files
    
    if not all_files:
        logger.warning(
            "No PDF or TXT files found under %s.\n"
            "Add source documents to the subfolders (who_factsheets, icmr_guidelines, "
            "nhp_content, mohfw_schemes) and re-run ingest.py.",
            RAW_SOURCES_DIR,
        )
        return []

    logger.info("Found %d file(s) to process.", len(all_files))

    all_documents: list[Document] = []
    for filepath in tqdm(all_files, desc="Loading Files", unit="file"):
        try:
            if filepath.suffix.lower() == ".pdf":
                loader = PyPDFLoader(str(filepath))
            else:
                loader = TextLoader(str(filepath), encoding="utf-8")
            
            docs = loader.load()
            logger.info(
                "  Loaded '%s' → %d page(s)", filepath.name, len(docs)
            )
            all_documents.extend(docs)
        except Exception as exc:
            logger.warning("  Failed to load '%s': %s", filepath.name, exc)

    logger.info("Total pages loaded: %d", len(all_documents))
    return all_documents


def split_and_tag_documents(raw_docs: list[Document]) -> list[Document]:
    """
    Split raw documents into chunks and attach metadata (category, source, page).

    Args:
        raw_docs: List of LangChain Documents (one per PDF page, typically).

    Returns:
        List of chunked Documents with enriched metadata.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " "],
        length_function=len,
    )

    chunked_docs: list[Document] = []
    per_file_counts: dict[str, int] = {}

    logger.info("Splitting documents into chunks (size=%d, overlap=%d)...", CHUNK_SIZE, CHUNK_OVERLAP)
    splits = splitter.split_documents(raw_docs)

    for chunk in tqdm(splits, desc="Tagging chunks", unit="chunk"):
        # Determine source filename
        source_path = chunk.metadata.get("source", "unknown")
        source_name = Path(source_path).name if source_path != "unknown" else "unknown"
        page_num = chunk.metadata.get("page", 0)

        # Auto-tag category
        category = auto_tag_category(chunk.page_content)

        # Attach enriched metadata
        chunk.metadata["category"] = category
        chunk.metadata["source_file"] = source_name
        chunk.metadata["page"] = page_num

        chunked_docs.append(chunk)
        per_file_counts[source_name] = per_file_counts.get(source_name, 0) + 1

    # Log per-file stats
    logger.info("Chunking complete. Per-file chunk counts:")
    for filename, count in sorted(per_file_counts.items()):
        logger.info("  %-40s %4d chunks", filename, count)
    logger.info("TOTAL CHUNKS: %d", len(chunked_docs))

    return chunked_docs


def save_chunks_to_json(chunked_docs: list[Document]) -> None:
    """
    Persist chunks to /data/processed/chunks.json for inspection and debugging.

    The JSON format is a list of dicts: {page_content, metadata}.
    This is NOT used by the vector store (which stores chunks in ChromaDB),
    but is useful for auditing the ingestion quality.
    """
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    serialisable = [
        {
            "page_content": doc.page_content,
            "metadata": doc.metadata,
        }
        for doc in chunked_docs
    ]

    with open(CHUNKS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(serialisable, f, ensure_ascii=False, indent=2)

    logger.info("Saved %d chunks to %s", len(serialisable), CHUNKS_JSON_PATH)


def run_ingest() -> list[Document]:
    """
    Main entry point: load → split → tag → save.

    Returns:
        List of LangChain Documents ready for vector store ingestion.
        Returns empty list if no source PDFs are found.
    """
    logger.info("=" * 60)
    logger.info("SwasthyaSetu AI — Document Ingestion Pipeline")
    logger.info("=" * 60)

    raw_docs = load_documents_from_directory()
    if not raw_docs:
        logger.warning(
            "No documents loaded. Add PDFs to data/raw_sources/ and re-run."
        )
        return []

    chunked_docs = split_and_tag_documents(raw_docs)
    save_chunks_to_json(chunked_docs)

    # Category distribution summary
    from collections import Counter
    cat_dist = Counter(doc.metadata["category"] for doc in chunked_docs)
    logger.info("\nCategory distribution:")
    for cat, count in cat_dist.most_common():
        logger.info("  %-30s %4d", cat, count)

    logger.info("\nIngestion complete! Run vectorstore.py next to build the index.")
    return chunked_docs


if __name__ == "__main__":
    documents = run_ingest()
    print(f"\n[OK] Ingest finished. {len(documents)} chunks ready for vector store.")
    if documents:
        print(f"  Sample chunk:\n  {documents[0].page_content[:200]}...")
        print(f"  Metadata: {documents[0].metadata}")
