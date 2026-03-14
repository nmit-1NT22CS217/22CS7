# PII-Anonymizer Web-CLI

A complete, modular Python-Flask application with **enhanced entity detection** that detects and anonymizes Personally Identifiable Information (PII) in text, supports multiple anonymization methods, stores encrypted reversible mappings, and enables deanonymization of LLM responses.

## Latest Features (Enhanced)

- ** LLM-Friendly Pseudonymization**: Uses semantic labels (`name_1`, `email_2`, `mobNo_1`) for better LLM understanding
- ** Complex Entity Detection**: Handles multi-token entities with spaces, punctuation, and line breaks
- ** Industry-Standard Labels**: Human-readable entity names following data privacy standards
- ** Detection Analytics**: Preview and statistics for detected entities
- ** Smart Validation**: Reduced false positives with type-specific validation

## Core Features

- ** Enhanced PII Detection**: Advanced spaCy NER + custom patterns + regex for complex entities
- ** Multiple Anonymization Modes**:
  - ** Pseudonymize**: LLM-friendly labels (`name_1`, `email_2`, `physical_address_1`...)
  - ** Mask**: Intelligent partial masking preserving structure (`jo****@email.com`)
  - ** Replace**: Human-friendly entity type labels (`[Person Name]`, `[Email Address]`...)
- ** Complex Entity Support**: Multi-word names, addresses, organizations with internal punctuation
- ** Encrypted Storage**: Secure Fernet encryption for reversible mappings
- ** LLM Integration**: LLM API integration with mock fallback
- ** Deanonymization**: Restore original PII from LLM responses
- ** Web Interface**: Clean, responsive web CLI interface

## Requirements

- Python 3.8+
- pip (Python package manager)

**Note:** This project uses the `cryptography` library for authenticated encryption.

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Download spaCy Model

```bash
python -m spacy download en_core_web_sm
```

### 3. Generate Encryption Key

```bash
python crypto_util.py
```

Copy the generated key to your `.env` file.

### 4. Configure Environment

```bash
cp .env.example .env
```


### 6. Run the Application

```bash
python app.py
```

---

## End-to-End Flow (Customer Doc → Response)

1. **Client submits input**:
   - Web UI (file upload) or API client sends either:
     - `multipart/form-data` with `file`, or
     - JSON with `base64_data` + `filename`.
   - Raw text can also be sent directly to `/api/anonymize`.
2. **API service receives request**:
   - Validates request payload and mode (`pseudonymize|mask|replace`).
   - If file-based, routes to OCR (local or remote).
3. **DKE envelope created by API (when proxying OCR)**:
   - API generates a one-time **data key** (32 bytes).
   - API encrypts the file payload with **AES-256-GCM** using the data key.
   - API encrypts the data key with the shared **master `ENCRYPTION_KEY`**.
   - API sends JSON:
     - `encrypted_payload`
     - `encrypted_data_key`
   - API sets header: `X-Encrypted-Response: true`.
4. **OCR service decrypts request**:
   - OCR service uses the shared `ENCRYPTION_KEY` to decrypt the data key.
   - OCR service uses the data key to decrypt the payload.
5. **OCR extraction pipeline**:
   - **PDF**:
     - PyMuPDF attempts direct text extraction.
     - If text is empty, each page is rendered to image and OCR is applied.
   - **Images**:
     - Pillow loads the image.
     - Tesseract extracts text via `pytesseract`.
   - OCR service returns:
     - `text`
     - `source_type`
     - `ocr_applied`
     - metadata (page count, image info).
6. **OCR response encryption (optional)**:
   - If `X-Encrypted-Response: true` was set:
     - OCR service encrypts the JSON response using DKE.
7. **API receives OCR output**:
   - If encrypted, API decrypts the response with DKE.
   - Extracted text is now plain for PII processing.
8. **PII detection (API service)**:
   - **spaCy NER** finds named entities.
   - **Regex + custom rules** find structured PII (email, phone, IDs, cards, etc.).
   - Results are merged and deduplicated.
9. **Context-aware filtering (optional)**:
   - If `context_prompt` is provided:
     - API sends detected PII list to LLM for relevance filtering.
     - Only relevant PII is kept for selective anonymization.
10. **Anonymization (API service)**:
   - `pseudonymize`: reversible tokens (`name_1`, `email_2`).
   - `mask`: irreversible partial masking.
   - `replace`: irreversible human-readable labels.
11. **Encrypted mapping storage with TTL**:
   - Reversible mappings are stored as `token -> original`.
   - Each entry gets a timestamp.
   - Entire mapping store is encrypted with AES-256-GCM.
   - Saved to `mappings.enc` (volume path if configured).
   - Background cleanup thread purges expired entries by TTL.
