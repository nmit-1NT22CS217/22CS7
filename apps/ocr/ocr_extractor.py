"""
OCR and Text Extraction Module with Context-Aware PII Detection.
Supports images (PNG, JPG, JPEG, BMP, TIFF), PDFs, and TXT files.
Uses minimal dependencies for efficient backend processing.
"""
import os
import re
import io
import base64
from typing import Dict, List, Tuple, Optional, Union
from pathlib import Path

# Optional imports with graceful fallback
try:
    import fitz  # PyMuPDF for PDF handling
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("PyMuPDF not available. PDF processing will be limited.")

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    print("Pillow not available. Image processing will be limited.")

try:
    from google.cloud import vision
    from google.oauth2 import service_account
    CLOUD_VISION_AVAILABLE = True
except ImportError:
    CLOUD_VISION_AVAILABLE = False
    print("Google Cloud Vision not available. Using fallback OCR.")

# Keep Tesseract as fallback only
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


class OCRExtractor:
    """
    Handles text extraction from various file formats with OCR capabilities.
    Designed for minimal dependencies and efficient processing.
    """
    
    SUPPORTED_IMAGE_FORMATS = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.gif', '.webp'}
    SUPPORTED_TEXT_FORMATS = {'.txt', '.text', '.md', '.csv'}
    SUPPORTED_PDF_FORMATS = {'.pdf'}
    
    def __init__(self, tesseract_cmd: Optional[str] = None, gcp_credentials_json: Optional[str] = None):
        """
        Initialize OCR extractor with cloud-based vision API.
        
        Args:
            tesseract_cmd: Optional path to tesseract executable (fallback only)
            gcp_credentials_json: Path to GCP service account JSON file or JSON string
        """
        self.tesseract_available = TESSERACT_AVAILABLE
        self.pymupdf_available = PYMUPDF_AVAILABLE
        self.pillow_available = PILLOW_AVAILABLE
        self.cloud_vision_available = CLOUD_VISION_AVAILABLE
        self.vision_client = None
        
        # Initialize Google Cloud Vision client
        if CLOUD_VISION_AVAILABLE:
            try:
                if gcp_credentials_json:
                    import json
                    if gcp_credentials_json.startswith('{'):
                        # Assume it's JSON string
                        credentials = service_account.Credentials.from_service_account_info(
                            json.loads(gcp_credentials_json)
                        )
                    else:
                        # Assume it's file path
                        credentials = service_account.Credentials.from_service_account_file(gcp_credentials_json)
                    self.vision_client = vision.ImageAnnotatorClient(credentials=credentials)
                else:
                    # Use default credentials (Application Default Credentials)
                    self.vision_client = vision.ImageAnnotatorClient()
                print("✓ Google Cloud Vision API initialized")
            except Exception as e:
                print(f"⚠ Could not initialize Google Cloud Vision: {e}")
                print("  Falling back to Tesseract if available")
                self.vision_client = None
        
        # Fallback Tesseract setup
        if tesseract_cmd and TESSERACT_AVAILABLE:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    
    def get_capabilities(self) -> Dict[str, bool]:
        """Return available processing capabilities."""
        has_cloud_ocr = self.cloud_vision_available and self.vision_client is not None
        has_fallback_ocr = self.tesseract_available and self.pillow_available
        
        return {
            'pdf_text_extraction': self.pymupdf_available,
            'pdf_ocr': self.pymupdf_available and (has_cloud_ocr or has_fallback_ocr),
            'image_ocr': (has_cloud_ocr or has_fallback_ocr) and self.pillow_available,
            'text_files': True,  # Always available
            'cloud_vision': has_cloud_ocr,
            'tesseract_fallback': has_fallback_ocr
        }
    
    def extract_text(self, 
                     file_path: Optional[str] = None,
                     file_bytes: Optional[bytes] = None,
                     file_name: Optional[str] = None,
                     base64_data: Optional[str] = None,
                     ocr_if_needed: bool = True) -> Dict[str, any]:
        """
        Extract text from a file (path, bytes, or base64).
        
        Args:
            file_path: Path to the file
            file_bytes: Raw file bytes
            file_name: Original filename (needed when using file_bytes/base64)
            base64_data: Base64 encoded file data
            ocr_if_needed: Whether to apply OCR if text extraction yields minimal results
            
        Returns:
            Dict with extracted text, metadata, and status
        """
        result = {
            'success': False,
            'text': '',
            'source_type': None,
            'pages_processed': 0,
            'ocr_applied': False,
            'error': None,
            'metadata': {}
        }
        
        try:
            # Determine file extension and get bytes
            if file_path:
                ext = Path(file_path).suffix.lower()
                with open(file_path, 'rb') as f:
                    file_bytes = f.read()
                file_name = Path(file_path).name
            elif base64_data:
                file_bytes = base64.b64decode(base64_data)
                ext = Path(file_name).suffix.lower() if file_name else ''
            elif file_bytes and file_name:
                ext = Path(file_name).suffix.lower()
            else:
                result['error'] = 'No valid file input provided'
                return result
            
            result['metadata']['filename'] = file_name
            result['metadata']['file_size'] = len(file_bytes)
            
            # Route to appropriate extractor
            if ext in self.SUPPORTED_TEXT_FORMATS:
                result = self._extract_from_text(file_bytes, result)
            elif ext in self.SUPPORTED_PDF_FORMATS:
                result = self._extract_from_pdf(file_bytes, result, ocr_if_needed)
            elif ext in self.SUPPORTED_IMAGE_FORMATS:
                result = self._extract_from_image(file_bytes, result)
            else:
                result['error'] = f'Unsupported file format: {ext}'
            
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    def _extract_from_text(self, file_bytes: bytes, result: Dict) -> Dict:
        """Extract text from plain text files."""
        try:
            # Try common encodings
            for encoding in ['utf-8', 'utf-16', 'latin-1', 'cp1252']:
                try:
                    text = file_bytes.decode(encoding)
                    result['text'] = text
                    result['source_type'] = 'text_file'
                    result['success'] = True
                    result['pages_processed'] = 1
                    return result
                except UnicodeDecodeError:
                    continue
            
            result['error'] = 'Could not decode text file with supported encodings'
        except Exception as e:
            result['error'] = f'Text extraction failed: {str(e)}'
        
        return result
    
    def _extract_from_pdf(self, file_bytes: bytes, result: Dict, ocr_if_needed: bool = True) -> Dict:
        """Extract text from PDF files using PyMuPDF."""
        if not self.pymupdf_available:
            result['error'] = 'PyMuPDF not available for PDF processing'
            return result
        
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            result['metadata']['page_count'] = len(doc)
            
            all_text = []
            pages_with_text = 0
            
            for page_num, page in enumerate(doc):
                # Try direct text extraction first
                text = page.get_text("text").strip()
                
                if text:
                    all_text.append(f"--- Page {page_num + 1} ---\n{text}")
                    pages_with_text += 1
                elif ocr_if_needed and self.vision_client and self.pillow_available:
                    # Apply OCR to page if no text found
                    ocr_text = self._ocr_pdf_page(page)
                    if ocr_text:
                        all_text.append(f"--- Page {page_num + 1} (OCR) ---\n{ocr_text}")
                        result['ocr_applied'] = True
                        pages_with_text += 1
            
            doc.close()
            
            result['text'] = '\n\n'.join(all_text)
            result['source_type'] = 'pdf'
            result['pages_processed'] = pages_with_text
            result['success'] = bool(result['text'])
            
            if not result['text']:
                result['error'] = 'No text could be extracted from PDF'
                
        except Exception as e:
            result['error'] = f'PDF extraction failed: {str(e)}'
        
        return result
    
    def _ocr_pdf_page(self, page, dpi: int = 200) -> str:
        """Apply OCR to a PDF page using Cloud Vision or Tesseract."""
        try:
            # Render page to image
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Convert image to bytes
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes = img_bytes.getvalue()
            
            # Try Cloud Vision first
            if self.vision_client:
                vision_image = vision.Image(content=img_bytes)
                response = self.vision_client.document_text_detection(image=vision_image)
                text = response.full_text_annotation.text if response.full_text_annotation else ''
                if text:
                    return text.strip()
            
            # Fallback to Tesseract
            if self.tesseract_available:
                text = pytesseract.image_to_string(img, lang='eng')
                return text.strip()
                
            return ""
            
        except Exception as e:
            print(f"OCR failed for page: {e}")
            return ""
    
    def _extract_from_image(self, file_bytes: bytes, result: Dict) -> Dict:
        """Extract text from images using Cloud Vision or Tesseract."""
        if not self.pillow_available:
            result['error'] = 'Pillow not available for image processing'
            return result
        
        if not self.vision_client and not self.tesseract_available:
            result['error'] = 'No OCR method available (Cloud Vision or Tesseract)'
            return result
        
        try:
            # Load image
            img = Image.open(io.BytesIO(file_bytes))
            result['metadata']['image_size'] = img.size
            result['metadata']['image_mode'] = img.mode
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'P', 'LA'):
                img = img.convert('RGB')
            
            # Try Cloud Vision first
            if self.vision_client:
                vision_image = vision.Image(content=file_bytes)
                response = self.vision_client.document_text_detection(image=vision_image)
                text = response.full_text_annotation.text if response.full_text_annotation else ''
                
                if text:
                    result['text'] = text.strip()
                    result['source_type'] = 'image'
                    result['ocr_applied'] = True
                    result['ocr_method'] = 'google_cloud_vision'
                    result['pages_processed'] = 1
                    result['success'] = True
                    return result
            
            # Fallback to Tesseract
            if self.tesseract_available:
                text = pytesseract.image_to_string(img, lang='eng')
                result['text'] = text.strip()
                result['source_type'] = 'image'
                result['ocr_applied'] = True
                result['ocr_method'] = 'tesseract'
                result['pages_processed'] = 1
                result['success'] = bool(result['text'])
                
                if not result['text']:
                    result['error'] = 'OCR could not extract any text from image'
                return result
            
            result['error'] = 'No OCR method available'
                
        except Exception as e:
            result['error'] = f'Image OCR failed: {str(e)}'
        
        return result


    def _extract_with_cloud_vision(self, image_path: Union[str, bytes]) -> Dict[str, any]:
        """
        Extract text using Google Cloud Vision API.
        """
        result = {'success': False, 'text': '', 'error': None}
        
        if not self.vision_client:
            result['error'] = 'Cloud Vision client not initialized'
            return result
        
        try:
            # Read image
            if isinstance(image_path, bytes):
                image_bytes = image_path
            else:
                with open(image_path, 'rb') as f:
                    image_bytes = f.read()
            
            # Create image object
            image = vision.Image(content=image_bytes)
            
            # Perform OCR
            response = self.vision_client.document_text_detection(image=image)
            
            # Extract text from response
            text = response.full_text_annotation.text if response.full_text_annotation else ''
            
            result['success'] = True
            result['text'] = text
            
        except Exception as e:
            result['error'] = f'Cloud Vision OCR failed: {str(e)}'
        
        return result
    
    def _extract_with_tesseract(self, image_path: Union[str, bytes]) -> Dict[str, any]:
        """
        Extract text using Tesseract (fallback).
        """
        result = {'success': False, 'text': '', 'error': None}
        
        if not self.tesseract_available or not self.pillow_available:
            result['error'] = 'Tesseract not available'
            return result
        
        try:
            if isinstance(image_path, bytes):
                image = Image.open(io.BytesIO(image_path))
            else:
                image = Image.open(image_path)
            
            text = pytesseract.image_to_string(image, lang='eng')
            result['success'] = True
            result['text'] = text
            
        except Exception as e:
            result['error'] = f'Tesseract OCR failed: {str(e)}'
        
        return result


