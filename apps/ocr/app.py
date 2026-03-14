"""
OCR Service Application
Provides OCR text extraction and context-aware PII processing endpoints.
"""
import os
import json
import json
from flask import Flask, Blueprint, request, jsonify
from dotenv import load_dotenv
from flask_cors import CORS
try:
    from .ocr_extractor import OCRExtractor, ContextAwarePIIExtractor
    from .anonymizer import PIIAnonymizer
    from .llm_client import GroqClient
    from .storage import MappingStorage
    from .crypto_util import generate_key, dke_decrypt, dke_encrypt
except ImportError:  # Support running as a top-level module (e.g., Railway root=apps/ocr)
    from ocr_extractor import OCRExtractor, ContextAwarePIIExtractor
    from anonymizer import PIIAnonymizer
    from llm_client import GroqClient
    from storage import MappingStorage
    from crypto_util import generate_key, dke_decrypt, dke_encrypt

load_dotenv()

app = Flask(__name__)

# OCR blueprint (can be reused by other Flask apps)
ocr_bp = Blueprint('ocr', __name__, url_prefix='/api/ocr')

# Use environment variable for secret key, or generate one if not provided
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    SECRET_KEY = os.urandom(24)
app.config['SECRET_KEY'] = SECRET_KEY

# CORS: allow any origin (Railway/public deployment friendly)
CORS(app)

ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', '').encode()
if not ENCRYPTION_KEY or ENCRYPTION_KEY == b'your_encryption_key_here':
    print("WARNING: No valid ENCRYPTION_KEY found in environment variables!")
    ENCRYPTION_KEY = generate_key()
    print(f"Using temporary key for this session. For production, set ENCRYPTION_KEY environment variable!")


def _get_decrypted_json():
    """Attempt to decrypt a DKE-wrapped JSON payload.

    The API service may forward requests encrypted using Data Key Encryption
    (DKE). This helper detects the envelope and decrypts it using the shared
    ENCRYPTION_KEY.

    Returns:
        dict|None: Decrypted JSON object, or None if no DKE payload is present.
    """
    if not request.is_json:
        return None

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None

    if 'encrypted_payload' in data and 'encrypted_data_key' in data:
        try:
            decrypted_bytes = dke_decrypt(
                data['encrypted_payload'],
                data['encrypted_data_key'],
                ENCRYPTION_KEY
            )
            return json.loads(decrypted_bytes)
        except Exception as e:
            print(f"[OCR DKE] Failed to decrypt payload: {e}")
            return None

    return None

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
MAPPING_TTL = int(os.getenv('MAPPING_TTL', '1800'))

# Initialize components
print("Initializing OCR Service...")

# Initialize OCR Extractor
ocr_extractor = OCRExtractor()
print(f"OCR Extractor initialized: {ocr_extractor.get_capabilities()}")

# Initialize Anonymizer for PII processing
anonymizer = PIIAnonymizer()
print("PII Anonymizer initialized")

# Initialize LLM client
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')

if GROQ_API_KEY:
    print(f"Running with Groq LLM")
    llm_client = GroqClient(GROQ_API_KEY, GROQ_MODEL)
else:
    print("No GROQ_API_KEY found - running in mock mode")
    llm_client = GroqClient(None, GROQ_MODEL)

# Initialize Context-Aware PII Extractor
context_extractor = ContextAwarePIIExtractor(llm_client)
print("Context-Aware PII Extractor initialized")

# Initialize storage
storage = MappingStorage(MAPPINGS_FILE, ENCRYPTION_KEY, ttl_seconds=MAPPING_TTL)
print(f"Storage initialized (TTL: {storage._format_ttl(MAPPING_TTL)})")

print("OCR Service ready")



@ocr_bp.route('/capabilities', methods=['GET'])
def get_ocr_capabilities():
    """Get available OCR and file processing capabilities."""
    return jsonify({
        'capabilities': ocr_extractor.get_capabilities(),
        'supported_formats': {
            'images': list(OCRExtractor.SUPPORTED_IMAGE_FORMATS),
            'text': list(OCRExtractor.SUPPORTED_TEXT_FORMATS),
            'pdf': list(OCRExtractor.SUPPORTED_PDF_FORMATS)
        }
    })


