# SwasthyaSetu AI — Setup & Usage Guide

<div align="center">

## 🏥 स्वास्थ्य सेतु AI
### RAG-Based Multilingual Health Information Assistant

*Free, open-source health information in 10+ Indian languages*

**⚠️ DISCLAIMER: This is a health INFORMATION tool only — NOT a medical diagnostic system.**
**For medical emergencies, always call 108 immediately.**

</div>

---

## Features

- 🌐 **Multilingual**: Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada, Malayalam, Punjabi, English
- 🔍 **RAG-powered**: Answers grounded in WHO, ICMR, NHP India, and MoHFW documents
- 🚨 **Emergency detection**: Instant helpline routing for 10 emergency categories (rule-based, no LLM)
- 🎙️ **Voice I/O**: Speech-to-text and text-to-speech via Bhashini (Govt of India)
- 🏥 **Hospital finder**: Nearest PHC/hospital via browser geolocation
- 💊 **Scheme awareness**: Explains Ayushman Bharat, PMJAY, eSanjeevani, Jan Aushadhi
- 📱 **Mobile-first**: Works on basic smartphones via browser

---

## Quick Start

### Prerequisites

- Python 3.10 or higher
- Git
- A modern web browser

---

## Step 1: Install Python Dependencies

```bash
# Navigate to the project folder
cd swasthya-setu-ai

# Create a virtual environment (recommended)
python -m venv venv

# Activate it:
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install all dependencies
pip install -r requirements.txt
```

> **Note**: The first install downloads PyTorch and sentence-transformers,
> which can be 500MB+. Use a WiFi connection.

---

## Step 2: Download the FastText Language Detection Model

The language detection module requires the `lid.176.ftz` model file from Facebook AI.

```bash
# Download the model (about 917 KB)
# Option 1: curl
curl -L https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz -o backend/lid.176.ftz

# Option 2: wget
wget https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz -O backend/lid.176.ftz

# Option 3: Download manually from browser
# URL: https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz
# Save to: swasthya-setu-ai/backend/lid.176.ftz
```

> If this file is missing, the system automatically falls back to `langdetect`
> (slightly less accurate but functional). The app will NOT crash.

---

## Step 3: Configure Environment Variables

```bash
# Copy the template
cp .env.example .env

# Edit .env with your API keys
# Use any text editor (Notepad, VS Code, nano, etc.)
```

**Required variables in `.env`:**

```env
# -----------------------------------------------------------
# HuggingFace API Token
# Get from: https://huggingface.co/settings/tokens
# Used for: 
#   - LLM generation (mistralai/Mistral-7B-Instruct-v0.2)
#   - Speech-to-Text (Whisper large-v3) 
#   - Text-to-Speech (Facebook MMS-TTS for Indian languages)
# -----------------------------------------------------------
HUGGINGFACE_API_KEY=your_huggingface_token_here
```

> **Note**: A HuggingFace token is required for both the LLM (Mistral) and the voice features.

---

## Step 4: Add Source PDF Documents

Place health information PDFs in the appropriate subfolders:

```
data/raw_sources/
├── who_factsheets/         ← WHO disease fact sheets (see README inside)
├── icmr_guidelines/        ← ICMR health guidelines
├── nhp_content/            ← National Health Portal content
└── mohfw_schemes/          ← Government health scheme documents
```

Each subfolder has a `README.md` with specific download instructions.

**Quick start for testing**: Even 1-2 PDFs are enough to test the system.
Download any WHO fact sheet (e.g., dengue or malaria) and place it in `who_factsheets/`.

---

## Step 5: Run the Ingestion Pipeline

```bash
cd backend

# Process all PDFs and create chunks.json
python ingest.py
```

**Expected output:**
```
2024-01-01 10:00:00 [INFO] Found 5 PDF file(s) to process.
2024-01-01 10:00:01 [INFO]   Loaded 'who_dengue_factsheet.pdf' → 8 page(s)
...
2024-01-01 10:00:05 [INFO] TOTAL CHUNKS: 247
2024-01-01 10:00:05 [INFO] Saved 247 chunks to data/processed/chunks.json
```

---

## Step 6: Build the Vector Store

```bash
# Still in backend/ directory
python vectorstore.py
```

**Expected output:**
```
2024-01-01 10:01:00 [INFO] Loading embedding model 'BAAI/bge-m3'...
[First run downloads ~1.1GB model — subsequent runs are fast]
2024-01-01 10:02:00 [INFO] Embedding model loaded successfully.
2024-01-01 10:02:00 [INFO] Building vector store with 247 chunks...
2024-01-01 10:02:30 [INFO] Vector store built. Collection has 247 vectors.
```

> **First-time warning**: Downloading the BGE-M3 model takes 3-10 minutes
> depending on your internet speed. The model is cached locally after the first download.

---

## Step 7: Start the Backend Server

```bash
# Still in backend/ directory
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Expected output:**
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     SwasthyaSetu AI — Starting up
INFO:     Configuration validated successfully.
INFO:     API docs available at: http://localhost:8000/docs
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Visit **http://localhost:8000/docs** to see the interactive API documentation.

---

## Step 8: Open the Frontend

Simply open the frontend in your browser:

```
# Option 1: Direct file open
# Navigate to the file in your file explorer and double-click:
swasthya-setu-ai/frontend/index.html

# Option 2: Open from terminal
# Windows:
start frontend/index.html

