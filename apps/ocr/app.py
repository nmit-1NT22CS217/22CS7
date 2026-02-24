"""
OCR API for PII-Anonymizer (EasyOCR + PyMuPDF).
"""
import io
import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from flask_cors import CORS

try:
    import fitz
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
    TESSERACT_CMD = os.getenv("TESSERACT_CMD")
    if TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
except ImportError:
    OCR_AVAILABLE = False


def ocr_results_to_text(results):
    """Convert EasyOCR results into multi-line text preserving line layout."""
    if not results:
        return ''

    items = []
    heights = []
    for bbox, text, _ in results:
        ys = [p[1] for p in bbox]
        xs = [p[0] for p in bbox]
        mid_y = sum(ys) / len(ys)
        min_x = min(xs)
        height = max(ys) - min(ys)
        items.append({'mid_y': mid_y, 'min_x': min_x, 'text': text, 'height': height})
        heights.append(height)

    avg_height = max(1.0, (sum(heights) / len(heights))) if heights else 1.0
    threshold = max(8.0, avg_height * 0.8)

    items.sort(key=lambda x: x['mid_y'])

    lines = []
    current_line = [items[0]]
    base_y = items[0]['mid_y']

    for it in items[1:]:
        if abs(it['mid_y'] - base_y) <= threshold:
            current_line.append(it)
            base_y = sum(i['mid_y'] for i in current_line) / len(current_line)
        else:
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

allowed_origins_env = os.getenv('ALLOWED_ORIGINS', '')
if allowed_origins_env:
    allowed = [o.strip() for o in allowed_origins_env.split(',') if o.strip()]
    CORS(app, origins=allowed)
else:
    CORS(app)

OCR_LANGS = [lang.strip() for lang in os.getenv('OCR_LANGS', 'eng').split(',') if lang.strip()]
TESS_LANG = "+".join(OCR_LANGS) if OCR_LANGS else "eng"


@app.route('/')
def index():
    return jsonify({
        'service': 'pii-anonymizer-ocr',
        'status': 'ok',
        'ocr_available': OCR_AVAILABLE,
        'ocr_langs': OCR_LANGS
    })


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
                text = pytesseract.image_to_string(image, lang=TESS_LANG)
                combined_text.append(text.strip())
            elif lower.endswith('.pdf'):
                doc = fitz.open(stream=data, filetype='pdf')
                for page in doc:
                    pix = page.get_pixmap()
                    img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
                    text = pytesseract.image_to_string(img, lang=TESS_LANG)
                    combined_text.append(text.strip())
            else:
                continue
        except Exception as e:
            return jsonify({'error': f'OCR failed on {filename}: {str(e)}'}), 500

    text = '\n\n'.join(combined_text)
    return jsonify({'text': text})


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy' if OCR_AVAILABLE else 'unhealthy',
        'ocr_available': OCR_AVAILABLE,
        'ocr_langs': OCR_LANGS
    })


if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.getenv('PORT', 5001))

    print("Starting OCR Flask application...")
    print(f"   Debug mode: {debug_mode}")
    print(f"   Port: {port}")
    print("   Host: 0.0.0.0")

    app.run(
        debug=debug_mode,
        host='0.0.0.0',
        port=port
    )
