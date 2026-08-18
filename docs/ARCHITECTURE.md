# SwasthyaSetu AI — System Architecture

## Overview

SwasthyaSetu AI is a Retrieval-Augmented Generation (RAG) system that answers health
information queries in 10+ Indian languages. The architecture is designed around three
core principles: **safety**, **accuracy**, and **accessibility**.

## System Flow Diagram

```mermaid
flowchart TD
    A([User]) -->|Text or Voice input| B

    subgraph FRONTEND["Frontend (HTML/CSS/JS)"]
        B[Chat Interface]
        B --> B1[Voice Input\nMediaRecorder API]
        B --> B2[Language Selector\nManual override]
        B --> B3[Category Filter\nOptional scoping]
    end

    B -->|POST /ask| C

    subgraph BACKEND["Backend (FastAPI — main.py)"]
        C[/ask endpoint] --> D

        subgraph PIPELINE["RAG Pipeline (rag_chain.py)"]
            D[Step 1: Language Detection\nlanguage_utils.py\nfasttext → langdetect fallback]
            D --> E

            E{Step 2: Emergency Check\nemergency_detector.py\nDETERMINISTIC rule-based\nNO LLM CALL}
            E -->|is_emergency = True| F
            E -->|is_emergency = False| G

            F[Return emergency message\n+ helpline number\nInstant - microseconds]

            G[Step 3: Retrieval\nvectorstore.py\nChromaDB + BGE-M3]
            G -->|No chunks found| H
            G -->|Chunks retrieved| I

            H[Return fallback\n'I don't know'\nNo LLM call]

            I[Step 4: Prompt Building\nSAFETY_PROMPT_TEMPLATE\n+ conversation history\n+ retrieved context]
            I --> J

            J[Step 5: LLM Generation\nMistral-7B-Instruct\nvia HuggingFaceEndpoint]
            J --> K

            K[Step 6: Update Memory\nconversation_memory.py\nIn-memory dict]
        end

        L[Voice: hf_voice_utils.py\nASR: /speech-to-text\nTTS: /text-to-speech]
        M[Location: hospital_finder.py\n/nearest-hospital\nHaversine distance]
    end

    subgraph KNOWLEDGE["Knowledge Base"]
        N[(ChromaDB\nPersistent vector store\nbackend/chroma_db/)]
        O[BAAI/bge-m3\nMultilingual embeddings\n100+ languages]
    end

    subgraph SOURCES["Source Documents (data/raw_sources/)"]
        P[WHO Fact Sheets]
        Q[ICMR Guidelines]
        R[NHP India Content]
        S[MoHFW Scheme PDFs]
    end

    subgraph INGEST["Ingestion Pipeline (run once)"]
        T[ingest.py\nPDF Loading + Chunking\nAuto-category tagging]
        T --> U[vectorstore.py\nbuild_vector_store]
        U --> N
    end

    P & Q & R & S --> T
    O --> G
    G <-->|similarity_search| N

    F & H & K --> V[Structured JSON response]
    V --> B

    style F fill:#ffe4e6,stroke:#f43f5e,color:#9f1239
    style E fill:#fef3c7,stroke:#f59e0b,color:#78350f
    style H fill:#f0fdf4,stroke:#22c55e,color:#14532d
```

## Component Descriptions

### 1. Frontend (frontend/)

| Component | Purpose |
|---|---|
| `index.html` | Main chat interface. Persistent disclaimer banner. Never dismissible. |
| `about.html` | Project info, safety guidelines, government scheme alignment. |
| `css/variables.css` | Design token system — medical blue theme, emergency red reserved for alerts only. |
| `js/chat.js` | Message sending, rendering (normal/emergency/error), session management. |
| `js/voice.js` | MediaRecorder-based audio capture → Bhashini ASR → text; Bhashini TTS → audio playback. |
| `js/languageSelector.js` | User language preference override; auto-populated from detection result. |
| `js/hospitalFinder.js` | Browser Geolocation API → /nearest-hospital endpoint → results cards. |
| `js/utils.js` | Debounce, sanitization, timestamp, audio helpers, markdown rendering. |
| `js/config.js` | API base URL, supported languages, category options. |

### 2. Backend API (backend/main.py)

FastAPI application with 6 endpoints:

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | Health check + disclaimer text |
| `/ask` | POST | Main RAG query endpoint |
| `/speech-to-text` | POST | HuggingFace Whisper ASR (voice → text) |
| `/text-to-speech` | POST | HuggingFace MMS-TTS (text → audio) |
| `/nearest-hospital` | POST | Haversine nearest facility finder |
| `/clear-session/{id}` | POST | Reset conversation memory |

### 3. Language Detection (backend/language_utils.py)

**Primary**: fasttext `lid.176.ftz` model — 176 languages, runs in microseconds.

**Fallback**: `langdetect` — used if fasttext confidence < 0.5.

**Safe default**: `('en', 'English')` returned if both fail.