12. **Optional LLM call**:
   - API sends anonymized text to LLM.
   - If reversible mappings exist, API deanonymizes LLM output.
13. **Final response**:
   - Always returns anonymized text.
   - Optionally returns LLM response and deanonymized output.

## Encryption Standards and Techniques Used

- **AES-256-GCM (authenticated encryption)** for all stored mappings and payload encryption.
- **Data Key Encryption (DKE)** for OCR proxy:
  - Each request generates a one-time data key.
  - Payload is encrypted with the data key.
  - The data key is encrypted with the shared master key (`ENCRYPTION_KEY`).
- **At-rest encryption** for mapping storage (`mappings.enc`) with per-entry TTL.
- **Transport security** is provided by HTTPS in production (Railway/Cloud), while DKE adds an extra layer even over TLS.

## What Is the Various Detection Mechanism Used

- **spaCy NER** for standard entity recognition.
- **Regex-based detectors** for structured patterns (emails, phones, IDs, cards, etc.).
- **Custom pattern rules** to catch multi-token and punctuation-heavy entities.
- **Context-aware filtering** using LLM classification to keep only relevant PII (optional).

## What Is Various Anonymizing Techniques Used

- **Pseudonymize (reversible):** semantic placeholders like `name_1`, `email_2`.
- **Mask (irreversible):** partial masking while preserving structure.
- **Replace (irreversible):** human-friendly labels like `[Email Address]`.

## Multiple Strategies for Diverse Anonymisation

- **Selective Pseudonymization:** only context-relevant PII is anonymized.
- **Full Anonymization:** all detected PII is anonymized regardless of context.
- **LLM-safe placeholders:** labels are optimized for downstream LLM comprehension.

## What Kind of Middleware Layer Used

- **API Service** acts as the orchestration layer:
  - Accepts user input and files
  - Coordinates OCR and anonymization
  - Optionally calls LLM
- **OCR Proxy Blueprint** acts as a secure middleware:
  - Wraps OCR requests in DKE envelopes
  - Decrypts OCR responses before returning to clients

## How Reversible Anonymization Is Achieved

- Reversible mappings are stored as encrypted key/value pairs.
- Each mapping entry is timestamped and expires based on TTL.
- When LLM responses arrive, mappings are applied in reverse to restore original PII.
- Users can immediately wipe all mappings via the clear-mappings endpoint.

## How Is This Accessible Interface When Put Into Production

- **Web UI** hosted by the API service (`/`).
- **REST API endpoints** for programmatic usage (`/api/anonymize`, `/api/ocr/*`, `/api/deanonymize`).
- **Health endpoints** (`/api/health`, `/health`) for monitoring.
- **CORS open** for public frontends and cross-domain use.

##  Browser Extension

The PII Anonymizer is also available as a **browser extension** for Chrome, Edge, and other Chromium-based browsers!

### Extension Features

- **Popup Interface**: Anonymize text directly from the extension popup
- **Context Menu**: Right-click on selected text to anonymize instantly
- **Multiple Modes**: Pseudonymize, Mask, or Replace - same as the web app
- **History Tracking**: Keep track of your anonymization history
- **LLM Integration**: Process anonymized text with AI

#### Step 1: Install the Extension

1. Open `chrome://extensions/` in your browser
2. Enable "Developer mode" (top right)
3. Click "Load unpacked"
4. Select the `extension/` folder

#### Step 2: Configure

1. Click the extension icon → Settings
2. Enter your deployed API URL
3. Click "Test Connection" → "Save"

### Building for Distribution

```powershell
.\build-extension.ps1
```

This creates `dist/pii-anonymizer-extension.zip` for Chrome Web Store upload.


---

## Project Structure

```
fyp_01/
├── app.py                 # Flask application
├── anonymizer.py          # PII detection and anonymization
├── storage.py             # Encrypted mapping storage
├── crypto_util.py         # Encryption utilities
├── llm_client.py          # LLM client (Groq)
├── requirements.txt       # Python dependencies
├── render.yaml            # Render deployment config
├── Procfile               # Heroku/Railway config
├── templates/
│   └── index.html         # Web interface
└── extension/             # Browser extension
    ├── manifest.json      # Extension config
    ├── popup.html/css/js  # Extension popup
    ├── background.js      # Service worker
    ├── content.js/css     # Page injection
    ├── options.html       # Settings page
    └── icons/             # Extension icons
```

---

**Built with ❤️ by Alex, Adit, Yashas and Rahul**