# macOS:
open frontend/index.html

# Linux:
xdg-open frontend/index.html
```

> **Note**: The frontend uses ES6 modules (`import`/`export`). If you see
> CORS errors opening the file directly, use a simple local server:
> ```bash
> # In the frontend/ directory:
> python -m http.server 3000
> # Then open: http://localhost:3000
> ```

---

## Testing the System

### Test 1: Health API check
```bash
curl http://localhost:8000/
```

### Test 2: Emergency detection
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "I have severe chest pain and left arm pain", "session_id": "test-1"}'
```

### Test 3: Hindi health query
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "डेंगू बुखार के क्या लक्षण हैं?", "session_id": "test-2"}'
```

### Test 4: Out-of-scope query
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the stock price of Reliance?", "session_id": "test-3"}'
```

---

## Troubleshooting

### ❌ "FastText model not found"
**Problem**: `lid.176.ftz` not in `backend/` directory.
**Solution**: Download it following Step 2 above. The app falls back to `langdetect` automatically — language detection still works, just slightly less accurately.

---

### ❌ "ChromaDB store not found" / "Knowledge base not found"
**Problem**: Skipped Steps 5 or 6.
**Solution**: Run `python ingest.py` then `python vectorstore.py` from the `backend/` directory.

---

### ❌ "No PDF files found under data/raw_sources/"
**Problem**: No PDFs added to the source folders.
**Solution**: Add at least one PDF to any subfolder under `data/raw_sources/` (see READMEs in each subfolder for recommended sources).

---

### ❌ Voice not working / STT fails
**Problem**: HuggingFace API cold start or missing token.
**Solution**: Make sure `HUGGINGFACE_API_KEY` is set in your `.env`. If it's your first time calling the voice endpoint, HuggingFace models may be loading (can take ~20s) and the frontend will temporarily fall back to text.

---

### ❌ BGE-M3 model download very slow
**Problem**: 1.1GB model taking long to download.
**Solution**: This is a one-time download. Use a stable WiFi connection.
The model is cached in `~/.cache/huggingface/` after the first download.

---

### ❌ "HUGGINGFACE_API_KEY is not set"
**Problem**: `.env` file missing or `HUGGINGFACE_API_KEY` not filled in.
**Solution**: Get a free API key from https://huggingface.co/settings/tokens and add it to your `.env` file.

---

### ❌ CORS errors in browser (file:// protocol)
**Problem**: ES6 modules don't work via `file://` in some browsers.
**Solution**: Serve the frontend via a local HTTP server:
```bash
cd frontend/
python -m http.server 3000
```
Then access: http://localhost:3000

---

### ❌ Port 8000 already in use
**Problem**: Another process is using port 8000.
**Solution**: Change the port:
```bash
uvicorn main:app --reload --port 8001
```
And update `frontend/js/config.js`:
```js
export const API_BASE_URL = "http://localhost:8001";
```

---

## Project Structure

```
swasthya-setu-ai/
├── data/
│   ├── raw_sources/
│   │   ├── who_factsheets/      ← Add WHO PDFs here
│   │   ├── icmr_guidelines/     ← Add ICMR PDFs here
│   │   ├── nhp_content/         ← Add NHP content here
│   │   └── mohfw_schemes/       ← Add scheme PDFs here
│   └── processed/
│       └── chunks.json          ← Auto-generated by ingest.py
├── backend/
│   ├── main.py                  ← FastAPI app
│   ├── config.py                ← Environment variables
│   ├── ingest.py                ← PDF → chunks pipeline
│   ├── vectorstore.py           ← ChromaDB + BGE-M3
│   ├── language_utils.py        ← FastText + langdetect
│   ├── emergency_detector.py    ← Rule-based safety gate
│   ├── rag_chain.py             ← Mistral LLM + RAG pipeline
│   ├── hf_voice_utils.py        ← HuggingFace Whisper + MMS-TTS
│   ├── conversation_memory.py   ← Session history
│   ├── hospital_finder.py       ← Nearest facility finder
│   ├── requirements.txt
│   ├── lid.176.ftz              ← Download separately (Step 2)
│   └── chroma_db/               ← Auto-generated, gitignored
├── frontend/
│   ├── index.html               ← Main chat interface
│   ├── about.html               ← About / safety / schemes page
│   ├── css/                     ← Stylesheets
│   └── js/                      ← JavaScript modules
├── docs/
│   ├── ARCHITECTURE.md          ← System design
│   ├── SAFETY_GUIDELINES.md     ← Safety guardrails
│   └── SIH_PRESENTATION_OUTLINE.md
├── .env.example                 ← Copy to .env and fill in keys
├── .gitignore
└── requirements.txt
```

---

## Contributing

This project was built for Smart India Hackathon. For production deployment
or academic collaboration, please contact the project team.

**Important production requirements before any public deployment**:
1. Clinical audit of all emergency keywords and response messages by qualified medical professionals
2. DISHA (Digital Information Security in Healthcare Act) compliance review
3. Restriction of CORS origins to specific domain(s)
4. Addition of authentication and rate limiting
5. Replace in-memory session storage with Redis or PostgreSQL

---

## License

This project is developed for educational and hackathon purposes.
Source documents (WHO, ICMR, NHP, MoHFW) are used under their respective
open-access/government open data licenses.

---

*Built with ❤️ for India's health information access — SwasthyaSetu AI*
