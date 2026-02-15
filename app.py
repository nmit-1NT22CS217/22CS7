"""
Flask application for PII-Anonymizer Web-CLI.
Main entry point for the web application.
"""
import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from flask_cors import CORS
from anonymizer import PIIAnonymizer
from storage import MappingStorage
from llm_client import GroqClient

# optional OCR dependencies (pure-Python OCR using EasyOCR + PyMuPDF)
try:
    import easyocr
    import fitz                # PyMuPDF
    from PIL import Image
    import numpy as np

    # load upfront to avoid overhead per request
    OCR_READER = easyocr.Reader(['en'], gpu=False)
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    OCR_READER = None
    # if packages are missing, /api/ocr will return an error

import io


def ocr_results_to_text(results):
    """Convert EasyOCR results into multi-line text preserving line layout.

    results: list of (bbox, text, confidence)
    Returns: string with lines separated by '\n'
    """
    if not results:
        return ''

    items = []
    heights = []
    for bbox, text, conf in results:
        # bbox is list of four points [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
        ys = [p[1] for p in bbox]
        xs = [p[0] for p in bbox]
        mid_y = sum(ys) / len(ys)
        min_x = min(xs)
        height = max(ys) - min(ys)
        items.append({'mid_y': mid_y, 'min_x': min_x, 'text': text, 'height': height})
        heights.append(height)

    avg_height = max(1.0, (sum(heights) / len(heights))) if heights else 1.0
    # threshold to group words into the same line (based on average box height)
    threshold = max(8.0, avg_height * 0.8)

    # sort items top-to-bottom
    items.sort(key=lambda x: x['mid_y'])

    lines = []
    current_line = [items[0]]
    base_y = items[0]['mid_y']

    for it in items[1:]:
        if abs(it['mid_y'] - base_y) <= threshold:
            current_line.append(it)
            # update running average for base_y
            base_y = sum(i['mid_y'] for i in current_line) / len(current_line)
        else:
            # flush current line (sort left-to-right)
            current_line.sort(key=lambda x: x['min_x'])
            lines.append(' '.join(i['text'] for i in current_line))
            current_line = [it]
            base_y = it['mid_y']

    if current_line:
        current_line.sort(key=lambda x: x['min_x'])
        lines.append(' '.join(i['text'] for i in current_line))

    return '\n'.join(lines)

load_dotenv()

app = Flask(__name__)

# Use environment variable for secret key, or generate one if not provided
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    SECRET_KEY = os.urandom(24)
    # In production, you should set this as an environment variable
app.config['SECRET_KEY'] = SECRET_KEY

# If ALLOWED_ORIGINS is set in .env, use it as a comma-separated list. Otherwise default to allow all origins (useful for GitHub Pages during testing).
allowed_origins_env = os.getenv('ALLOWED_ORIGINS', '')
if allowed_origins_env:
    allowed = [o.strip() for o in allowed_origins_env.split(',') if o.strip()]
    CORS(app, origins=allowed)
else:
    # Default: allow all origins (change in production to restrict)
    CORS(app)

ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', '').encode()
if not ENCRYPTION_KEY or ENCRYPTION_KEY == b'your_encryption_key_here':
    print("WARNING: No valid ENCRYPTION_KEY found in environment variables!")
    # In production, generate a temporary key but warn about it
    from crypto_util import generate_key
    ENCRYPTION_KEY = generate_key()
    print(f"Using temporary key for this session. For production, set ENCRYPTION_KEY environment variable!")
    print(f"Generated key: {ENCRYPTION_KEY.decode()}")

MAPPINGS_FILE = os.getenv('MAPPINGS_FILE', 'mappings.enc')

# Initialize components
print("Initializing PII Anonymizer...")
anonymizer = PIIAnonymizer()
print("PII Anonymizer initialized")

print("Initializing storage...")
storage = MappingStorage(MAPPINGS_FILE, ENCRYPTION_KEY)
print("Storage initialized")

# Initialize LLM client
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')


