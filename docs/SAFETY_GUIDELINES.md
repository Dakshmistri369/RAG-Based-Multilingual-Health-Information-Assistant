# SwasthyaSetu AI — Safety Guidelines

## Overview

This document enumerates all safety guardrails implemented in SwasthyaSetu AI.
It is intended for review by SIH judges, clinical advisors, and future developers.

SwasthyaSetu AI is explicitly designed as a **health INFORMATION and EDUCATION tool**.
Every safety decision in this system stems from that fundamental framing.

---

## 1. Emergency Detection — Deterministic Rule-Based System

### What it does
Every user query is scanned for emergency keywords BEFORE any AI processing.
If a match is found, the system immediately returns helpline information WITHOUT
calling the LLM or the retrieval system.

### Why it's deterministic (not LLM-based)

| Factor | LLM Approach | Rule-Based Approach (chosen) |
|---|---|---|
| Speed | 1-5 seconds (LLM call) | < 1 millisecond |
| Reliability | Non-deterministic (same input can give different outputs) | Deterministic (same input always same output) |
| Auditability | Cannot be audited by clinical experts | Every keyword can be reviewed and approved |
| Failure mode | May miss keywords under token pressure | Cannot "forget" a keyword |
| Appropriate for safety-critical path | ❌ No | ✅ Yes |

### Emergency categories covered

| # | Category | Languages | Helpline |
|---|---|---|---|
| 1 | Cardiac emergency (chest pain, heart attack) | EN, HI, TA, BN | 108 |
| 2 | Breathing difficulty / choking | EN, HI, TA, BN | 108 |
| 3 | Stroke symptoms (FAST: face, arm, speech, time) | EN, HI, TA, BN | 108 |
| 4 | Severe bleeding / haemorrhage | EN, HI, TA, BN | 108 |
| 5 | Severe allergic reaction / anaphylaxis | EN, HI, TA, BN | 108 |
| 6 | High fever in infant (under 3 months) | EN, HI, TA, BN | 108 |
| 7 | Mental health crisis / suicidal ideation | EN, HI, TA, BN | KIRAN 1800-599-0019 |
| 8 | Domestic violence indicators | EN, HI, TA, BN | Women's Helpline 181 |
| 9 | Poisoning / accidental ingestion / snake bite | EN, HI, TA, BN | 108 |
| 10 | Obstetric emergency (pregnancy complications) | EN, HI, TA, BN | 108 |

### Implementation location
`backend/emergency_detector.py` — `check_emergency()` function, called first in `rag_chain.generate_health_response()`

---

## 2. No Medication Dosage Policy

### Rule
The AI system is **explicitly prohibited** from providing specific medication dosages,
drug quantities, or treatment schedules.

### Enforcement mechanism
The `SAFETY_PROMPT_TEMPLATE` in `rag_chain.py` contains this explicit instruction:

> "NEVER give specific medication dosages — redirect to 'consult a doctor/pharmacist'"

### Rationale
- Incorrect dosage information is directly dangerous to health
- Dosages vary by patient age, weight, comorbidities, and other factors
- Only a licensed healthcare professional can determine safe dosages
- This is a legal and ethical requirement for health information tools

---

## 3. No-Diagnosis Policy

### Rule
The AI system is **prohibited** from telling users they have a specific disease or condition.

### Enforcement mechanism
The `SAFETY_PROMPT_TEMPLATE` includes:

> "NEVER attempt diagnosis — describe general symptom/condition information only"

### How it works in practice
- ✅ Allowed: "Dengue fever typically presents with high fever, severe headache, and joint pain..."
- ❌ Prohibited: "Based on your symptoms, you have dengue fever."
- ✅ Allowed: "These symptoms are associated with several conditions. Please consult a doctor for diagnosis."

---

## 4. Knowledge Boundary Enforcement (Hallucination Prevention)

### Rule
The AI must respond ONLY using information retrieved from the knowledge base.

### Three-layer enforcement

**Layer 1: Retrieval-first architecture (RAG)**
Every response is grounded in retrieved documents. The LLM does not generate
from general training knowledge alone.

**Layer 2: Explicit prompt instruction**
```
"Answer using ONLY the provided retrieved context — no outside knowledge"
```

**Layer 3: No-retrieval fallback**
If no relevant chunks are retrieved from ChromaDB, the system returns a
pre-written "I don't know" message in the user's language — WITHOUT calling
the LLM. This prevents the LLM from fabricating answers to out-of-scope queries.

**Implementation**: `rag_chain.py` lines checking `if not retrieved_docs`

---

## 5. Mandatory Disclaimer on Every Response

### Rule
Every AI-generated response must end with a disclaimer that the information
is general and not a medical diagnosis.

### Enforcement
The `SAFETY_PROMPT_TEMPLATE` includes:

> "Always end with a brief disclaimer that this is general information, not diagnosis"

### UI reinforcement
- **Permanent disclaimer banner** at the top of the chat interface (non-dismissible)
- Every bot response shows a "⚕️ Not medical advice" indicator
- The About page contains a prominent disclaimer box

---

## 6. Mental Health Sensitivity

### Special handling
Mental health crisis detection (including suicidal ideation and self-harm) is handled
with particular care:

1. **Compassionate response tone**: The emergency message for mental health crises
   starts with "I hear you, and what you're feeling matters deeply" — not clinical
   or alarmist language.

2. **Correct helpline**: KIRAN Helpline (1800-599-0019) — Government of India,
   free, 24/7, available in 13 Indian languages — is provided, NOT general emergency 108.

3. **No AI advice for mental health crises**: When a mental health emergency is detected,
   the system returns ONLY the helpline information — no AI-generated mental health
   counselling, which would be inappropriate.

### Implementation location
`emergency_detector.py`, category `mental_health_crisis`

---

## 7. Professional Consultation Recommendation

### Rule
For any query where the user may be unwell or seeking guidance on a health issue,
the AI must recommend professional consultation.

### Enforcement
The `SAFETY_PROMPT_TEMPLATE` includes:

> "For anything suggesting seriousness, recommend eSanjeevani teleconsultation
>  or nearest health center"

### Specific recommendations provided
- **eSanjeevani** (esanjeevaniopd.in) — Free government telemedicine
- **Nearest PHC/hospital** — via the hospital finder feature
- **ABHA health ID** — for accessing government health services

---

## 8. Source Citation

### Rule
Every AI response must cite the source document(s) it used.

### Benefits
- **Transparency**: Users can verify information independently
- **Trust**: Shows the response is evidence-based
- **Accountability**: Makes the knowledge base auditable

### Implementation
Source metadata (filename, category, page number) is extracted from retrieved
chunks and returned in the API response, then displayed as source tags in the UI.

---

## 9. Language Accuracy

### Rule
The AI must respond in the user's language, not default to English.

### Implementation
- Language detected before retrieval via fasttext/langdetect
- Detected language code passed to prompt template
- Explicit instruction: "Respond ONLY in {language_name}"
- Pre-written fallback messages available in Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati
- BGE-M3 embeddings enable cross-lingual retrieval — Hindi queries match English source docs

---

## 10. CORS and API Security

### Current (Demo/Hackathon)
- CORS allows all origins (`allow_origins=["*"]`)
- No authentication on API endpoints

### Production requirements (documented)
Comments in `main.py` explicitly note:
- Restrict CORS to specific frontend domain(s)
- Add JWT or API key authentication
- Add rate limiting (slowapi or similar)
- Restrict session management to server-side authentication

---

## 11. Voice Feature Safety

### Rule
Voice features must degrade gracefully — their unavailability must NEVER affect
the core health information functionality.

### Implementation
- All Bhashini API calls wrapped in try/except
- Returns `None` (not an exception) on failure
- Frontend checks for `null` audio and silently falls back to text-only mode
- `USE_MOCK_BHASHINI=True` flag for demo reliability when govt API is down

---

## 12. Input Sanitization

### Rule
All user input must be sanitized before rendering in the DOM.

### Implementation
`frontend/js/utils.js` — `sanitizeInput()` function encodes HTML special characters
before any user content is inserted into the DOM via `innerHTML`, preventing XSS.

---

## Responsibility Matrix

| Guardrail | Enforcement Layer | Auditable? | Failure Mode |
|---|---|---|---|
| Emergency detection | Rule-based code | ✅ Yes | False positive (over-trigger) is acceptable; false negative is not possible for listed keywords |
| No dosage policy | LLM prompt + UI | Partially | LLM could theoretically ignore instruction; prompt engineering minimises risk |
| No diagnosis | LLM prompt + UI | Partially | Same as above |
| Hallucination prevention | RAG architecture + no-result fallback | ✅ Yes | Falls back to "I don't know" |
| Mandatory disclaimer | LLM prompt + UI (permanent banner) | ✅ Yes | UI banner cannot be hidden |
| Mental health handling | Rule-based emergency detection | ✅ Yes | Same reliability as emergency detection |

---

## Recommended Future Enhancements

1. **Red-teaming**: Systematic adversarial testing to find prompt injection vulnerabilities
2. **Clinical audit**: Review of emergency keyword lists and fallback messages by qualified medical professionals
3. **User feedback loop**: Flag mechanism for users to report incorrect or potentially harmful information
4. **LLM output filtering**: Post-processing filter to detect and block dosage information if LLM safety prompt is bypassed
5. **Logging for safety review**: Store all queries and responses (anonymised) for periodic safety audits
