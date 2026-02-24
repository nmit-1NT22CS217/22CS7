"""
Core API for PII-Anonymizer (OCR removed).
"""
import os
from pathlib import Path
from flask import Flask, request, jsonify, render_template
import requests
from dotenv import load_dotenv
from flask_cors import CORS
from anonymizer import PIIAnonymizer
from storage import MappingStorage
from llm_client import GroqClient

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=True)

app = Flask(__name__)

# Use environment variable for secret key, or generate one if not provided
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    SECRET_KEY = os.urandom(24)
app.config['SECRET_KEY'] = SECRET_KEY

# If ALLOWED_ORIGINS is set in .env, use it as a comma-separated list. Otherwise allow all origins.
allowed_origins_env = os.getenv('ALLOWED_ORIGINS', '')
if allowed_origins_env:
    allowed = [o.strip() for o in allowed_origins_env.split(',') if o.strip()]
    CORS(app, origins=allowed)
else:
    CORS(app)

ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', '').encode()
if not ENCRYPTION_KEY or ENCRYPTION_KEY == b'your_encryption_key_here':
    print("WARNING: No valid ENCRYPTION_KEY found in environment variables!")
    from crypto_util import generate_key
    ENCRYPTION_KEY = generate_key()
    print("Using temporary key for this session. For production, set ENCRYPTION_KEY environment variable!")
    print(f"Generated key: {ENCRYPTION_KEY.decode()}")

MAPPINGS_FILE = os.getenv('MAPPINGS_FILE', 'mappings.enc')

print("Initializing PII Anonymizer...")
anonymizer = PIIAnonymizer()
print("PII Anonymizer initialized")

print("Initializing storage...")
storage = MappingStorage(MAPPINGS_FILE, ENCRYPTION_KEY)
print("Storage initialized")

GROQ_API_KEY = (os.getenv('GROQ_API_KEY') or '').strip()
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')

if GROQ_API_KEY:
    print("Running in API mode with Groq")
    print(f"   Model: {GROQ_MODEL}")
    print(f"   API Key: {GROQ_API_KEY[:20]}...{GROQ_API_KEY[-4:]}")
    llm_client = GroqClient(GROQ_API_KEY, GROQ_MODEL)
else:
    print("No GROQ_API_KEY found - running in mock mode")
    print("   Set GROQ_API_KEY environment variable to enable LLM features")
    llm_client = GroqClient(None, GROQ_MODEL)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/ui')
def ui():
    return render_template('index.html')