@ocr_bp.route('/extract', methods=['POST'])
def extract_text_from_file():
    """
    Extract text from uploaded file (image, PDF, or text file).
    
    Request: multipart/form-data with 'file' field
    OR JSON with 'base64_data' and 'filename' fields
    
    Response JSON:
        {
            "success": true/false,
            "text": "extracted text",
            "source_type": "image|pdf|text_file",
            "pages_processed": 1,
            "ocr_applied": true/false,
            "metadata": {...}
        }
    """
    try:
        # Handle DKE-wrapped request from a proxying API service
        decrypted = _get_decrypted_json()
        if decrypted is not None:
            print("[OCR DKE] Received encrypted payload, decrypting...")
            data = decrypted
        else:
            data = None

        # Handle file upload or base64 data
        if request.content_type and 'multipart/form-data' in request.content_type:
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            file_bytes = file.read()
            file_name = file.filename
            print(f"[OCR DEBUG] Received file: {file_name}, size: {len(file_bytes)} bytes")
        else:
            if data is None:
                data = request.get_json()
            if not data or 'base64_data' not in data:
                return jsonify({'error': 'No file data provided'}), 400
            
            import base64
            file_bytes = base64.b64decode(data['base64_data'])
            file_name = data.get('filename', 'unknown')
            print(f"[OCR DEBUG] Received base64 file: {file_name}, size: {len(file_bytes)} bytes")
        
        print(f"[OCR DEBUG] Calling extract_text...")
        # Extract text
        result = ocr_extractor.extract_text(
            file_bytes=file_bytes,
            file_name=file_name
        )
        print(f"[OCR DEBUG] Result success: {result.get('success')}, text length: {len(result.get('text', ''))}")
        
        # Encrypt response if requested by proxy
        if request.headers.get('X-Encrypted-Response') == 'true':
            encrypted_result = dke_encrypt(json.dumps(result).encode('utf-8'), ENCRYPTION_KEY)
            response = jsonify(encrypted_result)
            response.headers['X-Encrypted-Response'] = 'true'
            return response
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in extract_text_from_file: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Extraction failed: {str(e)}'}), 500


