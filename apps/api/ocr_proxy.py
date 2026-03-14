"""Proxy/forwarding helpers to route OCR requests to a remote OCR service.

This module supports Data Key Encryption (DKE) so that the API service can send
sensitive document payloads to the OCR service without ever transmitting plaintext.

The proxy wraps incoming requests into a JSON envelope of the form:

    {
      "encrypted_payload": "...",
      "encrypted_data_key": "..."
    }

The remote OCR service must support decrypting this envelope using the shared
ENCRYPTION_KEY environment variable.
"""

import base64
import json
import urllib.error
import urllib.parse
import urllib.request

from flask import Blueprint, request, Response, jsonify

try:
    from .crypto_util import dke_encrypt, dke_decrypt
except ImportError:  # Support running as a top-level module (e.g., Railway root=apps/api)
    from crypto_util import dke_encrypt, dke_decrypt


def create_ocr_proxy_blueprint(ocr_service_url: str, master_key: bytes) -> Blueprint:
    """Create a Blueprint that proxies OCR requests through DKE to a remote service."""

    ocr_service_url = ocr_service_url.rstrip('/')
    bp = Blueprint('ocr_proxy', __name__, url_prefix='/api/ocr')

    def _build_target_url(path: str) -> str:
        url = f"{ocr_service_url}/api/ocr/{path.lstrip('/')}"
        if request.query_string:
            url = f"{url}?{request.query_string.decode('utf-8')}"
        return url

    @bp.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
    def proxy(path: str):
        """Proxy all OCR endpoint requests to the remote OCR service."""

        target_url = _build_target_url(path)

        # For GET/DELETE requests, forward without encrypting (no body payload)
        if request.method in ('GET', 'DELETE'):
            data = None
        else:
            # Convert incoming payload to a JSON serializable structure
            if request.content_type and 'multipart/form-data' in request.content_type:
                # Convert multipart form uploads into JSON so we can encrypt them
                if 'file' not in request.files:
                    return jsonify({'error': 'No file provided'}), 400

                file = request.files['file']
                file_bytes = file.read()
                payload = {
                    'base64_data': base64.b64encode(file_bytes).decode('utf-8'),
                    'filename': file.filename,
                }
                # Include any additional form fields
                for k, v in request.form.items():
                    payload[k] = v
            else:
                # For JSON requests, parse existing body (or use empty dict)
                try:
                    payload = request.get_json(force=True)
                except Exception:
                    payload = {}
                if payload is None:
                    payload = {}

            # Wrap using DKE
            envelope = dke_encrypt(json.dumps(payload).encode('utf-8'), master_key)
            data = json.dumps(envelope).encode('utf-8')

        req = urllib.request.Request(target_url, data=data, method=request.method)
        req.add_header('Content-Type', 'application/json')
        req.add_header('X-Encrypted-Response', 'true')  # Request encrypted response
        # Mark as forwarded to avoid recursive proxying loops
        req.add_header('X-Forwarded-For-OCR', '1')

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_body = resp.read()
                resp_headers = dict(resp.getheaders())
                status_code = resp.getcode()
        except urllib.error.HTTPError as e:
            resp_body = e.read()
            resp_headers = dict(e.headers)
            status_code = e.code
        except Exception as e:
            return jsonify({'error': f'Proxy error: {e}'}), 502

        # Decrypt response if it's DKE encrypted
        if resp_headers.get('X-Encrypted-Response') == 'true':
            try:
                envelope = json.loads(resp_body.decode('utf-8'))
                resp_body = dke_decrypt(
                    envelope['encrypted_payload'],
                    envelope['encrypted_data_key'],
                    master_key
                )
            except Exception as e:
                return jsonify({'error': f'Decryption error: {e}'}), 502

        # Return the response from the remote service
        # Filter out hop-by-hop headers
        filtered_headers = {
            k: v
            for k, v in resp_headers.items()
            if k.lower() not in ('transfer-encoding', 'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te', 'trailers', 'upgrade', 'x-encrypted-response')
        }
        return Response(resp_body, status=status_code, headers=filtered_headers)

    return bp