class ContextAwarePIIExtractor:
    """
    Hybrid context-aware PII extractor.
    
    Uses the robust regex+spaCy detection from PIIAnonymizer to find ALL PIIs,
    then uses the LLM to filter which ones are relevant to the user's context.
    This ensures no PII is ever missed — the LLM only classifies, not detects.
    """
    
    def __init__(self, llm_client):
        """
        Initialize with an LLM client.
        
        Args:
            llm_client: Instance of GroqClient or compatible LLM client
        """
        self.llm_client = llm_client
    
    def extract_contextual_pii(self, 
                                text: str, 
                                context_prompt: str,
                                pii_categories: Optional[List[str]] = None,
                                detected_piis: Optional[List] = None) -> Dict:
        """
        Filter pre-detected PIIs based on user context.
        
        Uses a hybrid approach:
        1. Accepts pre-detected PIIs (from regex+spaCy via PIIAnonymizer.detect_pii())
        2. Sends the detected PII list to the LLM asking which are relevant
        3. Falls back to keyword matching if LLM fails
        
        Args:
            text: The extracted text from OCR/file
            context_prompt: User's query/context describing what they need
            pii_categories: Optional list of PII categories to focus on
            detected_piis: Pre-detected PIIs as list of (value, type, start, end) tuples.
                          If None, falls back to LLM-only detection (less reliable).
            
        Returns:
            Dict with identified PIIs, their types, and extraction rationale
        """
        # If we have pre-detected PIIs, use the hybrid approach (reliable)
        if detected_piis and len(detected_piis) > 0:
            return self._filter_with_llm(text, context_prompt, detected_piis, pii_categories)
        
        # Fallback: LLM-only detection (kept for backward compatibility)
        return self._detect_with_llm(text, context_prompt, pii_categories)
    
    def _filter_with_llm(self, text: str, context_prompt: str,
                          detected_piis: List, pii_categories: Optional[List[str]]) -> Dict:
        """
        Send pre-detected PIIs to LLM for context-based filtering.
        The LLM only classifies — it doesn't need to find PIIs itself.
        """
        # Build a compact list of detected PIIs for the LLM
        pii_list_str = self._format_detected_piis(detected_piis)
        
        categories_hint = ""
        if pii_categories:
            categories_hint = f"\nThe user is specifically interested in: {', '.join(pii_categories)}"
        
        prompt = f"""You are a PII relevance classifier. Below is a list of ALL Personally Identifiable Information (PII) detected in a document by an automated scanner. Your job is to classify each PII as RELEVANT or EXCLUDED based on the user's context query.

DETECTED PII ITEMS:
{pii_list_str}

USER'S CONTEXT/QUERY:
\"\"\"{context_prompt}\"\"\"{categories_hint}

INSTRUCTIONS:
- Classify EVERY detected PII item as either "relevant" or "excluded"
- Base your decision on the user's stated context/query
- If the user asks for "Name, Phone and Account" — include ALL names, ALL phone numbers, ALL account numbers found
- Include items for ALL persons/entities found in the document, not just the first one
- Respond with ONLY a valid JSON object (no markdown, no code fences)

JSON FORMAT:
{{
    "relevant_indices": [0, 1, 3, 5],
    "summary": "Brief explanation"
}}

Where "relevant_indices" contains the index numbers of the PII items that ARE relevant to the user's query. All other items are excluded."""
        
        try:
            response = self.llm_client.generate_response(prompt)
            return self._parse_filter_response(response, detected_piis, text, context_prompt)
        except Exception as e:
            print(f"   LLM filtering failed: {e}, falling back to keyword matching")
            return self._keyword_fallback(detected_piis, context_prompt, text)
    
    def _format_detected_piis(self, detected_piis: List) -> str:
        """Format detected PIIs into a numbered list for the LLM."""
        lines = []
        for i, pii in enumerate(detected_piis):
            value, pii_type = pii[0], pii[1]
            lines.append(f"  [{i}] Type: {pii_type}, Value: \"{value}\"")
        return '\n'.join(lines)
    
    def _enrich_positions(self, pii_items: List, original_text: str) -> List:
        """
        Ensure every PII item has a valid 'position' field.
        For items missing position data, search for their value in the original text.
        This is critical for correct grouping on the frontend.
        """
        if not original_text:
            return pii_items
        text_lower = original_text.lower()
        # Track used positions to handle duplicate values at different locations
        used_positions = set()
        for item in pii_items:
            pos = item.get('position')
            if pos is not None and pos != 9999999 and isinstance(pos, (int, float)):
                used_positions.add(int(pos))
                continue
            val = item.get('value', '')
            if not val:
                item['position'] = 9999999
                continue
            # Try exact match first
            idx = original_text.find(val)
            if idx == -1:
                # Try case-insensitive
                idx = text_lower.find(val.lower())
            # If still not found, try partial match (first few words)
            if idx == -1 and len(val) > 10:
                # Try first 3 words
                words = val.split()
                if len(words) >= 2:
                    partial = ' '.join(words[:min(3, len(words))])
                    idx = text_lower.find(partial.lower())
            if idx != -1:
                # Avoid same position for different items
                while idx in used_positions:
                    next_idx = original_text.find(val, idx + 1)
                    if next_idx == -1:
                        next_idx = text_lower.find(val.lower(), idx + 1)
                    if next_idx == -1:
                        break
                    idx = next_idx
                used_positions.add(idx)
                item['position'] = idx
            else:
                item['position'] = 9999999
        return pii_items

    def _parse_filter_response(self, response: str, detected_piis: List,
                                original_text: str, context_prompt: str) -> Dict:
        """Parse the LLM's filtering response and build the result."""
        import json
        
        result = {
            'success': True,
            'relevant_pii': [],
            'excluded_pii': [],
            'summary': '',
            'text_for_pseudonymization': original_text,
            'raw_response': response
        }
        
        parsed = self._try_parse_json(response)
        
        if parsed and isinstance(parsed, dict):
            # Handle both int and string indices from LLM
            raw_indices = parsed.get('relevant_indices', [])
            relevant_indices = set()
            for idx in raw_indices:
                try:
                    relevant_indices.add(int(idx))
                except (ValueError, TypeError):
                    pass
            result['summary'] = parsed.get('summary', '')
            
            for i, pii in enumerate(detected_piis):
                value, pii_type = pii[0], pii[1]
                start_pos = pii[2] if len(pii) > 2 else i
                if i in relevant_indices:
                    result['relevant_pii'].append({
                        'value': value,
                        'type': pii_type,
                        'confidence': 0.95,
                        'reason': f'Relevant to context: {context_prompt}',
                        'position': start_pos
                    })
                else:
                    result['excluded_pii'].append({
                        'value': value,
                        'type': pii_type,
                        'reason_excluded': 'Not relevant to user query'
                    })
            
            if result['relevant_pii']:
                # Enrich positions as safety net
                self._enrich_positions(result['relevant_pii'], original_text)
                return result
        
        # If JSON parsing failed or no relevant items, try keyword fallback
        print("   LLM filter response unusable, using keyword fallback")
        return self._keyword_fallback(detected_piis, context_prompt, original_text)
    
    def _keyword_fallback(self, detected_piis: List, context_prompt: str,
                           original_text: str) -> Dict:
        """
        Fallback: match PII types against keywords in the context prompt.
        This ensures PII cards always appear even if the LLM fails.
        """
        context_lower = context_prompt.lower()
        
        # Map context keywords → PII types (covers all 63 entity types)
        keyword_map = {
            # --- Identity ---
            'name': {'PERSON_NAME', 'PERSON', 'NAME'},
            'person': {'PERSON_NAME', 'PERSON', 'NAME'},
            'identity': {'PERSON_NAME', 'PASSPORT', 'PASSPORT_US', 'PASSPORT_UK', 'PASSPORT_INDIA', 'DRIVER_LICENSE', 'INDIA_DL', 'SSN', 'INDIA_PAN', 'INDIA_AADHAAR', 'UK_NIN', 'CANADA_SIN', 'AUSTRALIA_TFN'},
            'nationality': {'NATIONALITY_GROUP'},
            'language': {'LANGUAGE_NAME'},
            # --- Contact ---
            'phone': {'PHONE', 'PHONE_NUMBER', 'MOBILE'},
            'mobile': {'PHONE', 'PHONE_NUMBER', 'MOBILE'},
            'contact': {'PHONE', 'EMAIL', 'PHONE_NUMBER', 'ADDRESS', 'LOCALITY'},
            'email': {'EMAIL', 'EMAIL_ADDRESS'},
            'mail': {'EMAIL', 'EMAIL_ADDRESS'},
            # --- Address & Location ---
            'address': {'ADDRESS', 'LOCALITY', 'PIN_CODE', 'ZIP_CODE', 'UK_POSTCODE'},
            'location': {'LOCATION', 'ADDRESS', 'LOCALITY'},
            'locality': {'LOCALITY', 'ADDRESS'},
            'postcode': {'UK_POSTCODE', 'CANADA_POSTCODE', 'AUSTRALIA_POSTCODE', 'FRANCE_POSTCODE', 'NETHERLANDS_POSTCODE', 'JAPAN_POSTCODE', 'GERMANY_PLZ', 'BRAZIL_CEP'},
            'zip': {'ZIP_CODE'},
            'pin code': {'PIN_CODE'},
            'plz': {'GERMANY_PLZ'},
            'cep': {'BRAZIL_CEP'},
            # --- Financial ---
            'account': {'ACCOUNT_ID', 'ACCOUNT_NUMBER', 'BANK_ACCOUNT', 'INDIA_AADHAAR'},
            'bank': {'BANK_ACCOUNT', 'ACCOUNT_ID', 'ACCOUNT_NUMBER', 'INDIA_AADHAAR', 'IFSC_CODE', 'SWIFT_BIC', 'SORT_CODE', 'BSB_NUMBER', 'ROUTING_NUMBER', 'IBAN'},
            'card': {'CREDIT_CARD'},
            'credit': {'CREDIT_CARD'},
            'financial': {'FINANCIAL_AMOUNT', 'BANK_ACCOUNT', 'CREDIT_CARD', 'ACCOUNT_ID', 'ACCOUNT_NUMBER'},
            'money': {'FINANCIAL_AMOUNT'},
            'amount': {'FINANCIAL_AMOUNT'},
            'iban': {'IBAN'},
            'swift': {'SWIFT_BIC'},
            'bic': {'SWIFT_BIC'},
            'ifsc': {'IFSC_CODE'},
            'sort code': {'SORT_CODE'},
            'bsb': {'BSB_NUMBER'},
            'routing': {'ROUTING_NUMBER'},
            # --- Government IDs ---
            'ssn': {'SSN'},
            'social security': {'SSN'},
            'aadhaar': {'INDIA_AADHAAR'},
            'aadhar': {'INDIA_AADHAAR'},
            'pan': {'INDIA_PAN'},
            'sin': {'CANADA_SIN'},
            'tfn': {'AUSTRALIA_TFN'},
            'tax file': {'AUSTRALIA_TFN'},
            'steuer': {'GERMANY_STEUER_ID'},
            'tax id': {'GERMANY_STEUER_ID', 'AUSTRALIA_TFN', 'CANADA_SIN'},
            'vat': {'UK_VAT', 'EU_VAT'},
            'gst': {'CANADA_GST'},
            'abn': {'AUSTRALIA_ABN'},
            # --- Travel & Licenses ---
            'passport': {'PASSPORT', 'PASSPORT_CONTEXT', 'PASSPORT_US', 'PASSPORT_UK', 'PASSPORT_INDIA'},
            'driver': {'DRIVER_LICENSE', 'DRIVER_LICENSE_CONTEXT', 'INDIA_DL'},
            'license': {'DRIVER_LICENSE', 'DRIVER_LICENSE_CONTEXT', 'INDIA_DL'},
            'driving': {'DRIVER_LICENSE', 'DRIVER_LICENSE_CONTEXT', 'INDIA_DL'},
            # --- Medical ---
            'nhs': {'UK_NHS'},
            'medicare': {'US_MEDICARE'},
            'medical': {'MEDICAL_ID', 'US_MEDICARE', 'UK_NHS'},
            'health': {'MEDICAL_ID', 'US_MEDICARE', 'UK_NHS'},
            # --- National IDs ---
            'national insurance': {'UK_NIN'},
            'nin': {'UK_NIN'},
            # --- Network & Digital ---
            'ip': {'IP_ADDRESS', 'IPV6_ADDRESS'},
            'ipv6': {'IPV6_ADDRESS'},
            'mac': {'MAC_ADDRESS'},
            'url': {'URL'},
            'website': {'URL'},
            'link': {'URL'},
            'network': {'IP_ADDRESS', 'IPV6_ADDRESS', 'MAC_ADDRESS', 'URL'},
            # --- Vehicle ---
            'vehicle': {'UK_VEHICLE_REG', 'INDIA_VEHICLE_REG'},
            'registration': {'UK_VEHICLE_REG', 'INDIA_VEHICLE_REG'},
            # --- Organizational & Misc ---
            'organization': {'ORGANIZATION'},
            'company': {'ORGANIZATION'},
            'employer': {'ORGANIZATION', 'EMPLOYEE_ID'},
            'employee': {'EMPLOYEE_ID'},
            'employee id': {'EMPLOYEE_ID'},
            'application': {'APPLICATION_NUMBER'},
            'application number': {'APPLICATION_NUMBER'},
            'facility': {'FACILITY_NAME'},
            'event': {'EVENT_NAME'},
            'legal': {'LEGAL_DOCUMENT'},
            'document': {'LEGAL_DOCUMENT'},
            'artwork': {'ARTWORK_TITLE'},
            # --- Temporal ---
            'date': {'DATE_TIME'},
            'dob': {'DATE_TIME'},
            'time': {'DATE_TIME'},
            'birthday': {'DATE_TIME'},
            # --- Catch-all ---
            'all': None,
            'everything': None,
        }
        
        # Determine which PII types are wanted
        wanted_types = set()
        include_all = False
        
        for keyword, types in keyword_map.items():
            if keyword in context_lower:
                if types is None:
                    include_all = True
                    break
                wanted_types.update(types)
        
        # If no keywords matched, include everything (safe default)
        if not wanted_types and not include_all:
            include_all = True
        
        result = {
            'success': True,
            'relevant_pii': [],
            'excluded_pii': [],
            'summary': f'Filtered by keyword matching on context: {context_prompt}',
            'text_for_pseudonymization': original_text,
        }
        
        for i, pii in enumerate(detected_piis):
            value, pii_type = pii[0], pii[1]
            start_pos = pii[2] if len(pii) > 2 else i
            if include_all or pii_type in wanted_types:
                result['relevant_pii'].append({
                    'value': value,
                    'type': pii_type,
                    'confidence': 0.9,
                    'reason': f'Matches context: {context_prompt}',
                    'position': start_pos
                })
            else:
                result['excluded_pii'].append({
                    'value': value,
                    'type': pii_type,
                    'reason_excluded': 'Not matching requested PII types'
                })
        
        return result
    
    def _detect_with_llm(self, text: str, context_prompt: str,
                          pii_categories: Optional[List[str]]) -> Dict:
        """Legacy: LLM-only detection (fallback when no pre-detected PIIs provided)."""
        system_context = self._build_extraction_prompt(context_prompt, pii_categories)
        
        full_prompt = f"""{system_context}

TEXT TO ANALYZE:
\"\"\"
{text}
\"\"\"

USER'S CONTEXT/QUERY:
\"\"\"{context_prompt}\"\"\"

IMPORTANT: Respond with ONLY a valid JSON object (no markdown, no code fences, no extra text).
The JSON must contain:
1. "relevant_pii": Array of objects with "value", "type", "confidence" (0-1), and "reason"
2. "excluded_pii": Array of PII found but not relevant to context (with "value", "type", "reason_excluded")
3. "summary": Brief explanation of extraction decisions

Do NOT include "text_for_pseudonymization".

Example:
{{
    "relevant_pii": [
        {{"value": "John Smith", "type": "PERSON_NAME", "confidence": 0.95, "reason": "Name relevant to query"}},
        {{"value": "+1-555-1234", "type": "PHONE", "confidence": 0.9, "reason": "Phone number"}}
    ],
    "excluded_pii": [
        {{"value": "2024-01-15", "type": "DATE", "reason_excluded": "Not personally identifying"}}
    ],
    "summary": "Extracted relevant identifiers"
}}"""
        
        try:
            response = self.llm_client.generate_response(full_prompt)
            return self._parse_extraction_response(response, text)
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'relevant_pii': [],
                'text_for_pseudonymization': text
            }
    
    def _build_extraction_prompt(self, context_prompt: str, pii_categories: Optional[List[str]]) -> str:
        """Build the system prompt for LLM-only extraction (legacy fallback)."""
        categories_hint = ""
        if pii_categories:
            categories_hint = f"\nFocus particularly on these PII types: {', '.join(pii_categories)}"
        
        return f"""You are a context-aware PII extraction specialist. Analyze text and identify ALL Personally Identifiable Information (PII) that is RELEVANT based on the user's context.

RULES:
1. Find ALL instances across ALL persons/paragraphs in the document
2. Return every PII that matches the user's requested types
3. Do NOT summarize or skip duplicates — list each occurrence separately
{categories_hint}"""

    def _parse_extraction_response(self, response: str, original_text: str) -> Dict:
        """Parse LLM response and extract structured PII data with robust fallbacks."""
        import json
        
        result = {
            'success': True,
            'relevant_pii': [],
            'excluded_pii': [],
            'summary': '',
            'text_for_pseudonymization': original_text,
            'raw_response': response
        }
        
        parsed = self._try_parse_json(response)
        
        if parsed and isinstance(parsed, dict):
            result['relevant_pii'] = parsed.get('relevant_pii', [])
            result['excluded_pii'] = parsed.get('excluded_pii', [])
            result['summary'] = parsed.get('summary', '')
            result['text_for_pseudonymization'] = parsed.get('text_for_pseudonymization', original_text)
        else:
            # Last-resort: try to extract PII items via regex from the raw text
            extracted = self._extract_pii_from_text(response)
            if extracted:
                result['relevant_pii'] = extracted
                result['summary'] = 'Extracted PII from non-JSON response'
            else:
                result['summary'] = 'Could not parse structured response, using full text'
                result['text_for_pseudonymization'] = original_text
        
        # Enrich positions for all items (LLM responses typically lack position data)
        if result['relevant_pii']:
            self._enrich_positions(result['relevant_pii'], original_text)
        
        return result
    
    def _try_parse_json(self, response: str):
        """Try multiple strategies to extract valid JSON from LLM response."""
        import json
        
        # Strategy 1: Direct parse (response is pure JSON)
        try:
            return json.loads(response.strip())
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Strategy 2: Strip markdown code fences (```json ... ``` or ``` ... ```)
        cleaned = re.sub(r'^```(?:json)?\s*\n?', '', response.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r'\n?```\s*$', '', cleaned.strip(), flags=re.MULTILINE)
        try:
            return json.loads(cleaned.strip())
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Strategy 3: Find the outermost balanced JSON object
        json_str = self._find_balanced_json(cleaned)
        if json_str:
            try:
                return json.loads(json_str)
            except (json.JSONDecodeError, ValueError):
                pass
        
        # Strategy 4: Greedy regex match (original approach) on cleaned text
        json_match = re.search(r'\{[\s\S]*\}', cleaned)
        if json_match:
            try:
                return json.loads(json_match.group())
            except (json.JSONDecodeError, ValueError):
                pass
        
        # Strategy 5: Try to repair truncated JSON (missing closing braces/brackets)
        if json_match:
            repaired = self._repair_truncated_json(json_match.group())
            if repaired:
                try:
                    return json.loads(repaired)
                except (json.JSONDecodeError, ValueError):
                    pass
        
        return None
    
    def _find_balanced_json(self, text: str):
        """Find the first balanced { ... } JSON object in text."""
        start = text.find('{')
        if start == -1:
            return None
        
        depth = 0
        in_string = False
        escape_next = False
        
        for i in range(start, len(text)):
            ch = text[i]
            if escape_next:
                escape_next = False
                continue
            if ch == '\\' and in_string:
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        
        return None
    
    def _repair_truncated_json(self, text: str):
        """Attempt to repair JSON that was truncated (e.g. due to max_tokens)."""
        # Count unclosed brackets and braces
        in_string = False
        escape_next = False
        stack = []
        
        for ch in text:
            if escape_next:
                escape_next = False
                continue
            if ch == '\\' and in_string:
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch in ('{', '['):
                stack.append(ch)
            elif ch == '}' and stack and stack[-1] == '{':
                stack.pop()
            elif ch == ']' and stack and stack[-1] == '[':
                stack.pop()
        
        if not stack:
            return None  # Already balanced, nothing to repair
        
        # Close the string if we're inside one
        repaired = text
        if in_string:
            repaired += '"'
        
        # Close open brackets/braces in reverse order
        for opener in reversed(stack):
            repaired += ']' if opener == '[' else '}'
        
        return repaired
    
    def _extract_pii_from_text(self, response: str) -> list:
        """
        Last-resort: extract PII-like entries from free-text LLM response
        by looking for quoted value/type pairs.
        """
        pii_items = []
        # Look for patterns like "value": "...", "type": "..."
        pattern = re.finditer(
            r'"value"\s*:\s*"([^"]+)"\s*,\s*"type"\s*:\s*"([^"]+)"',
            response
        )
        for m in pattern:
            pii_items.append({
                'value': m.group(1),
                'type': m.group(2),
                'confidence': 0.8,
                'reason': 'Extracted from partial response'
            })
        return pii_items
    
    def get_targeted_text(self, 
                          extraction_result: Dict,
                          include_only_relevant: bool = True) -> str:
        """
        Get text prepared for pseudonymization based on extraction results.
        
        Args:
            extraction_result: Result from extract_contextual_pii
            include_only_relevant: If True, marks only relevant PII for processing
            
        Returns:
            Text ready for pseudonymization
        """
        if not extraction_result.get('success'):
            return extraction_result.get('text_for_pseudonymization', '')
        
        return extraction_result.get('text_for_pseudonymization', '')