@ocr_bp.route('/process', methods=['POST'])
def process_file_with_context():
    """
    Full pipeline: Extract text from file and identify context-relevant PII.
    
    Request: multipart/form-data with:
        - 'file': The file to process
        - 'context_prompt': User's context/query for PII extraction
        - 'pii_categories' (optional): Comma-separated PII categories to focus on
        - 'skip_filtering' (optional): 'true' to skip context filtering
    
    OR JSON with:
        - 'base64_data': Base64 encoded file
        - 'filename': Original filename
        - 'context_prompt': User's context/query
        - 'pii_categories' (optional): Array of PII categories
        - 'skip_filtering' (optional): boolean
    
    Response JSON:
        {
            "success": true/false,
            "extraction": {...},
            "pii_analysis": {
                "relevant_pii": [...],
                "excluded_pii": [...],
                "summary": "..."
            },
            "text_for_pseudonymization": "..."
        }
    """
    try:
        # Attempt to decrypt DKE-wrapped request from an API proxy
        decrypted = _get_decrypted_json()
        if decrypted is not None:
            print("[OCR DKE] Received encrypted payload, decrypting...")
            data = decrypted
        else:
            data = None

        # Parse request
        if request.content_type and 'multipart/form-data' in request.content_type:
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            
            file = request.files['file']
            file_bytes = file.read()
            file_name = file.filename
            
            context_prompt = request.form.get('context_prompt', '')
            pii_categories = request.form.get('pii_categories', '')
            pii_categories = [c.strip() for c in pii_categories.split(',')] if pii_categories else None
            skip_filtering = request.form.get('skip_filtering', 'false').lower() == 'true'
        else:
            if data is None:
                data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            import base64
            if 'base64_data' in data:
                file_bytes = base64.b64decode(data['base64_data'])
                file_name = data.get('filename', 'unknown')
            else:
                return jsonify({'error': 'No file data provided'}), 400
            
            context_prompt = data.get('context_prompt', '')
            pii_categories = data.get('pii_categories')
            skip_filtering = data.get('skip_filtering', False)
        
        if not context_prompt and not skip_filtering:
            return jsonify({'error': 'context_prompt is required unless skip_filtering is true'}), 400
        
        # Step 1: Extract text from file
        extraction = ocr_extractor.extract_text(
            file_bytes=file_bytes,
            file_name=file_name
        )
        
        if not extraction.get('success', False):
            return jsonify({
                'success': False,
                'extraction': extraction,
                'error': extraction.get('error', 'Text extraction failed')
            })
        
        extracted_text = extraction.get('text', '')
        
        # Step 2: Context-aware PII analysis
        pii_analysis = None
        text_for_pseudonymization = extracted_text
        relevant_pii_list = None
        
        if context_prompt and not skip_filtering:
            print(f"[/api/ocr/process] Running hybrid context-aware PII extraction...")
            print(f"   Context prompt: {context_prompt[:100]}...")
            print(f"   Text length: {len(extracted_text)} chars")
            
            try:
                # Step 2a: Detect ALL PIIs using the thorough regex+spaCy anonymizer
                detected_piis = anonymizer.detect_pii(extracted_text)
                print(f"   Regex+spaCy detected: {len(detected_piis)} PII entities")
                
                # Step 2b: Use LLM to filter which PIIs are relevant to context
                pii_result = context_extractor.extract_contextual_pii(
                    text=extracted_text,
                    context_prompt=context_prompt,
                    pii_categories=pii_categories,
                    detected_piis=detected_piis
                )
                
                if pii_result.get('success', False):
                    relevant_pii_list = pii_result.get('relevant_pii', [])
                    pii_analysis = {
                        'relevant_pii': relevant_pii_list,
                        'excluded_pii': pii_result.get('excluded_pii', []),
                        'summary': pii_result.get('summary', '')
                    }
                    
                    # Generate selectively anonymized preview
                    if relevant_pii_list:
                        preview_text, _ = anonymizer.selective_pseudonymize(
                            extracted_text, relevant_pii_list, mode='pseudonymize'
                        )
                        text_for_pseudonymization = preview_text
                    
                    print(f"   PII analysis complete: {len(relevant_pii_list)} relevant, "
                          f"{len(pii_result.get('excluded_pii', []))} excluded")
                else:
                    error_msg = pii_result.get('error', 'Unknown error')
                    print(f"   PII extraction failed: {error_msg}")
                    pii_analysis = {
                        'relevant_pii': [],
                        'excluded_pii': [],
                        'summary': f"Context filtering failed: {error_msg}"
                    }
            except Exception as e:
                print(f"   Context extraction error: {str(e)}")
                pii_analysis = {
                    'relevant_pii': [],
                    'excluded_pii': [],
                    'summary': f"Context filtering error: {str(e)}"
                }
        else:
            if skip_filtering:
                print("[/api/ocr/process] Context filtering skipped by user")
                pii_analysis = {
                    'relevant_pii': [],
                    'excluded_pii': [],
                    'summary': 'Context filtering was skipped. All PII will be anonymized.'
                }
        
        result = {
            'success': True,
            'extraction': extraction,
            'extracted_text': extracted_text,
            'text_for_pseudonymization': text_for_pseudonymization,
            'context_prompt': context_prompt
        }
        
        if pii_analysis:
            result['pii_analysis'] = pii_analysis
        
        # Encrypt response if requested by proxy
        if request.headers.get('X-Encrypted-Response') == 'true':
            encrypted_result = dke_encrypt(json.dumps(result).encode('utf-8'), ENCRYPTION_KEY)
            response = jsonify(encrypted_result)
            response.headers['X-Encrypted-Response'] = 'true'
            return response
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in process_file_with_context: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500


