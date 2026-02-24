# PII Anonymizer 2025 (Split Services)

This repo runs **four services** locally:
- **API** (PII detect/anonymize + LLM)
- **OCR** (EasyOCR / PDF)
- **Drift** (model training + drift metrics)
- **Web** (React UI)

> The trained drift models are shipped in `apps/drift/models`.

## Prerequisites
- Python 3.11+ (3.12 works)
- Node.js 18+
- Git

## Fork + Clone
1. Fork this repo on GitHub.
2. Clone your fork:
   ```bash
   git clone <your-fork-url>
   cd PII-Anonymizer-2025-main - Copy
   ```

## Environment Files
Create these files locally (do **not** commit your keys):

### API
`apps/api/.env`
```
GROQ_API_KEY=your_groq_key_here
OCR_BASE_URL=http://127.0.0.1:5001
ENCRYPTION_KEY=your_32_byte_key_base64
```

### Drift
`apps/drift/.env`
```
GROQ_API_KEY=your_groq_key_here
```

### Web
`apps/web/.env.local`
```
VITE_API_BASE=http://127.0.0.1:5000
VITE_MODEL_BASE=http://127.0.0.1:8000
```

## Install Dependencies
### API
```bash
cd apps/api
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### OCR
```bash
cd apps/ocr
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Drift
```bash
cd apps/drift
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Web
```bash
cd apps/web
npm install
```

## Run Locally (order matters)
### 1) OCR
```bash
cd apps/ocr
python app.py
```
Runs on `http://127.0.0.1:5001`

### 2) API
```bash
cd apps/api
python app.py
```
Runs on `http://127.0.0.1:5000`

### 3) Drift
```bash
cd apps/drift
python app.py
```
Runs on `http://127.0.0.1:8000`

### 4) Web
```bash
cd apps/web
npm run dev -- --host localhost --port 5173
```
Open `http://127.0.0.1:5173`

## Notes
- If `/train-model` returns 500, you need more labeled samples. Add labels via the drift `/feedback` endpoint or lower the threshold with `TRAINING_MIN_SAMPLES` in `apps/drift/.env`.
- Never commit `.env` files or API keys.

## Services Map
- API: `apps/api`
- OCR: `apps/ocr`
- Drift: `apps/drift`
- Web: `apps/web`
