# SwasthyaSetu AI — SIH Presentation Outline

**Event**: Smart India Hackathon (SIH)
**Theme**: MedTech / HealthTech
**Project Name**: SwasthyaSetu AI — RAG-Based Multilingual Health Information Assistant
**Tagline**: "स्वास्थ्य सेतु — Bridging Citizens to Health Knowledge"

**Recommended duration**: 8–10 minutes presentation + 5 minutes demo

---

## Slide 1: Title Slide

**Content**:
- Project Name: SwasthyaSetu AI
- Tagline: Multilingual AI-Powered Health Information for Every Indian
- Team name, institution, SIH problem statement number
- A clean screenshot of the chat interface

**Key visual**: Screenshot of the chat interface showing a Hindi health query with a clean response

---

## Slide 2: Problem Statement

**Content**:

🔴 **The Problem**:
- 1.4 billion Indians need reliable health information
- 90+ crore Indians are NOT English-proficient
- First-generation smartphone users lack access to quality health information in their language
- Misinformation and WhatsApp forwards cause health harm
- Rural citizens don't know about government health entitlements (PMJAY, eSanjeevani)

**Statistics to cite**:
- Only 10% of India's population speaks English fluently (Census)
- 65% of Indians rely on informal sources for health information (WHO India)
- 300 million people eligible for Ayushman Bharat remain unregistered

**Key visual**: Map of India showing linguistic diversity (22 scheduled languages)

---

## Slide 3: Existing Gap

**Content**:

| Existing Solution | Gap |
|---|---|
| General search engines | Not health-specific; returns unverified sources |
| English-only health apps | Excludes 90% of Indian population |
| Chatbots with no safety guardrails | Risk of dangerous medical advice |
| Telemedicine apps | Need internet + English literacy + doctor availability |
| WhatsApp health bots | No source verification; spread misinformation |

**Our solution**: A trust-first, multilingual, RAG-grounded health information assistant
with built-in safety guardrails and government scheme awareness.

---

## Slide 4: Solution Overview

**Content**:

**SwasthyaSetu AI** (स्वास्थ्य सेतु = Health Bridge):

✅ Answers health questions in **Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati,
   Kannada, Malayalam, Punjabi, and English**

✅ Uses **verified sources**: WHO fact sheets, ICMR guidelines, NHP India,
   MoHFW government scheme documents