# ----- OCR endpoint -------------------------------------------------------
@app.route('/api/ocr', methods=['POST'])
def ocr_file():
    """Perform OCR on an uploaded image or PDF and return extracted text."""
    if not OCR_AVAILABLE:
        return jsonify({'error': 'OCR packages not installed on server'}), 500

    files = request.files.getlist('file')
    if not files:
        return jsonify({'error': 'No file provided'}), 400

    combined_text = []
    for file in files:
        filename = file.filename or ''
        if not filename:
            continue
        data = file.read()
        lower = filename.lower()
        try:
            if lower.endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff')):
                image = Image.open(io.BytesIO(data)).convert('RGB')
                arr = np.array(image)
                results = OCR_READER.readtext(arr)
                # preserve layout: group OCR results into lines
                combined_text.append(ocr_results_to_text(results))
            elif lower.endswith('.pdf'):
                doc = fitz.open(stream=data, filetype='pdf')
                for page in doc:
                    pix = page.get_pixmap()
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    arr = np.array(img)
                    results = OCR_READER.readtext(arr)
                    combined_text.append(ocr_results_to_text(results))
            else:
                # skip unsupported types but continue
                continue
        except Exception as e:
            return jsonify({'error': f'OCR failed on {filename}: {str(e)}'}), 500

    text = '\n\n'.join(combined_text)
    return jsonify({'text': text})


@app.route('/api/detect', methods=['POST'])
def detect_pii():
    """Detect all PII entities in the provided text and return grouped by type.
    
    Request JSON:
        {
            "text": "Text to analyze for PII"
        }
    
    Response JSON:
        {
            "detected_pii": {
                "Person Name": ["John Doe", "Jane Smith"],
                "Email Address": ["john@example.com"],
                ...
            },
            "pii_categories": [
                {
                    "label": "Person Name",
                    "count": 2,
                    "examples": ["John Doe", "Jane Smith"],
                    "locked": false
                },
                ...
            ]
        }
    """
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400
        
        text = data['text'].strip()
        if not text:
            return jsonify({'error': 'Empty text provided'}), 400
        
        # Detect all entities
        entities = anonymizer.detect_pii(text)
        
        # Group by human label
        detected_by_label = {}
        for entity_text, entity_type, _, _ in entities:
            human_label = anonymizer.HUMAN_LABELS.get(entity_type, entity_type)
            if human_label not in detected_by_label:
                detected_by_label[human_label] = []
            detected_by_label[human_label].append(entity_text)
        
        # Define sensitive/locked categories (always anonymize, no checkbox)
        sensitive_categories = {
            'Aadhaar Number', 'National ID', 'Military ID', 'Passport Number', 
            'Credit Card', 'Social Security Number', 'Bank Account', 
            'IBAN', 'Routing Number', 'MICR Code', 'Cheque Number'
        }
        
        # Build response with category details
        pii_categories = []
        for label in sorted(detected_by_label.keys()):
            examples = list(dict.fromkeys(detected_by_label[label]))[:5]  # Unique, max 5
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
        scenario = data.get('scenario', '').strip()
        
        print(f"Processing text (length: {len(text)}, mode: {mode})")
        
        # Allowed labels control: optional list of human-friendly labels the user wants anonymized
        allowed_labels = data.get('allowed_labels')  # e.g. ['Person Name','Email Address']

        # Use the appropriate anonymization method based on mode
        if mode == 'mask':
            # mask doesn't store mappings; allow-list handled via temporary attribute
            setattr(anonymizer, '_allowed_labels_temp', allowed_labels)
            anonymized_text, mappings = anonymizer.mask(text)
            setattr(anonymizer, '_allowed_labels_temp', None)
            print(f"Using mask mode (irreversible)")
        elif mode == 'replace':
            setattr(anonymizer, '_allowed_labels_temp', allowed_labels)
            anonymized_text, mappings = anonymizer.replace(text)
            setattr(anonymizer, '_allowed_labels_temp', None)
            print(f"Using replace mode (irreversible)")
        else:  # Default to pseudonymize
            anonymized_text, mappings = anonymizer.pseudonymize(text, allowed_labels=allowed_labels)
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
            # Build prompt including optional scenario/instructions
            if scenario:
                llm_prompt = f"Scenario/Instructions: {scenario}\n\nPlease respond to the following message:\n\n{anonymized_text}"
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
    """Clear all stored mappings."""
    try:
        storage.clear_mappings()
        return jsonify({'message': 'Mappings cleared successfully'})
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
            'version': '2.0.0',  # Update version
            'anonymizer_healthy': anonymizer_healthy,
            'llm_mode': 'mock' if (not llm_client or llm_client.mock_mode) else 'api',
            'llm_available': GROQ_API_KEY is not None,
            'ocr_available': OCR_AVAILABLE,
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
        # OCR packages installed?
        checks['ocr_available'] = OCR_AVAILABLE
    
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
