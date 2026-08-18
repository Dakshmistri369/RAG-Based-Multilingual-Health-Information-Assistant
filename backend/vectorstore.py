"""
backend/vectorstore.py
=======================
ChromaDB vector store management for SwasthyaSetu AI.

Key design decisions:
- Embedding model: BAAI/bge-m3
  This is a massively multilingual model supporting 100+ languages.
  Its crucial advantage: a Hindi query and an English document are embedded into
  the SAME semantic space, enabling cross-lingual retrieval WITHOUT needing to
  translate the query first. This is why we can answer Hindi/Tamil/Bengali
  questions using English WHO/ICMR source documents.

- Vector store: ChromaDB with persistent local storage
  Simple, file-based, no external database needed — ideal for a hackathon demo.
  In production, consider Pinecone or Weaviate for scale.

Usage (standalone — builds the index from scratch):
    cd backend/
    python vectorstore.py

Or imported in rag_chain.py:
    from vectorstore import get_retriever
    retriever = get_retriever(k=5)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain.schema import BaseRetriever, Document

# ── Path setup ────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from config import (
    CHROMA_PERSIST_DIR,
    CHROMA_COLLECTION_NAME,
    EMBEDDING_MODEL_NAME,
    DEFAULT_TOP_K,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ── Lazy-loaded singletons ────────────────────────────────────────────────────
# These are module-level singletons so the embedding model is loaded only ONCE
# per process (loading BGE-M3 can take 10–30 seconds on first run).
_embeddings: Optional[HuggingFaceEmbeddings] = None
_vector_store: Optional[Chroma] = None


def _get_embeddings() -> HuggingFaceEmbeddings:
    """
    Return (or lazily initialise) the BGE-M3 embedding function.

    BGE-M3 encode_kwargs:
    - normalize_embeddings=True: cosine similarity-ready output, which is what
      ChromaDB uses by default and gives better retrieval quality.
    """
    global _embeddings
    if _embeddings is None:
        logger.info(
            "Loading embedding model '%s' (may take 10-30s on first run)...",
            EMBEDDING_MODEL_NAME,
        )
        _embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL_NAME,
            encode_kwargs={"normalize_embeddings": True},
        )
        logger.info("Embedding model loaded successfully.")
    return _embeddings


def build_vector_store(documents: list[Document]) -> Chroma:
    """
    Create or overwrite the ChromaDB vector store from the given documents.

    This function should be called once after ingest.py has produced chunks.
    It embeds all chunks using BGE-M3 and persists them to disk.

    Args:
        documents: List of LangChain Documents (from ingest.run_ingest()).

    Returns:
        Initialised Chroma vector store instance.
    """
    global _vector_store

    if not documents:
        raise ValueError(
            "No documents provided to build_vector_store. "
            "Run ingest.py first to generate source chunks."
        )

    logger.info(
        "Building vector store with %d chunks → '%s'",
        len(documents), CHROMA_PERSIST_DIR,
    )

    embeddings = _get_embeddings()

    # Chroma.from_documents() creates the collection and persists automatically
    _vector_store = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=CHROMA_PERSIST_DIR,
        collection_name=CHROMA_COLLECTION_NAME,
    )

    # Log collection size for verification
    count = _vector_store._collection.count()
    logger.info(
        "Vector store built successfully. Collection '%s' now has %d vectors.",
        CHROMA_COLLECTION_NAME, count,
    )
    return _vector_store


def get_vector_store() -> Chroma:
    """
    Return (or lazily load) the existing ChromaDB vector store from disk.

    Raises FileNotFoundError if the store hasn't been built yet.
    """
    global _vector_store
    if _vector_store is not None:
        return _vector_store

    persist_path = Path(CHROMA_PERSIST_DIR)
    if not persist_path.exists() or not any(persist_path.iterdir()):
        raise FileNotFoundError(
            f"ChromaDB store not found at '{CHROMA_PERSIST_DIR}'. "
            "Run 'python vectorstore.py' (or 'python ingest.py' first) to build it."
        )

    logger.info("Loading existing vector store from '%s'...", CHROMA_PERSIST_DIR)
    embeddings = _get_embeddings()

    _vector_store = Chroma(
        persist_directory=CHROMA_PERSIST_DIR,
        collection_name=CHROMA_COLLECTION_NAME,
        embedding_function=embeddings,
    )

    count = _vector_store._collection.count()
    logger.info(
        "Vector store loaded. Collection '%s' has %d vectors.",
        CHROMA_COLLECTION_NAME, count,
    )
    return _vector_store


def get_retriever(
    category_filter: Optional[str] = None,
    k: int = DEFAULT_TOP_K,
) -> BaseRetriever:
    """
    Return a LangChain retriever backed by the vector store.

    Args:
        category_filter: If provided, retrieves only chunks matching this
                         category in their metadata (e.g. 'symptoms', 'scheme_info').
                         Useful for scoped retrieval when the query category is known.
        k:               Number of chunks to retrieve per query.

    Returns:
        LangChain BaseRetriever ready to use in a chain or standalone.

    Example:
        retriever = get_retriever(k=5)
        docs = retriever.invoke("What are symptoms of dengue?")
    """
    store = get_vector_store()

    search_kwargs: dict = {"k": k}
    if category_filter:
        search_kwargs["filter"] = {"category": category_filter}
        logger.debug(
            "Retriever configured with category filter: '%s', k=%d",
            category_filter, k,
        )
    else:
        logger.debug("Retriever configured: k=%d (no category filter)", k)

    return store.as_retriever(search_kwargs=search_kwargs)


def similarity_search_with_score(
    query: str,
    k: int = DEFAULT_TOP_K,
    category_filter: Optional[str] = None,
) -> list[tuple[Document, float]]:
    """
    Direct similarity search returning documents with their distance scores.
    Useful for debugging retrieval quality.

    Returns:
        List of (Document, score) tuples. Lower score = more similar (L2 distance).
    """
    store = get_vector_store()
    filter_dict = {"category": category_filter} if category_filter else None
    return store.similarity_search_with_score(query, k=k, filter=filter_dict)


# ── Standalone build mode ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Build the SwasthyaSetu AI vector store from ingested chunks."
    )
    parser.add_argument(
        "--test-query", type=str, default=None,
        help="Optional test query to run after building the store.",
    )
    args = parser.parse_args()

    # Import and run ingest
    from ingest import run_ingest
    docs = run_ingest()

    if not docs:
        print("\n✗ No documents ingested. Add PDFs to data/raw_sources/ first.")
        sys.exit(1)

    # Build vector store
    vs = build_vector_store(docs)
    print(f"\n✓ Vector store built with {vs._collection.count()} vectors.")

    # Optional: test retrieval
    test_q = args.test_query or "What are the symptoms of dengue fever?"
    print(f"\nTest query: '{test_q}'")
    retriever = get_retriever(k=3)
    results = retriever.invoke(test_q)

    print(f"Retrieved {len(results)} chunk(s):")
    for i, doc in enumerate(results, 1):
        print(f"\n  [{i}] Source: {doc.metadata.get('source_file', 'unknown')}")
        print(f"       Category: {doc.metadata.get('category', 'unknown')}")
        print(f"       Content: {doc.page_content[:200]}...")