✅ **Instantly detects emergencies** and provides correct helpline numbers (108,
   KIRAN, Women's Helpline) — no AI involvement for safety-critical responses

✅ Explains **Ayushman Bharat, PMJAY, eSanjeevani, Jan Aushadhi** entitlements

✅ **Voice-enabled** in Indian languages via HuggingFace MMS-TTS

✅ Works on **basic smartphones** — lightweight frontend, no app installation needed

---

## Slide 5: Architecture Overview

**Content**: [Insert mermaid diagram from ARCHITECTURE.md]

**Key points to narrate**:
1. "Every query goes through language detection first — so the user gets a response in THEIR language"
2. "Emergency detection is DETERMINISTIC — no AI — for maximum reliability"
3. "RAG means we only answer from verified documents — we cannot hallucinate facts we weren't given"
4. "If we don't know, we say so — rather than guessing"

**Key visual**: Simplified architecture diagram (5 boxes: User → Language Detection → Emergency Check → Retrieval → Mistral-7B → Response)

---

## Slide 6: Live Demo Script

### Demo Query 1: Normal Hindi Query
**Query**: "डेंगू बुखार के क्या लक्षण हैं और मुझे कब डॉक्टर के पास जाना चाहिए?"
*(What are the symptoms of dengue fever and when should I see a doctor?)*

**Expected outcome**:
- Language detected as Hindi
- Response in fluent Hindi
- Sources from WHO dengue fact sheet cited
- Recommends eSanjeevani if symptoms are severe
- Ends with disclaimer in Hindi

**What to highlight**: "Notice the response is in the user's language, cites its source, and recommends free government telemedicine."

---

### Demo Query 2: Emergency Query (English)
**Query**: "I have severe chest pain and my left arm is hurting"

**Expected outcome**:
- Emergency detected INSTANTLY (no loading time — no LLM call)
- Red emergency alert UI appears prominently
- "Call 108" button displayed prominently (clickable as tel: link on mobile)
- Includes first aid instructions

**What to highlight**: "This response happens in MILLISECONDS — no AI involved. We don't ask the LLM whether this is an emergency. We know it is, and we act immediately."

---

### Demo Query 3: Out-of-Scope Query
**Query**: "What is the price of iPhone 15 in India?"

**Expected outcome**:
- Language detected as English
- No emergency triggered
- No relevant chunks retrieved
- Returns pre-written fallback: "I don't have enough information in my knowledge base to answer this."
- Does NOT attempt to answer from general knowledge
- Recommends consulting a health professional (clarifying this is a health tool)

**What to highlight**: "The system knows its limits. It doesn't hallucinate. When it can't answer, it says so explicitly and tells you where to go for help."

---

### Demo Query 4 (Optional): Voice Input
- Click microphone button
- Speak: "Ayushman Bharat mein register kaise karein?" (How to register in Ayushman Bharat?)
- Show voice transcription (via Whisper large-v3) → Hindi response about PMJAY registration
- Play TTS audio response in Hindi via MMS-TTS

---

### Demo Query 5 (Optional): Hospital Finder
- Click "Find Nearest Hospital" in sidebar
- Allow location permission
- Show 3 nearest hospitals/PHCs with distances and clickable phone numbers

---

## Slide 7: Technology Stack

**Content**:

| Layer | Technology | Why Chosen |
|---|---|---|
| LLM | Mistral-7B-Instruct-v0.2 | Fast open-source model, excellent instruction following, free tier via HF |
| Embeddings | BAAI/bge-m3 | Cross-lingual retrieval — Hindi query matches English doc |
| Vector DB | ChromaDB | Local, persistent, no external service needed |
| RAG Framework | LangChain | Industry standard, modular |
| Language Detection | FastText + langdetect | 176 languages, offline, fast |
| Voice | HF Whisper v3 + MMS-TTS | High accuracy for Indian languages |
| Backend | FastAPI (Python) | Fast, async, auto-documentation |
| Frontend | HTML5 + Vanilla JS | No build step, works on any device |

**Key differentiator**: BGE-M3 embeddings enable **cross-lingual retrieval** — a Hindi question matches an English WHO document without translation. This is why the system works multilingually without maintaining separate document copies in each language.

---

## Slide 8: Government Scheme Alignment

**Content**:

| Government Initiative | How SwasthyaSetu Aligns |
|---|---|
| Ayushman Bharat Digital Mission (ABDM) | Supports ABDM's goal of digital health access for all; recommends ABHA health ID |
| eSanjeevani | Recommends free teleconsultation for health concerns requiring professional evaluation |
| Jan Aushadhi | Informs users about affordable generic medicines when appropriate |
| National Health Portal (NHP) | Uses NHP content as a primary knowledge source |
| ICMR | Uses ICMR public guidelines as authoritative health information source |
| National Digital Health Mission | Advances NDHM's citizen-facing digital health objectives |

---

## Slide 9: Safety & Ethics

**Content**:

**12 Implemented Safety Guardrails**:

1. 🚨 Deterministic emergency detection (no LLM, instant)
2. 🚫 Strict no-dosage policy in LLM prompt
3. 🚫 No-diagnosis policy in LLM prompt
4. 📚 RAG architecture prevents hallucination
5. 💬 "I don't know" fallback when context is insufficient
6. ⚕️ Mandatory disclaimer on every response
7. 💙 Sensitive mental health crisis handling (KIRAN, not generic response)
8. 🔊 Voice feature degrades gracefully (never breaks core functionality)
9. 📄 Mandatory source citation on every response
10. 🌐 Responds in user's language always
11. 🔒 Input sanitization (XSS prevention)
12. 📱 Permanent non-dismissible disclaimer banner in UI

**Ethical framing**:
- This is an INFORMATION tool, not a diagnostic system — consistent in UI, prompts, and documentation
- Built for the most vulnerable users: low health literacy, low English proficiency, rural India

---

## Slide 10: SDG Alignment

**Content**:

| SDG | Alignment |
|---|---|
| **SDG 3**: Good Health and Well-being | Democratises access to quality health information for all 1.4B Indians |
| **SDG 9**: Industry, Innovation, Infrastructure | AI-powered digital health infrastructure accessible via basic smartphones |
| **SDG 10**: Reduced Inequalities | Bridges health information gap between urban/rural, literate/non-literate, English/non-English populations |
| **SDG 4**: Quality Education | Health literacy and awareness as a form of health education |
| **SDG 17**: Partnerships | Built on government partnerships (Bhashini, NHP, ICMR, WHO) |

---

## Slide 11: Future Scope

**Content**:

**Phase 2 Enhancements (6 months)**:
- Deploy on WhatsApp via Bhashini WhatsApp bot (zero new app install required)
- ABHA health ID integration for personalised health records
- Real-time ABDM facility registry for hospital finder
- Larger knowledge base: all 22 scheduled Indian languages

**Phase 3 Enhancements (12 months)**:
- ASHA worker dashboard: enable frontline health workers to use SwasthyaSetu for community outreach
- Offline mode for low-connectivity areas (cached common queries)
- Integration with eSanjeevani for seamless handoff to teleconsultation
- Clinical validation audit of all emergency keywords and response messages

**Scale target**:
- 10 million+ monthly active users via government health portal integration
- Partnership with NHM for official deployment in PHC waiting areas (QR code access)

---

## Slide 12: Thank You + Demo Invitation

**Content**:
- "SwasthyaSetu AI — स्वास्थ्य सेतु"
- "Bridging India's 1.4 billion citizens to quality health information"
- GitHub repo link
- Team members

**Call to action for judges**: "Try asking a health question in your native language!"

**Key takeaway**: "We didn't just build a chatbot. We built a safety-first, multilingual, evidence-grounded health information system that respects the linguistic and economic diversity of India."

---

## Appendix: Possible Judge Questions & Answers

**Q: Why not use GPT-4 instead of Mistral?**
A: Mistral-7B provides excellent instruction following and can be run efficiently or accessed via free-tier endpoints like HuggingFace Inference API, making the system highly accessible and cost-effective compared to closed-source models with high token costs.

**Q: How do you prevent the AI from giving wrong medical advice?**
A: Three layers: (1) RAG — only answers from verified documents, (2) explicit prompt constraints prohibiting dosages and diagnosis, (3) "I don't know" fallback when context is insufficient.

**Q: What happens if HuggingFace API is down?**
A: The app falls back to text-only mode automatically for voice features, and returns a graceful error message for text generation. Core static features (like hospital finder and emergency detection) never depend on the LLM API.

**Q: Why build this as a web app vs. a mobile app?**
A: Progressive web apps accessible via browser work on ALL smartphones — including low-end Android phones — without requiring installation. This is critical for rural users with limited storage.

**Q: Is this HIPAA/DISHA compliant?**
A: We don't store any health data. No user health information is persisted beyond the current session. Session memory is in-memory only. Production deployment would require a DISHA compliance audit.
