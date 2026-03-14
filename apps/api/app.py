"""
Flask application for PII-Anonymizer Web-CLI.
Main entry point for the web application.
"""
import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from flask_cors import CORS
try:
    from .anonymizer import PIIAnonymizer
    from .storage import MappingStorage
    from .llm_client import GroqClient
except ImportError:  # Support running as a top-level module (e.g., Railway root=apps/api)
    from anonymizer import PIIAnonymizer
    from storage import MappingStorage
    from llm_client import GroqClient

load_dotenv()

app = Flask(__name__)

# Use environment variable for secret key, or generate one if not provided
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    SECRET_KEY = os.urandom(24)
    # In production, you should set this as an environment variable
app.config['SECRET_KEY'] = SECRET_KEY

# CORS: allow any origin (Railway/public deployment friendly)
CORS(app)

ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', '').encode()
if not ENCRYPTION_KEY or ENCRYPTION_KEY == b'your_encryption_key_here':
    print("WARNING: No valid ENCRYPTION_KEY found in environment variables!")
    # In production, generate a temporary key but warn about it
    try:
        from .crypto_util import generate_key
    except ImportError:
        from crypto_util import generate_key
    ENCRYPTION_KEY = generate_key()
    print(f"Using temporary key for this session. For production, set ENCRYPTION_KEY environment variable!")
    print(f"Generated key: {ENCRYPTION_KEY.decode()}")

# Decide whether to proxy OCR requests to a remote OCR service (using DKE) or
# to handle them locally via the built-in OCR blueprint.
def _normalize_service_url(url: str) -> str:
    url = (url or '').strip()
    if url and not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url

OCR_SERVICE_URL = _normalize_service_url(os.getenv('OCR_SERVICE_URL', '').strip())
if OCR_SERVICE_URL:
    try:
        from .ocr_proxy import create_ocr_proxy_blueprint
    except ImportError:
        from ocr_proxy import create_ocr_proxy_blueprint
    print(f"Proxying OCR requests to {OCR_SERVICE_URL} using DKE encryption")
    app.register_blueprint(create_ocr_proxy_blueprint(OCR_SERVICE_URL, ENCRYPTION_KEY))
else:
    from apps.ocr.app import ocr_bp
    app.register_blueprint(ocr_bp)

def _resolve_mappings_path(path_value: str) -> str:
    """Resolve mappings file path, preferring Railway volume if provided."""
    volume_root = os.getenv('RAILWAY_VOLUME_PATH', '').strip()
    mappings_dir = os.getenv('MAPPINGS_DIR', '').strip()
    base_dir = mappings_dir or volume_root
    if base_dir and not os.path.isabs(path_value):
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, path_value)
    return path_value

MAPPINGS_FILE = _resolve_mappings_path(os.getenv('MAPPINGS_FILE', 'mappings.enc'))
MAPPING_TTL = int(os.getenv('MAPPING_TTL', '1800'))  # Default: 30 min

# Initialize components
print("Initializing PII Anonymizer...")
anonymizer = PIIAnonymizer()
print("PII Anonymizer initialized")

print("Initializing storage...")
storage = MappingStorage(MAPPINGS_FILE, ENCRYPTION_KEY, ttl_seconds=MAPPING_TTL)
print(f"Storage initialized (TTL: {storage._format_ttl(MAPPING_TTL)}, auto-cleanup: active)")

# Initialize LLM client
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')

if GROQ_API_KEY:
    print(f"Running in API mode with Groq")
    print(f"   Model: {GROQ_MODEL}")
    print(f"   API Key: {GROQ_API_KEY[:20]}...{GROQ_API_KEY[-4:]}")
    llm_client = GroqClient(GROQ_API_KEY, GROQ_MODEL)
else:
    print("No GROQ_API_KEY found - running in mock mode")
    print("   Set GROQ_API_KEY environment variable to enable LLM features")
    llm_client = GroqClient(None, GROQ_MODEL)  # Will use mock mode

