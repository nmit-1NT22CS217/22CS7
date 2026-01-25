# PII-Anonymizer Web-CLI

A complete, modular Python-Flask application with **enhanced entity detection** that detects and anonymizes Personally Identifiable Information (PII) in text, supports multiple anonymization methods, stores encrypted reversible mappings, and enables deanonymization of LLM responses.

## 🔥 Latest Features (Enhanced)

- **🧠 LLM-Friendly Pseudonymization**: Uses semantic labels (`name_1`, `email_2`, `mobNo_1`) for better LLM understanding
- **🔍 Complex Entity Detection**: Handles multi-token entities with spaces, punctuation, and line breaks
- **🏷️ Industry-Standard Labels**: Human-readable entity names following data privacy standards
- **📊 Detection Analytics**: Preview and statistics for detected entities
- **🎯 Smart Validation**: Reduced false positives with type-specific validation

## Core Features

- **Enhanced PII Detection**: Advanced spaCy NER + custom patterns + regex for complex entities
- **Multiple Anonymization Modes**:
  - **Pseudonymize**: LLM-friendly labels (`name_1`, `email_2`, `physical_address_1`...)
  - **Mask**: Intelligent partial masking preserving structure (`jo****@email.com`)
  - **Replace**: Human-friendly entity type labels (`[Person Name]`, `[Email Address]`...)
- **Complex Entity Support**: Multi-word names, addresses, organizations with internal punctuation
- **Encrypted Storage**: Secure Fernet encryption for reversible mappings
- **LLM Integration**: LLM API integration with mock fallback
- **Deanonymization**: Restore original PII from LLM responses
- **Web Interface**: Clean, responsive web CLI interface

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

### 5. Run the Application

```bash
python app.py
```

**Built with ❤️ by Alex, Adit, Yashas and Rahul**