@app.route('/api/detect', methods=['POST'])
def detect_pii():
    """Detect all PII entities in the provided text and return grouped by type."""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400

        text = data['text'].strip()
        if not text:
            return jsonify({'error': 'Empty text provided'}), 400

        entities = anonymizer.detect_pii(text)

        detected_by_label = {}
        for entity_text, entity_type, _, _ in entities:
            human_label = anonymizer.HUMAN_LABELS.get(entity_type, entity_type)
            if human_label not in detected_by_label:
                detected_by_label[human_label] = []
            detected_by_label[human_label].append(entity_text)

        sensitive_categories = {
            'Aadhaar Number', 'National ID', 'Military ID', 'Passport Number',
            'Credit Card', 'Social Security Number', 'Bank Account',
            'IBAN', 'Routing Number', 'MICR Code', 'Cheque Number'
        }

        pii_categories = []
        for label in sorted(detected_by_label.keys()):
            examples = list(dict.fromkeys(detected_by_label[label]))[:5]
            is_locked = label in sensitive_categories
            pii_categories.append({
                'label': label,
                'count': len(detected_by_label[label]),
                'examples': examples,
                'locked': is_locked
            })

        return jsonify({
            'detected_pii': detected_by_label,
            'pii_categories': pii_categories,
            'total_entities': len(entities)
        })

    except Exception as e:
        print(f"Error in detect_pii: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/api/anonymize', methods=['POST'])
def anonymize_text():
    """Enhanced anonymize endpoint with three anonymization modes."""
    try:
        data = request.get_json()

        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400

        text = data['text'].strip()
        if not text:
            return jsonify({'error': 'Empty text provided'}), 400

        mode = data.get('mode', data.get('action', 'pseudonymize'))
        if mode == 'anonymize':
            mode = 'pseudonymize'

        call_llm = data.get('call_llm', False)
        scenario = data.get('scenario', '').strip()

        print(f"Processing text (length: {len(text)}, mode: {mode})")

        allowed_labels = data.get('allowed_labels')

        if mode == 'mask':
            setattr(anonymizer, '_allowed_labels_temp', allowed_labels)
            anonymized_text, mappings = anonymizer.mask(text)
            setattr(anonymizer, '_allowed_labels_temp', None)
            print("Using mask mode (irreversible)")
        elif mode == 'replace':
            setattr(anonymizer, '_allowed_labels_temp', allowed_labels)
            anonymized_text, mappings = anonymizer.replace(text)
            setattr(anonymizer, '_allowed_labels_temp', None)
            print("Using replace mode (irreversible)")
        else:
            anonymized_text, mappings = anonymizer.pseudonymize(text, allowed_labels=allowed_labels)
            print("Using pseudonymize mode (reversible)")

        if mappings:
            storage.add_mappings(mappings)
            print(f"Stored {len(mappings)} entity mappings")
        else:
            print(f"No mappings stored - {mode} mode is irreversible")

        response_data = {
            'anonymized_text': anonymized_text,
            'entity_mappings': mappings,
            'mappings_count': len(mappings),
            'mode': mode,
            'reversible': len(mappings) > 0
        }

        if call_llm and llm_client:
            print("Calling LLM with anonymized text...")
            if scenario:
                llm_prompt = f"Scenario/Instructions: {scenario}\n\nPlease respond to the following message:\n\n{anonymized_text}"
            else:
                llm_prompt = f"Please respond to the following message:\n\n{anonymized_text}"
            llm_response = llm_client.generate_response(llm_prompt)
            print(f"LLM response received (length: {len(llm_response)})")

            if mappings:
                deanonymized_output = anonymizer.deanonymize(llm_response, mappings)
            else:
                deanonymized_output = llm_response
                print(f"LLM response cannot be deanonymized ({mode} mode is irreversible)")

            response_data.update({
                'llm_response': llm_response,
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
    """Deanonymize text using stored mappings."""
    try:
        data = request.get_json()

        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400

        text = data['text']

        mappings = storage.load_mappings()
        deanonymized_text = anonymizer.deanonymize(text, mappings)

        return jsonify({
            'deanonymized_text': deanonymized_text,
            'mappings_used': len(mappings)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/clear-mappings', methods=['POST'])
def clear_mappings():
    """Clear all stored mappings."""
    try:
        storage.clear_mappings()
        return jsonify({'message': 'Mappings cleared successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/mappings', methods=['GET'])
def list_mappings():
    """Return stored mappings."""
    try:
        mappings = storage.load_mappings()
        return jsonify({'mappings': mappings, 'count': len(mappings)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/delete-mapping', methods=['POST'])
def delete_mapping():
    """Delete a single mapping by key."""
    try:
        data = request.get_json() or {}
        key = data.get('key')
        if not key:
            return jsonify({'error': 'key is required'}), 400

        mappings = storage.load_mappings()
        if key in mappings:
            del mappings[key]
            storage.save_mappings(mappings)
        return jsonify({'message': 'mapping deleted', 'key': key})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Enhanced health check endpoint for production monitoring."""
    try:
        test_result = anonymizer.detect_pii("Test John Doe")
        anonymizer_healthy = len(test_result) > 0

        return jsonify({
            'status': 'healthy',
            'timestamp': os.environ.get('TIMESTAMP', 'unknown'),
            'version': '2.0.0',
            'anonymizer_healthy': anonymizer_healthy,
            'llm_mode': 'mock' if (not llm_client or llm_client.mock_mode) else 'api',
    'llm_available': bool(GROQ_API_KEY),
            'ocr_available': False,
            'mappings_file_exists': os.path.exists(MAPPINGS_FILE),
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


@app.route('/api/ocr', methods=['POST'])
def proxy_ocr():
    """Proxy OCR requests to the OCR service."""
    ocr_base = os.getenv('OCR_BASE_URL', '').strip().rstrip('/')
    if not ocr_base:
        return jsonify({'error': 'OCR service not configured (OCR_BASE_URL missing).'}), 501

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    files = []
    for f in request.files.getlist('file'):
        files.append(('file', (f.filename, f.stream, f.mimetype)))

    try:
        resp = requests.post(f"{ocr_base}/api/ocr", files=files, timeout=120)
        return (resp.content, resp.status_code, resp.headers.items())
    except requests.RequestException as e:
        return jsonify({'error': f'OCR service unavailable: {str(e)}'}), 502


@app.route('/api/startup-check', methods=['GET'])
def startup_check():
    """Comprehensive startup check for debugging deployment issues."""
    checks = {}

    try:
        import spacy
        _ = spacy.load('en_core_web_sm')
        checks['spacy_model'] = 'loaded'
    except Exception as e:
        checks['spacy_model'] = f'error: {str(e)}'

    try:
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
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.getenv('PORT', 5000))

    print("Starting Flask application...")
    print(f"   Debug mode: {debug_mode}")
    print(f"   Port: {port}")
    print("   Host: 0.0.0.0")

    app.run(
        debug=debug_mode,
        host='0.0.0.0',
        port=port
    )