print("API Service initialized")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/anonymize', methods=['POST'])
def anonymize_text():
    """
    Enhanced anonymize endpoint with three anonymization modes.
    
    Request JSON:
        {
            "text": "Input text with PII",
            "mode": "pseudonymize|mask|replace",
            "call_llm": true|false
        }
    
    Anonymization Modes:
        - pseudonymize: Creates semantic placeholders (name_1, email_1, mobNo_1, etc.)
        - mask: Intelligent partial masking preserving structure (P*** M***, +1 (555) 123-X567)
        - replace: Human-friendly labels ([Person Name], [Email Address], [Phone Number])
    
    Response JSON:
        {
            "anonymized_text": "...",
            "entity_mappings": {...},
            "llm_response": "...",  (if call_llm=true)
            "llm_response_anonymized": "...",  (if call_llm=true)
            "deanonymized_output": "...",  (if call_llm=true)
            "mappings_count": 5
        }
    """
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400
        
        text = data['text'].strip()
        if not text:
            return jsonify({'error': 'Empty text provided'}), 400
        
        # Support both 'action' and 'mode' for backward compatibility
        mode = data.get('mode', data.get('action', 'pseudonymize'))
        if mode == 'anonymize':  # Map old 'anonymize' to 'pseudonymize'
            mode = 'pseudonymize'
        
        call_llm = data.get('call_llm', False)
        context_prompt = data.get('context_prompt', '').strip()
        
        print(f"Processing text (length: {len(text)}, mode: {mode})")
        if context_prompt:
            print(f"Context prompt provided: {context_prompt[:100]}...")
        
        # Use the appropriate anonymization method based on mode
        if mode == 'mask':
            anonymized_text, mappings = anonymizer.mask(text)
            print(f"Using mask mode (irreversible)")
        elif mode == 'replace':
            anonymized_text, mappings = anonymizer.replace(text)
            print(f"Using replace mode (irreversible)")
        else:  # Default to pseudonymize
            anonymized_text, mappings = anonymizer.pseudonymize(text)
            print(f"Using pseudonymize mode (reversible)")
        
        # Store mappings for later deanonymization (only for pseudonymize mode)
        if mappings:
            storage.add_mappings(mappings)
            print(f"Stored {len(mappings)} entity mappings")
        else:
            print(f"No mappings stored - {mode} mode is irreversible")
        
        response_data = {
            'anonymized_text': anonymized_text,
            'entity_mappings': mappings,  # Include mappings in response
            'mappings_count': len(mappings),
            'mode': mode,
            'reversible': len(mappings) > 0
        }
        
        if call_llm and llm_client:
            print("Calling LLM with anonymized text...")
            # Build LLM prompt including context prompt if provided
            if context_prompt:
                llm_prompt = (f"User's request/context: {context_prompt}\n\n"
                              f"Below is the relevant information (with PII anonymized):\n\n{anonymized_text}\n\n"
                              f"Please respond to the user's request above using the anonymized information provided.")
            else:
                llm_prompt = f"Please respond to the following message:\n\n{anonymized_text}"
            llm_response = llm_client.generate_response(llm_prompt)
            print(f"LLM response received (length: {len(llm_response)})")
            
            # Deanonymize the LLM response (only works if mappings exist)
            if mappings:
                deanonymized_output = anonymizer.deanonymize(llm_response, mappings)
            else:
                deanonymized_output = llm_response  # Can't deanonymize mask/replace
                print(f"LLM response cannot be deanonymized ({mode} mode is irreversible)")
            
            response_data.update({
                'llm_response': llm_response,  # Keep original name for compatibility
                'llm_response_anonymized': llm_response,
                'deanonymized_output': deanonymized_output
            })
        
        return jsonify(response_data)
    
    except Exception as e:
        print(f"Error in anonymize_text: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/api/deanonymize', methods=['POST'])
def deanonymize_text():
    """
    Deanonymize text using stored mappings.
    
    Request JSON:
        {
            "text": "Anonymized text"
        }
    
    Response JSON:
        {
            "deanonymized_text": "..."
        }
    """
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400
        
        text = data['text']
        
        # Load stored mappings
        mappings = storage.load_mappings()
        
        # Deanonymize
        deanonymized_text = anonymizer.deanonymize(text, mappings)
        
        return jsonify({
            'deanonymized_text': deanonymized_text,
            'mappings_used': len(mappings)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/clear-mappings', methods=['POST'])
def clear_mappings():
    """Clear all stored mappings immediately (secure wipe)."""
    try:
        storage.clear_mappings()
        return jsonify({'message': 'Mappings cleared and securely wiped'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/storage-info', methods=['GET'])
def storage_info():
    """Return storage health and TTL information."""
    try:
        info = storage.get_storage_info()
        return jsonify(info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/set-ttl', methods=['POST'])
def set_mapping_ttl():
    """
    Update the mapping TTL (time-to-live).
    
    Request JSON:
        { "ttl_seconds": 900 }   // e.g. 15 minutes
    
    Accepted range: 60 – 86400 seconds (1 minute – 24 hours)
    """
    try:
        data = request.get_json()
        if not data or 'ttl_seconds' not in data:
            return jsonify({'error': 'Provide ttl_seconds (60-86400)'}), 400
        
        ttl = int(data['ttl_seconds'])
        storage.set_ttl_seconds(ttl)
        
        return jsonify({
            'message': f'TTL updated to {storage._format_ttl(storage.ttl_seconds)}',
            'ttl_seconds': storage.ttl_seconds
        })
    except (ValueError, TypeError):
        return jsonify({'error': 'ttl_seconds must be an integer'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Enhanced health check endpoint for production monitoring."""
    try:
        # Test anonymizer functionality
        test_result = anonymizer.detect_pii("Test John Doe")
        anonymizer_healthy = len(test_result) > 0
        
        return jsonify({
            'status': 'healthy',
            'timestamp': os.environ.get('TIMESTAMP', 'unknown'),
            'version': '2.1.0',
            'anonymizer_healthy': anonymizer_healthy,
            'llm_mode': 'mock' if (not llm_client or llm_client.mock_mode) else 'api',
            'llm_available': GROQ_API_KEY is not None,
            'mappings_file_exists': os.path.exists(MAPPINGS_FILE),
            'storage': storage.get_storage_info(),
            'environment': {
                'python_version': f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
                'has_groq_api_key': bool(GROQ_API_KEY),
                'has_encryption_key': bool(ENCRYPTION_KEY),
                'debug_mode': os.getenv('FLASK_DEBUG', 'False') == 'True'
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': os.environ.get('TIMESTAMP', 'unknown')
        }), 500


# Add a startup endpoint to verify all components
@app.route('/api/startup-check', methods=['GET'])
def startup_check():
    """Comprehensive startup check for debugging deployment issues."""
    checks = {}
    
    try:
        # Check spaCy model
        import spacy
        nlp = spacy.load('en_core_web_sm')
        checks['spacy_model'] = 'loaded'
    except Exception as e:
        checks['spacy_model'] = f'error: {str(e)}'
    
    try:
        # Check anonymizer
        test_entities = anonymizer.detect_pii("John Doe works at ACME Corp")
        checks['anonymizer'] = f'working - detected {len(test_entities)} entities'
    except Exception as e:
        checks['anonymizer'] = f'error: {str(e)}'
    
    try:
        # Check storage
        test_mappings = {'test_1': 'test_value'}
        storage.add_mappings(test_mappings)
        loaded = storage.load_mappings()
        checks['storage'] = f'working - {len(loaded)} mappings stored'
    except Exception as e:
        checks['storage'] = f'error: {str(e)}'
    
    return jsonify({
        'checks': checks,
        'environment_vars': {
            'GROQ_API_KEY': 'set' if GROQ_API_KEY else 'not set',
            'ENCRYPTION_KEY': 'set' if ENCRYPTION_KEY else 'not set',
            'MAPPINGS_FILE': MAPPINGS_FILE,
            'PORT': os.getenv('PORT', 'not set'),
            'FLASK_DEBUG': os.getenv('FLASK_DEBUG', 'not set')
        }
    })





if __name__ == '__main__':
    # Development server configuration
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.getenv('PORT', 5000))
    
    print(f"Starting Flask application...")
    print(f"   Debug mode: {debug_mode}")
    print(f"   Port: {port}")
    print(f"   Host: 0.0.0.0")
    
    app.run(
        debug=debug_mode,
        host='0.0.0.0',
        port=port
    )