**Known limitation**: Hinglish (code-mixed Hindi+English) is ambiguous for n-gram detectors. The LLM prompt explicitly instructs Gemini to handle code-mixed input gracefully regardless of the detected label.

### 4. Emergency Detector (backend/emergency_detector.py)

**Design principle**: DETERMINISTIC, rule-based matching. No LLM.

**Why**: Emergency detection must be auditable, instant, and guaranteed reliable. LLMs can be inconsistent and add latency — unacceptable on the safety critical path.

**Coverage**: 10 emergency categories with keywords in English, Hindi, Tamil, and Bengali:
1. Cardiac emergency → 108
2. Breathing difficulty/choking → 108
3. Stroke symptoms → 108
4. Severe bleeding → 108
5. Anaphylaxis → 108
6. High fever in infant → 108
7. Mental health crisis/suicidal ideation → KIRAN 1800-599-0019
8. Domestic violence → Women's Helpline 181
9. Poisoning → 108
10. Obstetric emergency → 108

### 5. Ingestion Pipeline (backend/ingest.py)

```
PDF files
  ↓ PyPDFLoader (LangChain)
Raw Document objects (one per page)
  ↓ RecursiveCharacterTextSplitter (700 chars, 120 overlap)
Chunked Documents
  ↓ auto_tag_category() (keyword matching)
Chunks with metadata: {category, source_file, page}
  ↓ Save to data/processed/chunks.json
  ↓ Return to vectorstore.py
```

**Category keyword coverage**: 8 categories × 10+ keywords each (English + Hindi equivalents):
`emergency`, `symptoms`, `prevention`, `treatment_general`, `scheme_info`, `mental_health`, `maternal_child_health`, `general`

### 6. Vector Store (backend/vectorstore.py)

**Embedding model**: `BAAI/bge-m3`
- Supports 100+ languages natively
- Cross-lingual retrieval: Hindi query → English document match (same semantic space)
- Normalized embeddings for cosine similarity

**Vector database**: ChromaDB with local persistence (`backend/chroma_db/`)
- No external database required
- Persistent across server restarts
- Supports metadata filtering (category, source)

### 7. RAG Chain (backend/rag_chain.py)

**LLM**: Mistral-7B-Instruct-v0.2 (via HuggingFace Inference API)
- Fast open-weight model with strong instruction-following capabilities
- Temperature: 0.2 (factual, low creativity)
- Max tokens: 1024

**Safety prompt constraints**:
1. Respond in detected language only
2. Use ONLY retrieved context (no outside knowledge)
3. Never give specific dosages
4. Never diagnose
5. Always recommend professional care
6. Mandatory disclaimer on every response
7. Explicitly acknowledge insufficient context
8. Use simple, jargon-free language
9. Cite source documents
10. Mention relevant government schemes where applicable

### 8. Conversation Memory (backend/conversation_memory.py)

Simple in-memory Python dict. Stores last 10 turns per session.

**Production note**: Replace with Redis or PostgreSQL for multi-instance deployment.

### 9. Hospital Finder (backend/hospital_finder.py)

Static dataset of 15 Indian hospitals/PHCs/CHCs with GPS coordinates.
Haversine formula calculates great-circle distance to user's location.

**Production upgrade path**: Replace static list with ABDM facility registry API or Google Places API.

### 10. HuggingFace Voice Integration (backend/hf_voice_utils.py)

Uses HuggingFace Inference API for multilingual voice features:
- **ASR (Speech-to-Text)**: `openai/whisper-large-v3` handles all Indian languages seamlessly.
- **TTS (Text-to-Speech)**: `facebook/mms-tts-{lang}` provides dedicated endpoints for 22+ Indian languages.

**Graceful degradation**: All HuggingFace API calls wrapped in try/except with retry logic for model cold-starts (HTTP 503). If the API remains unavailable, the app gracefully falls back to text-only mode without crashing.

## Data Flow: End-to-End Example

**Query**: "मुझे डेंगू बुखार के लक्षण बताएं" (Tell me the symptoms of dengue fever)

1. User types query in chat → `chat.js` → POST `/ask`
2. `language_utils.detect_language()` → `('hi', 'Hindi')`
3. `emergency_detector.check_emergency()` → `{is_emergency: False}` (no emergency keywords)
4. `vectorstore.get_retriever()` → similarity search in ChromaDB
5. BGE-M3 embeds "मुझे डेंगू बुखार के लक्षण बताएं" → matches WHO dengue fact sheet chunks
6. Top-5 chunks retrieved: dengue symptoms, prevention, treatment info
7. `SAFETY_PROMPT_TEMPLATE` built with: language=Hindi, context=chunks, question=query
8. Mistral-7B generates response IN HINDI based ONLY on retrieved context
9. Response includes source citation and mandatory disclaimer
10. `conversation_memory.update_history()` saves the turn
11. JSON response → `chat.js` renders bot bubble with source tags
12. Optional: TTS button lets user listen to response in Hindi via MMS-TTS

**Total latency**: ~2-5 seconds (retrieval ~0.5s + LLM ~1.5-4s)
