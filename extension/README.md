# PII Anonymizer Browser Extension

A browser extension that detects and anonymizes Personally Identifiable Information (PII) in text. Works with a deployed backend API to provide powerful NLP-based PII detection.

## 🌟 Features

- **Three Anonymization Modes:**
  - **Pseudonymize**: Reversible tokens (name_1, email_1) - can be deanonymized later
  - **Mask**: Partial hiding (J*** D***) - irreversible
  - **Replace**: Human-readable labels ([Person Name]) - irreversible

- **Context Menu Integration**: Right-click on selected text to anonymize instantly
- **LLM Integration**: Process anonymized text with AI (Groq/Llama)
- **History Tracking**: Keep track of your anonymization history
- **Cross-Platform**: Works on Chrome, Edge, and other Chromium-based browsers

## 📁 Extension Structure

```
extension/
├── manifest.json      # Extension configuration
├── popup.html         # Main extension popup UI
├── popup.css          # Popup styles
├── popup.js           # Popup logic
├── background.js      # Service worker for context menus
├── content.js         # Injected script for page interactions
├── content.css        # Styles for injected UI elements
├── options.html       # Settings page
└── icons/             # Extension icons
```

## 🚀 Installation

### Step 1: Deploy the Backend API

Before using the extension, you need to deploy the backend API.

#### Option A: Deploy to Render (Recommended - Free Tier Available)

1. Push your code to GitHub
2. Go to [render.com](https://render.com) and sign up
3. Click "New +" → "Web Service"
4. Connect your GitHub repository
5. Configure the service:
   - **Build Command**: `pip install -r requirements.txt && python -m spacy download en_core_web_sm`
   - **Start Command**: `gunicorn app:app`
6. Add environment variables in Render dashboard:
   - `ENCRYPTION_KEY`: Generate with `python -c "from crypto_util import generate_key; print(generate_key().decode())"`
   - `GROQ_API_KEY`: Your Groq API key (optional, for LLM features)
   - `ALLOWED_ORIGINS`: `chrome-extension://*`
7. Click "Create Web Service"
8. Note your deployed URL (e.g., `https://pii-anonymizer-api.onrender.com`)

#### Option B: Deploy to Railway

1. Install Railway CLI: `npm install -g @railway/cli`
2. Run `railway login` and `railway init`
3. Deploy with `railway up`
4. Set environment variables in Railway dashboard

#### Option C: Local Development

```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run the Flask app
python app.py
```
The API will be available at `http://localhost:5000`

### Step 2: Install the Extension

#### For Development/Testing:

1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top right)
3. Click "Load unpacked"
4. Select the `extension` folder from this project
5. The extension icon should appear in your toolbar

#### For Distribution:

1. Run the build script:
   ```powershell
   .\build-extension.ps1
   ```
2. This creates `dist/pii-anonymizer-extension.zip`
3. Upload to Chrome Web Store (requires developer account)

### Step 3: Configure the Extension

1. Click the extension icon in your toolbar
2. Click "⚙️ Settings" at the bottom
3. Enter your deployed API URL (e.g., `https://pii-anonymizer-api.onrender.com`)
4. Click "Test Connection" to verify
5. Click "Save Settings"

## 🎯 Usage

### Using the Popup

1. Click the extension icon
2. Paste or type text containing PII
3. Select anonymization mode
4. Optionally enable "Process with LLM"
5. Click "Anonymize"
6. Copy the result or view LLM response

### Using Context Menu

1. Select text on any webpage
2. Right-click → "🔒 PII Anonymizer"
3. Choose anonymization mode
4. Result appears in a modal overlay
5. Copy anonymized text with one click

### Deanonymizing

1. Open the extension popup
2. Click "Deanonymize" tab
3. Paste text with pseudonymize tokens (e.g., `name_1`, `email_1`)
4. Click "Deanonymize"
5. Original PII is restored from stored mappings

## 🔧 Configuration Options

### API Settings

| Setting | Description |
|---------|-------------|
| API URL | Your deployed backend URL |

### Default Preferences

| Setting | Description |
|---------|-------------|
| Default Mode | Pseudonymize, Mask, or Replace |
| Auto LLM | Automatically process with LLM |

## 🔒 Security Notes

- All PII processing happens on your deployed backend
- Mappings are encrypted with your `ENCRYPTION_KEY`
- No data is sent to third parties (except your LLM provider if configured)
- The extension only communicates with your configured API URL

## 🐛 Troubleshooting

### "Not connected to API"

1. Check that your backend is deployed and running
2. Verify the API URL in extension settings
3. Test the health endpoint: `https://your-api.com/api/health`

### "CORS Error"

1. Ensure `ALLOWED_ORIGINS` includes `chrome-extension://*`
2. Restart your backend after changing CORS settings

### "Deanonymization not working"

1. Deanonymization only works for "Pseudonymize" mode
2. Mappings must exist from a previous anonymization
3. Check that the backend hasn't restarted (clears in-memory mappings)

## 📄 API Endpoints

The extension uses these backend endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/anonymize` | POST | Anonymize text |
| `/api/deanonymize` | POST | Restore original text |
| `/api/clear-mappings` | POST | Clear stored mappings |

## 🛠️ Development

### Modifying the Extension

1. Make changes to files in `extension/` folder
2. Go to `chrome://extensions/`
3. Click the refresh icon on the extension card
4. Test your changes

### Updating Icons

1. Create PNG icons at 16x16, 48x48, and 128x128 pixels
2. Replace files in `extension/icons/` folder
3. Reload the extension

## 📝 License

MIT License - See LICENSE file for details.