@ocr_bp.route('/anonymize', methods=['POST'])
def ocr_and_anonymize():
    """
    Complete pipeline: Extract text, identify context-relevant PII, and pseudonymize.
    
    Request: multipart/form-data with:
        - 'file': The file to process
        - 'context_prompt': User's context/query for PII extraction
        - 'mode': 'pseudonymize' | 'mask' | 'replace' (default: pseudonymize)
        - 'call_llm': 'true' to get LLM response (default: false)
        - 'pii_categories' (optional): Comma-separated PII categories
        - 'skip_filtering' (optional): 'true' to skip context filtering
    
    Response JSON: Same as /api/anonymize endpoint plus extraction metadata
    """
    try:
        # Attempt to decrypt DKE-wrapped request from an API proxy
        decrypted = _get_decrypted_json()
        if decrypted is not None:
            print("[OCR DKE] Received encrypted payload, decrypting...")
            data = decrypted
        else:
            data = None

        # Parse request
        if request.content_type and 'multipart/form-data' in request.content_type:
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            
            file = request.files['file']
            file_bytes = file.read()
            file_name = file.filename
            
            context_prompt = request.form.get('context_prompt', '')
            mode = request.form.get('mode', 'pseudonymize')
            call_llm = request.form.get('call_llm', 'false').lower() == 'true'
            pii_categories = request.form.get('pii_categories', '')
            pii_categories = [c.strip() for c in pii_categories.split(',')] if pii_categories else None
            skip_filtering = request.form.get('skip_filtering', 'false').lower() == 'true'
        else:
            if data is None:
                data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            import base64
            if 'base64_data' in data:
                file_bytes = base64.b64decode(data['base64_data'])
                file_name = data.get('filename', 'unknown')
            else:
                return jsonify({'error': 'No file data provided'}), 400
            
            context_prompt = data.get('context_prompt', '')
            mode = data.get('mode', 'pseudonymize')
            call_llm = data.get('call_llm', False)
            pii_categories = data.get('pii_categories')
            skip_filtering = data.get('skip_filtering', False)
        
        # Step 1: Extract text from file
        extraction_result = ocr_extractor.extract_text(
            file_bytes=file_bytes,
            file_name=file_name
        )
        
        if not extraction_result.get('success', False):
            return jsonify({
                'error': extraction_result.get('error', 'File extraction failed'),
                'extraction': extraction_result
            }), 400
        
        text_to_anonymize = extraction_result.get('text', '')
        
        # Step 2: Anonymize ALL PII in the extracted text (full anonymization always)
        # Context prompt is only for PII identification/extraction, not for filtering anonymization
        print(f"Anonymizing all PII in extracted text ({len(text_to_anonymize)} chars, mode: {mode})")
        if mode == 'mask':
            anonymized_text, mappings = anonymizer.mask(text_to_anonymize)
        elif mode == 'replace':
            anonymized_text, mappings = anonymizer.replace(text_to_anonymize)
        else:
            anonymized_text, mappings = anonymizer.pseudonymize(text_to_anonymize)
        
        # Store mappings for later deanonymization
        if mappings:
            storage.add_mappings(mappings)
        
        response_data = {
            'success': True,
            'original_text': text_to_anonymize,
            'anonymized_text': anonymized_text,
            'entity_mappings': mappings,
            'mappings_count': len(mappings),
            'mode': mode,
            'reversible': len(mappings) > 0,
            'extraction_metadata': {
                'source_type': extraction_result.get('source_type'),
                'pages_processed': extraction_result.get('pages_processed'),
                'ocr_applied': extraction_result.get('ocr_applied'),
                'file_metadata': extraction_result.get('metadata', {})
            }
        }
        
        # Step 3: Call LLM if requested
        if call_llm and llm_client:
            # Build LLM prompt including context prompt if provided
            if context_prompt:
                llm_prompt = (f"User's request/context: {context_prompt}\n\n"
                              f"Below is the relevant information (with PII anonymized):\n\n{anonymized_text}\n\n"
                              f"Please respond to the user's request above using the anonymized information provided.")
            else:
                llm_prompt = f"Please respond to the following message:\n\n{anonymized_text}"
            
            llm_response = llm_client.generate_response(llm_prompt)
            
            if mappings:
                deanonymized_output = anonymizer.deanonymize(llm_response, mappings)
            else:
                deanonymized_output = llm_response
            
            response_data.update({
                'llm_response': llm_response,
                'llm_response_anonymized': llm_response,
                'deanonymized_output': deanonymized_output
            })
        
        # Encrypt response if requested by proxy
        if request.headers.get('X-Encrypted-Response') == 'true':
            encrypted_result = dke_encrypt(json.dumps(response_data).encode('utf-8'), ENCRYPTION_KEY)
            response = jsonify(encrypted_result)
            response.headers['X-Encrypted-Response'] = 'true'
            return response
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error in ocr_and_anonymize: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'OCR and anonymization failed: {str(e)}'}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check for OCR service."""
    return jsonify({
        'status': 'healthy',
        'service': 'ocr',
        'capabilities': ocr_extractor.get_capabilities()
    })


@app.route('/', methods=['GET'])
def root():
    """Default root route for platform health checks."""
    return jsonify({
        'status': 'ok',
        'service': 'ocr',
        'health': '/health'
    })


if __name__ == '__main__':
    # Development server configuration
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.getenv('PORT', 5001))  # Different port for OCR service
    
    print(f"Starting OCR Service...")
    print(f"   Debug mode: {debug_mode}")
    print(f"   Port: {port}")
    print(f"   Host: 0.0.0.0")

    # Register OCR routes when running as a standalone service
    app.register_blueprint(ocr_bp)

    app.run(
        debug=debug_mode,
        host='0.0.0.0',
        port=port
    )