class FileProcessor:
    """
    High-level file processor with cloud-based OCR and contextual PII extraction.
    """
    
    def __init__(self, llm_client, tesseract_cmd: Optional[str] = None, gcp_credentials_json: Optional[str] = None, context_prompt: str = ''):
        """
        Initialize file processor with cloud OCR support.
        
        Args:
            llm_client: LLM client instance for context-aware PII extraction
            tesseract_cmd: Optional path to Tesseract executable (fallback)
            gcp_credentials_json: GCP service account JSON file path or JSON string
            context_prompt: Default context prompt for PII extraction
            llm_client: LLM client for context-aware extraction
            tesseract_cmd: Optional path to tesseract executable
        """
        self.ocr_extractor = OCRExtractor(tesseract_cmd=tesseract_cmd, gcp_credentials_json=gcp_credentials_json)
        self.pii_extractor = ContextAwarePIIExtractor(llm_client)
    
    def process_file(self,
                     context_prompt: str,
                     file_path: Optional[str] = None,
                     file_bytes: Optional[bytes] = None,
                     file_name: Optional[str] = None,
                     base64_data: Optional[str] = None,
                     pii_categories: Optional[List[str]] = None,
                     skip_context_filtering: bool = False) -> Dict:
        """
        Process a file end-to-end: extract text, identify context-relevant PII.
        
        Args:
            context_prompt: User's context/query for PII extraction
            file_path: Path to file
            file_bytes: Raw file bytes
            file_name: Filename (needed with file_bytes/base64)
            base64_data: Base64 encoded file
            pii_categories: Specific PII categories to focus on
            skip_context_filtering: If True, skip LLM filtering and return all text
            
        Returns:
            Comprehensive processing result
        """
        result = {
            'success': False,
            'extraction': None,
            'pii_analysis': None,
            'text_for_pseudonymization': '',
            'error': None
        }
        
        # Step 1: Extract text from file
        extraction = self.ocr_extractor.extract_text(
            file_path=file_path,
            file_bytes=file_bytes,
            file_name=file_name,
            base64_data=base64_data
        )
        
        result['extraction'] = extraction
        
        if not extraction['success']:
            result['error'] = extraction.get('error', 'Text extraction failed')
            return result
        
        extracted_text = extraction['text']
        
        # Step 2: Context-aware PII analysis (optional)
        if skip_context_filtering:
            result['text_for_pseudonymization'] = extracted_text
            result['success'] = True
            result['pii_analysis'] = {
                'summary': 'Context filtering skipped - full text returned',
                'relevant_pii': [],
                'excluded_pii': []
            }
        else:
            pii_analysis = self.pii_extractor.extract_contextual_pii(
                text=extracted_text,
                context_prompt=context_prompt,
                pii_categories=pii_categories
            )
            
            result['pii_analysis'] = pii_analysis
            result['text_for_pseudonymization'] = pii_analysis.get('text_for_pseudonymization', extracted_text)
            result['success'] = True
        
        return result
    
    def get_capabilities(self) -> Dict[str, bool]:
        """Return available processing capabilities."""
        return self.ocr_extractor.get_capabilities()


# Utility function for quick text extraction
def quick_extract(file_path: str) -> str:
    """
    Quick utility to extract text from a file without context filtering.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Extracted text or error message
    """
    extractor = OCRExtractor()
    result = extractor.extract_text(file_path=file_path)
    
    if result['success']:
        return result['text']
    else:
        return f"Error: {result.get('error', 'Unknown error')}"
