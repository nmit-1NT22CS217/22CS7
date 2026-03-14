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

**Note:** This project uses built-in Python libraries for encryption (no external cryptography library needed).

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
