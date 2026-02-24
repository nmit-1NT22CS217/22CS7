"""
Enhanced PII Detection and Anonymization Module.
Handles complex entities with internal tokens using advanced spaCy NER,
custom patterns, and improved regex for multi-token PII detection.
"""
import re
import spacy
import datetime
from spacy.matcher import Matcher
from spacy.lang.en import English
from typing import Dict, List, Tuple, Set


class PIIAnonymizer:
    
    # Enhanced spaCy entity mapping with human-friendly labels
    SPACY_PII_ENTITIES = {
        'PERSON': 'PERSON_NAME',
        'GPE': 'LOCATION', 
        'ORG': 'ORGANIZATION',
        'DATE': 'DATE_TIME',
        'MONEY': 'FINANCIAL_AMOUNT',
        'FAC': 'FACILITY_NAME',
        'NORP': 'NATIONALITY_GROUP',
        'EVENT': 'EVENT_NAME',
        'LAW': 'LEGAL_DOCUMENT',
        'LANGUAGE': 'LANGUAGE_NAME',
        'WORK_OF_ART': 'ARTWORK_TITLE'
    }
    
    # Enhanced regex patterns for complex multi-token PII with context awareness
    REGEX_PATTERNS = {
        'EMAIL': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'PHONE': r'(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}(?:\s?(?:ext|extension|x)\.?\s?\d{1,5})?\b',
        'CREDIT_CARD': r'\b(?:4\d{3}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}|4\d{15}|5[1-5]\d{2}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}|5[1-5]\d{14}|3[47]\d{2}[\s-]?\d{6}[\s-]?\d{5}|3[47]\d{13}|3[0568]\d{2}[\s-]?\d{6}[\s-]?\d{4}|3[0568]\d{12}|6(?:011|5\d{2})[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}|6(?:011|5\d{2})\d{12})\b',
        'SSN': r'\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b',
        'ZIP_CODE': r'\b\d{5}(?:-\d{4})?\b',
        'ACCOUNT_ID': r'\b(?:ACC|ACCT|ID|REF|CASE|ORDER|TICKET|REQ)[-.\s#:]*\d{4,}(?:-\d+)*\b',
        'PASSPORT': r'\b[A-Z]{1,2}\d{6,9}\b',
        'DRIVER_LICENSE': r'\b[A-Z]{1,2}[-.\s]?\d{6,8}\b',
        'IP_ADDRESS': r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
        'URL': r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?',
        'MEDICAL_ID': r'\b(?:MRN|MR|PATIENT)[\s#:-]*\d{6,12}\b',
        'ADDRESS': r'\b\d+\s+(?:[A-Z][a-z]+\s+)*(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Place|Pl|Way|Circle|Cir|Parkway|Pkwy)\.?\b'
    }
    # Additional patterns for dates, times, pincodes and sensitive national IDs
    REGEX_PATTERNS.update({
        # Dates: DD/MM/YYYY, D/M/YY, YYYY-MM-DD, 12 Jan 2020, Jan 12, 2020
        'DATE': r'\b(?:\d{1,2}[\/\-\.\s]\d{1,2}[\/\-\.\s]\d{2,4}|\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*,?\s+\d{2,4})\b',
        # Times: 23:59, 11:59 PM, 7:05am, 07:05:30
        'TIME': r'\b(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?\s?(?:AM|PM|am|pm)?\b',
        # Indian PIN code (6 digits)
        'PINCODE': r'\b[1-9][0-9]{5}\b',
        # Aadhaar (India) 12 digits optionally spaced
        'AADHAAR': r'\b\d{4}\s?\d{4}\s?\d{4}\b',
        # Generic national id patterns: common prefixes used internationally
        'NATIONAL_ID': r'\b(?:ID|NID|NRIC|SSP|CNIC|SIN|NINO|CIF)[-:\s]*[A-Z0-9]{4,15}\b',
        # Military or defense IDs (heuristic): prefixed tags like 'MIL-', 'ARMY' with digits
        'MILITARY_ID': r'\b(?:MIL|ARMY|NAVY|AF|FORCE|NOC)[-:\s]*\d{3,10}\b'
    })

    # Bank check, financial and document-specific patterns
    REGEX_PATTERNS.update({
        # Cheque number with context
        'CHEQUE_NUMBER': r'\b(?:Cheque|Cheq|Chq|Cheque No|Chq No)[\s#:.]*\d{3,12}\b',
        # MICR code on cheque (9 digits) - contextually validated
        'MICR': r'\b\d{9}\b',
        # IFSC code typical format: 4 letters + 0 + 6 alnum
        'IFSC': r'\b[A-Za-z]{4}0[A-Za-z0-9]{6}\b',
        # Bank amounts with currency symbols or codes
        'BANK_AMOUNT': r'\b(?:Rs\.?|INR|USD|EUR|GBP|\$|€|£)?\s?\d{1,3}(?:[,\d]{0,3})*(?:\.\d{1,2})?\s?(?:USD|INR|Rs|EUR|€|GBP)?\b',
        # Amounts written in words often found on checks: 'Rupees Two Thousand Only'
        'AMOUNT_WORDS': r'\b(?:Rupees|Rupee|Dollars|Pounds|Euros)\s+[A-Za-z\s\-]{3,120}?Only\b',
        # Routing numbers / ABA (US) 9-digit with context
        'ROUTING_NUMBER': r'\b(?:Routing|RTN|ABA)[\s#:.]*\d{9}\b',
        # IBAN - generic international bank account pattern (starts with 2 letters + 2 digits)
        'IBAN': r'\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b'
    })
    
    # Human-friendly entity labels for better user experience
    HUMAN_LABELS = {
        'PERSON_NAME': 'Person Name',
        'LOCATION': 'Location',
        'ORGANIZATION': 'Organization',
        'DATE_TIME': 'Date/Time',
        'FINANCIAL_AMOUNT': 'Financial Amount',
        'FACILITY_NAME': 'Facility',
        'NATIONALITY_GROUP': 'Nationality/Group',
        'EVENT_NAME': 'Event',
        'LEGAL_DOCUMENT': 'Legal Document',
        'LANGUAGE_NAME': 'Language',
        'ARTWORK_TITLE': 'Artwork Title',
        'EMAIL': 'Email Address',
        'PHONE': 'Phone Number',
        'CREDIT_CARD': 'Credit Card',
        'SSN': 'Social Security Number',
        'ZIP_CODE': 'ZIP Code',
        'ACCOUNT_ID': 'Account ID',
        'PASSPORT': 'Passport Number',
        'DRIVER_LICENSE': 'Driver License',
        'ACCOUNT_NUMBER': 'Account Number',
        'EMPLOYEE_ID': 'Employee ID',
        'APPLICATION_NUMBER': 'Application Number',
        'BANK_ACCOUNT': 'Bank Account',
        'IP_ADDRESS': 'IP Address',
        'URL': 'Website URL',
        'MEDICAL_ID': 'Medical ID',
        'ADDRESS': 'Physical Address'
    }
    # Add human friendly labels for added patterns
    HUMAN_LABELS.update({
        'DATE': 'Date',
        'TIME': 'Time',
        'PINCODE': 'PIN Code',
        'AADHAAR': 'Aadhaar Number',
        'NATIONAL_ID': 'National ID',
        'MILITARY_ID': 'Military ID'
    })
    HUMAN_LABELS.update({
        'CHEQUE_NUMBER': 'Cheque Number',
        'MICR': 'MICR Code',
        'IFSC': 'IFSC Code',
        'BANK_AMOUNT': 'Bank Amount',
        'AMOUNT_WORDS': 'Amount (Words)',
        'ROUTING_NUMBER': 'Routing Number',
        'IBAN': 'IBAN'
    })
    
    def __init__(self, model_name: str = "en_core_web_sm"):
        """
        Initialize enhanced PII anonymizer with spaCy model and custom patterns.
        Sets up advanced entity recognition for complex multi-token PII.
        """
        try:
            self.nlp = spacy.load(model_name)
            self.setup_custom_patterns()
        except OSError:
            print(f"spaCy model '{model_name}' not found. Downloading...")
            import subprocess
            subprocess.run(["python", "-m", "spacy", "download", model_name])
            self.nlp = spacy.load(model_name)
            self.setup_custom_patterns()
        
        self.counter = 0
        self.mappings: Dict[str, str] = {}
    
    def setup_custom_patterns(self):
        """
        Set up custom spaCy patterns for better detection of complex PII entities
        with internal tokens, spaces, punctuation, and line breaks.
        """
        self.matcher = Matcher(self.nlp.vocab)
        
        # Pattern for multi-word names with titles (Dr. John Smith, Ms. Jane Doe, etc.)
        name_patterns = [
            [{"LOWER": {"IN": ["dr", "mr", "mrs", "ms", "prof", "professor", "captain", "sir", "madam"]}}, 
             {"IS_ALPHA": True}, 
             {"IS_ALPHA": True, "OP": "?"}],
            [{"IS_ALPHA": True, "IS_TITLE": True}, 
             {"IS_ALPHA": True, "IS_TITLE": True}, 
             {"IS_ALPHA": True, "IS_TITLE": True, "OP": "?"}]
        ]
        self.matcher.add("ENHANCED_PERSON", name_patterns)
        
        # Pattern for complex addresses with multiple components
        # Keep address patterns strict to avoid generic numeric+word matches like "150 words"
        address_patterns = [
            # Typical: number + street name + street type (e.g. "12 MG Road")
            [{"LIKE_NUM": True}, 
             {"IS_ALPHA": True, "OP": "+"}, 
             {"LOWER": {"IN": ["street", "st", "avenue", "ave", "road", "rd", "boulevard", "blvd", "drive", "dr", "lane", "ln"]}}],
            # Apartment/unit style: number + optional name + (apt|suite|unit) + optional number
            [{"LIKE_NUM": True}, 
             {"IS_ALPHA": True, "OP": "?"}, 
             {"LOWER": {"IN": ["apt", "apartment", "suite", "unit", "floor", "fl"]}}, 
             {"LIKE_NUM": True, "OP": "?"}]
        ]
        self.matcher.add("ENHANCED_ADDRESS", address_patterns)
        
        # Pattern for organization names with legal suffixes
        org_patterns = [
            [{"IS_ALPHA": True, "OP": "+"}, 
             {"LOWER": {"IN": ["inc", "corp", "llc", "ltd", "co", "company", "corporation", "incorporated", "limited"]}}],
            [{"IS_TITLE": True, "OP": "+"}, 
             {"LOWER": {"IN": ["bank", "hospital", "university", "college", "school", "clinic", "medical", "center"]}}]
        ]
        self.matcher.add("ENHANCED_ORGANIZATION", org_patterns)
        
        # Pattern for complex dates and times
        datetime_patterns = [
            [{"LIKE_NUM": True}, 
             {"TEXT": {"IN": ["/", "-", "."]}}, 
             {"LIKE_NUM": True}, 
             {"TEXT": {"IN": ["/", "-", "."]}}, 
             {"LIKE_NUM": True}],
            [{"IS_ALPHA": True, "LENGTH": {">=": 3}}, 
             {"LIKE_NUM": True}, 
             {"TEXT": ","}, 
             {"LIKE_NUM": True}]
        ]
        self.matcher.add("ENHANCED_DATETIME", datetime_patterns)
    
    def detect_pii(self, text: str) -> List[Tuple[str, str, int, int]]:
        """
        Enhanced PII detection using spaCy NER, custom patterns, and regex.
        Handles complex entities with internal tokens, spaces, punctuation, and line breaks.
        Includes special handling for key-value pairs to avoid misclassification.
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of tuples: (entity_text, entity_type, start_pos, end_pos)
        """
        entities = []
        seen_spans = set()
        
        # Process text with spaCy
        doc = self.nlp(text)
        
        # SPECIAL HANDLING: Detect key-value pairs first
        self._detect_key_value_pairs(text, entities, seen_spans)
        
        # FIRST: Process regex patterns in priority order (more specific patterns first)
        # Order matters! Process longer/more specific patterns before shorter ones
        pattern_priority = [
            'CREDIT_CARD',  # Must come before PHONE (16 digits vs 10 digits)
            'SSN',          # Must come before general number patterns
            'AADHAAR',
            'PINCODE',
            'DATE',
            'TIME',
            'NATIONAL_ID',
            'MILITARY_ID',
            'CHEQUE_NUMBER',
            'MICR',
            'IFSC',
            'BANK_AMOUNT',
            'AMOUNT_WORDS',
            'ROUTING_NUMBER',
            'IBAN',
            'EMAIL',        # Specific format
            'PHONE',        # After credit card
            'ACCOUNT_ID',   # Before general patterns
            'ZIP_CODE',     # Specific 5-digit pattern
            'IP_ADDRESS',   # Specific format
            'URL',          # Specific format
            'PASSPORT',
            'DRIVER_LICENSE',
            'MEDICAL_ID',
            'ADDRESS',
        ]
        
        # Process patterns in priority order
        for entity_type in pattern_priority:
            if entity_type not in self.REGEX_PATTERNS:
                continue
                
            pattern = self.REGEX_PATTERNS[entity_type]
            for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                span = (match.start(), match.end())
                entity_text = match.group()
                
                # Skip if already covered by key-value detection or previous patterns
                if self._overlaps_with_existing(span, seen_spans):
                    continue
                
                # Additional validation for specific entity types
                if self._validate_entity(entity_text, entity_type):
                    entities.append((entity_text, entity_type, match.start(), match.end()))
                    seen_spans.add(span)
                    seen_spans.add(span)
        
        # SECOND: Process spaCy NER entities (but avoid overlaps with regex)
        for ent in doc.ents:
            if ent.label_ in self.SPACY_PII_ENTITIES:
                span = (ent.start_char, ent.end_char)
                
                # Skip if already covered by regex patterns or key-value pairs
                if self._overlaps_with_existing(span, seen_spans):
                    continue
                
                # Filter out very short entities that are likely false positives
                if len(ent.text.strip()) < 2:
                    continue
                
                # Enhanced validation for spaCy entities
                entity_label = self.SPACY_PII_ENTITIES.get(ent.label_, ent.label_)
                if self._validate_entity(ent.text, entity_label):
                    entities.append((ent.text, entity_label, ent.start_char, ent.end_char))
                    seen_spans.add(span)
        
        # THIRD: Custom pattern matching for complex entities (lowest priority)
        matches = self.matcher(doc)
        for match_id, start, end in matches:
            span_doc = doc[start:end]
            entity_text = span_doc.text
            match_label = self.nlp.vocab.strings[match_id]
            
            # Skip if already covered
            span = (span_doc.start_char, span_doc.end_char)
            if self._overlaps_with_existing(span, seen_spans):
                continue
            
            # Additional validation for custom patterns
            if len(entity_text.strip()) < 3:
                continue
            
            # Map custom patterns to entity types
            if match_label == "ENHANCED_PERSON":
                entity_type = "PERSON_NAME"
            elif match_label == "ENHANCED_ADDRESS":
                entity_type = "ADDRESS"
            elif match_label == "ENHANCED_ORGANIZATION":
                entity_type = "ORGANIZATION"
            elif match_label == "ENHANCED_DATETIME":
                entity_type = "DATE_TIME"
            else:
                entity_type = match_label
            
            if self._validate_entity(entity_text, entity_type):
                entities.append((entity_text, entity_type, span_doc.start_char, span_doc.end_char))
                seen_spans.add(span)
        
        # Sort by start position (important for replacement)
        entities.sort(key=lambda x: x[2])
        
        return entities
    
    def _detect_key_value_pairs(self, text: str, entities: List, seen_spans: Set):
        """
        Special detection for key-value pairs to avoid misclassification.
        Handles patterns like "Name: John Doe", "Phone Number: +1 234 567 8901", etc.
        """
        # Pattern for key-value pairs
        kv_patterns = [
            (r'Account\s+Number:\s*(\d{8,17})', 'ACCOUNT_NUMBER'),
            (r'Employee\s+ID:\s*(\w{3,15})', 'EMPLOYEE_ID'),
            (r'Application\s+Number:\s*(\w{3,15})', 'APPLICATION_NUMBER'),
            (r'Phone\s+Number:\s*(\+?[0-9\s\(\)\-\.]{10,20})', 'PHONE'),
            (r'Name:\s*([A-Z][a-zA-Z\s]{2,30})', 'PERSON_NAME'),
        ]
        
        for pattern, entity_type in kv_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                value = match.group(1).strip()
                value_start = match.start(1)
                value_end = match.end(1)
                
                # Validate the extracted value
                if self._validate_entity(value, entity_type):
                    entities.append((value, entity_type, value_start, value_end))
                    seen_spans.add((value_start, value_end))
    
    def _validate_entity(self, entity_text: str, entity_type: str) -> bool:
        """
        Enhanced validation to reduce false positives and improve context recognition.
        
        Args:
            entity_text: The detected entity text
            entity_type: The type of entity
            
        Returns:
            True if the entity is valid
        """
        text = entity_text.strip()
        
        # Common field labels that should not be treated as person names
        field_labels = {
            'phone number', 'email', 'address', 'account number', 'employee id', 
            'application number', 'name', 'contact', 'information', 'details',
            'verification', 'request', 'department', 'status', 'update', 'date',
            'salary', 'position', 'title', 'id', 'number', 'code', 'reference',
            'date of birth', 'first name', 'last name', 'document number', 
            'social security number', 'passport number', 'driver license', 
            'license number', 'credit card number', 'phone', 'mobile', 'cell'
        }
        
        # Common organizational terms that shouldn't be person names
        org_terms = {
            'hr', 'human resources', 'department', 'team', 'company', 'corporation',
            'inc', 'llc', 'ltd', 'co', 'organization', 'office', 'division'
        }
        
        # Skip field labels ONLY for unstructured entity types (not for structured data like EMAIL, PHONE, etc.)
        # Structured data types (EMAIL, PHONE, SSN, etc.) should be validated by their own rules
        text_lower = text.lower().strip()
        
        # Only apply field label filtering for unstructured entity types
        if entity_type in ['PERSON_NAME', 'ORGANIZATION', 'LOCATION']:
            if text_lower in field_labels or any(label in text_lower for label in field_labels):
                return False
        
        # If detected as PERSON_NAME, validate it's actually a person name
        if entity_type == 'PERSON_NAME':
            text_lower = text.lower()
            
            # Reject common field labels
            if text_lower in field_labels:
                return False
                
            # Reject organizational terms
            if text_lower in org_terms:
                return False
                
            # Reject if it contains common field patterns
            if any(pattern in text_lower for pattern in ['number', 'id', 'code', 'account', 'employee']):
                return False
                
            # Reject single words that are likely not names (unless common first names)
            common_first_names = {'john', 'jane', 'michael', 'sarah', 'david', 'mary', 'james', 'jennifer'}
            if len(text.split()) == 1 and text_lower not in common_first_names:
                if not text[0].isupper():  # Names should start with capital
                    return False
        
        # Enhanced phone number validation
        elif entity_type == 'PHONE':
            # Should contain enough digits and proper format
            digits = re.findall(r'\d', text)
            if len(digits) < 7:  # Minimum phone length
                return False
            
            if len(digits) < 10 and not re.search(r'[\(\)\-\.\s]', text):
                # Less than 10 digits should have separators
                return False
            
            # Reject if it looks like an account number or ID (too long)
            if len(digits) > 15:  # Too long for phone
                return False
            
            # Reject if it's 13+ consecutive digits (likely credit card or account number)
            if len(digits) >= 13:
                # Check if digits are consecutive (no separators)
                clean_text = ''.join(c for c in text if c.isdigit())
                if len(clean_text) >= 13:
                    return False
                
            # Should have phone-like separators if more than 11 digits
            if len(digits) > 11 and not re.search(r'[\(\)\-\.\s]', text):
                return False
        
        # Enhanced account number validation
        elif entity_type == 'ACCOUNT_NUMBER':
            digits = re.findall(r'\d', text)
            # Account numbers are typically 8-17 digits
            return 8 <= len(digits) <= 17
            
        elif entity_type == 'EMPLOYEE_ID':
            # Should have letters and/or numbers, reasonable length
            return len(text) >= 3 and len(text) <= 15
            
        elif entity_type == 'APPLICATION_NUMBER':
            # Should have letters and/or numbers, reasonable length
            return len(text) >= 3 and len(text) <= 15
        
        elif entity_type == 'EMAIL':
            # Enhanced email validation
            if '@' not in text:
                return False
            
            parts = text.split('@')
            if len(parts) != 2:
                return False
            
            local, domain = parts
            
            # Local part must exist and be reasonable
            if not local or len(local) < 1:
                return False
            
            # Domain must have at least one dot and valid parts
            if '.' not in domain:
                return False
            
            domain_parts = domain.split('.')
            if len(domain_parts) < 2:
                return False
            
            # All domain parts must exist
            if any(not part for part in domain_parts):
                return False
            
            return True
        
        elif entity_type == 'CREDIT_CARD':
            # Should have enough digits and match known card patterns
            digits = re.findall(r'\d', text)
            if not (13 <= len(digits) <= 19):
                return False
            
            # Get all digits as a string to check prefix
            digit_string = ''.join(digits)
            
            # Validate it starts with a known card prefix
            if digit_string[0] == '3':  # Amex, Diners
                if len(digit_string) not in [14, 15]:
                    return False
            elif digit_string[0] == '4':  # Visa (13 or 16 digits)
                if len(digit_string) not in [13, 16]:
                    return False
            elif digit_string[0] == '5':  # Mastercard (16 digits)
                if len(digit_string) != 16:
                    return False
                if digit_string[1] not in '12345':  # 51-55
                    return False
            elif digit_string[0] == '6':  # Discover (16 digits)
                if len(digit_string) != 16:
                    return False
            else:
                # Invalid prefix
                return False
            
            return True
        
        elif entity_type == 'SSN':
            # Should have exactly 9 digits
            digits = re.findall(r'\d', text)
            return len(digits) == 9
        
        elif entity_type == 'IP_ADDRESS':
            # Basic IP validation
            parts = text.split('.')
            if len(parts) != 4:
                return False
            try:
                return all(0 <= int(part) <= 255 for part in parts)
            except ValueError:
                return False
        
        elif entity_type == 'URL':
            # Should contain protocol or domain-like structure
            return any(protocol in text.lower() for protocol in ['http', 'www', '.com', '.org', '.net'])
        
        elif entity_type == 'DATE_TIME':
            # Reject ZIP codes (5 digits) - these are now handled by ZIP_CODE pattern
            if re.match(r'^\d{5}(?:-\d{4})?$', text.strip()):
                return False
            
            # Reject account IDs - these are now handled by ACCOUNT_ID pattern
            if re.match(r'^[A-Z]{2,4}[-.\s#:]*\d{4,}', text.strip(), re.IGNORECASE):
                return False
            
            # Reject pure numeric strings that are too short or too long for dates
            if text.strip().isdigit():
                digit_count = len(text.strip())
                # Valid date numbers: 1-2 digits (day), 4 digits (year), 6-8 digits (YYYYMMDD)
                if digit_count == 5 or digit_count == 7 or digit_count > 8:
                    return False
            
            # Reject if it looks like an ID or code (has dashes and multiple segments)
            if text.count('-') >= 2 and any(c.isalpha() for c in text):
                return False
            
            return True
        
        elif entity_type == 'ZIP_CODE':
            # Validate US ZIP code format
            return re.match(r'^\d{5}(?:-\d{4})?$', text.strip()) is not None

        elif entity_type == 'PINCODE':
            # Indian PIN: 6 digits, cannot start with 0
            return re.match(r'^[1-9][0-9]{5}$', text.strip()) is not None

        elif entity_type == 'AADHAAR':
            # Aadhaar: 12 digits, optionally spaced as 4 4 4
            clean = re.sub(r'\s', '', text)
            return re.match(r'^\d{12}$', clean) is not None

        elif entity_type == 'DATE':
            # Basic sanity checks for date formats recognized by regex
            t = text.strip()
            # Reject if purely numeric long strings (likely IDs)
            if re.match(r'^\d{8,}$', t):
                return False
            # Try to parse common formats to validate
            date_formats = ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d %b %Y', '%d %B %Y', '%b %d, %Y', '%B %d, %Y', '%d/%m/%y']
            for fmt in date_formats:
                try:
                    datetime.datetime.strptime(t, fmt)
                    return True
                except Exception:
                    continue
            # As a fallback, accept if pattern matched earlier (let caller trust regex)
            return True

        elif entity_type == 'TIME':
            # Validate time strings like HH:MM[:SS] with optional AM/PM
            t = text.strip()
            if re.match(r'^(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?\s?(?:AM|PM|am|pm)?$', t):
                return True
            return False

        elif entity_type in ['NATIONAL_ID', 'MILITARY_ID']:
            # Heuristic checks: length and presence of digits/letters
            clean = re.sub(r'[^A-Za-z0-9]', '', text)
            return 5 <= len(clean) <= 15
        
        elif entity_type == 'ACCOUNT_ID':
            # Validate account ID format
            if len(text.strip()) < 5:
                return False
            # Must have prefix and numbers
            return re.match(r'^[A-Z]{2,4}[-.\s#:]*\d{4,}', text.strip(), re.IGNORECASE) is not None

        elif entity_type == 'ADDRESS':
            # Reject phrases like '150 words' or other non-address numeric+word patterns
            if re.match(r'^\d+\s+words\b', text.lower()):
                return False
            # Must be reasonably long and contain letters
            if len(text.strip()) < 5:
                return False
            if not re.search(r'[a-zA-Z]', text):
                return False
            return True
        
        # For organizations, validate they're not field labels
        elif entity_type == 'ORGANIZATION':
            text_lower = text.lower()
            if text_lower in field_labels:
                return False

        elif entity_type == 'CHEQUE_NUMBER':
            # Accept cheque numbers when context is present or length reasonable
            digits = re.findall(r'\d', text)
            if 'cheq' in text.lower() or 'cheque' in text.lower() or 'chq' in text.lower():
                return 3 <= len(digits) <= 12
            return 6 <= len(digits) <= 12

        elif entity_type == 'MICR':
            digits = re.findall(r'\d', text)
            return len(digits) == 9

        elif entity_type == 'IFSC':
            return re.match(r'^[A-Za-z]{4}0[A-Za-z0-9]{6}$', text.strip()) is not None

        elif entity_type == 'BANK_AMOUNT':
            # Remove currency symbols and separators then try parse
            clean = re.sub(r'[\$,€£\s]', '', text)
            clean = clean.replace('Rs.', '').replace('INR', '')
            clean = clean.replace(',', '')
            if re.match(r'^\d+(?:\.\d+)?$', clean):
                try:
                    return float(clean) >= 0
                except Exception:
                    return False
            return False

        elif entity_type == 'AMOUNT_WORDS':
            t = text.strip()
            return bool(re.search(r'\b(?:Rupees|Rupee|Dollars|Pounds|Euros)\b', t, re.IGNORECASE) and 'only' in t.lower())

        elif entity_type == 'ROUTING_NUMBER':
            digits = re.findall(r'\d', text)
            return len(digits) == 9

        elif entity_type == 'IBAN':
            return re.match(r'^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$', text.strip().upper()) is not None
        
        return True
    
    def _overlaps_with_existing(self, span: Tuple[int, int], seen_spans: Set[Tuple[int, int]]) -> bool:
        """
        Check if a span overlaps with any existing spans to prevent duplicates.
        Uses a more sophisticated overlap detection to handle partial overlaps.
        
        Args:
            span: Tuple of (start, end) positions
            seen_spans: Set of already detected spans
            
        Returns:
            True if span overlaps with any existing span
        """
        start, end = span
        for seen_start, seen_end in seen_spans:
            # Check for any overlap with tolerance for entity boundaries
            overlap_start = max(start, seen_start)
            overlap_end = min(end, seen_end)
            
            # Consider overlapping if they share more than 20% of the smaller entity
            if overlap_start < overlap_end:
                overlap_length = overlap_end - overlap_start
                smaller_entity_length = min(end - start, seen_end - seen_start)
                
                # If overlap is more than 20% of smaller entity, consider it a duplicate
                if overlap_length / smaller_entity_length > 0.2:
                    return True
        return False
    
    def pseudonymize(self, text: str, allowed_labels: list = None) -> Tuple[str, Dict[str, str]]:
        """
        Enhanced pseudonymization with human-friendly labels for complex PII entities.
        Replace PII with descriptive, reversible pseudonyms using industry standards.
        
        Args:
            text: Input text containing PII
            
        Returns:
            Tuple of (anonymized_text, entity_mapping)
        """
        entities = self.detect_pii(text)
        self.counter = 0
        self.mappings = {}
        
        # Initialize entity counters for type-specific numbering
        entity_counters = {}
        
        # Track value-to-placeholder mapping to reuse same placeholder for identical values
        value_to_placeholder = {}
        
        # Process entities in correct order for position tracking
        result = text
        offset = 0
        
        for entity_text, entity_type, start, end in entities:
            # Check if we've seen this exact value before
            cache_key = f"{entity_type}:{entity_text}"

            # If allow-list provided, skip entities whose human label is not allowed
            human_label = self.HUMAN_LABELS.get(entity_type, entity_type)
            if allowed_labels is not None and human_label not in allowed_labels:
                continue
            
            if cache_key in value_to_placeholder:
                # Reuse existing placeholder for same value
                placeholder = value_to_placeholder[cache_key]
            else:
                # Generate new placeholder for new value
                # Create context-aware pseudonyms with type-specific counters
                if entity_type in entity_counters:
                    entity_counters[entity_type] += 1
                else:
                    entity_counters[entity_type] = 1
                
                count = entity_counters[entity_type]
                
                # LLM-friendly pseudonym generation with semantic labels
                if entity_type == "PERSON_NAME":
                    placeholder = f"name_{count}"
                elif entity_type == "ORGANIZATION":
                    placeholder = f"company_{count}"
                elif entity_type == "LOCATION":
                    placeholder = f"location_{count}"
                elif entity_type == "EMAIL":
                    placeholder = f"email_{count}"
                elif entity_type == "PHONE":
                    placeholder = f"mobNo_{count}"
                elif entity_type == "ADDRESS":
                    placeholder = f"physical_address_{count}"
                elif entity_type == "DATE_TIME":
                    placeholder = f"date_{count}"
                elif entity_type == "DATE":
                    placeholder = f"date_{count}"
                elif entity_type == "TIME":
                    placeholder = f"time_{count}"
                elif entity_type == "PINCODE":
                    placeholder = f"pincode_{count}"
                elif entity_type == "AADHAAR":
                    placeholder = f"aadhaar_{count}"
                elif entity_type == "NATIONAL_ID":
                    placeholder = f"national_id_{count}"
                elif entity_type == "MILITARY_ID":
                    placeholder = f"military_id_{count}"
                elif entity_type == "CREDIT_CARD":
                    placeholder = f"credit_card_{count}"
                elif entity_type == "SSN":
                    placeholder = f"ssn_{count}"
                elif entity_type == "ZIP_CODE":
                    placeholder = f"zipcode_{count}"
                elif entity_type == "ACCOUNT_ID":
                    placeholder = f"account_id_{count}"
                elif entity_type == "MEDICAL_ID":
                    placeholder = f"medical_id_{count}"
                elif entity_type == "FINANCIAL_AMOUNT":
                    placeholder = f"amount_{count}"
                elif entity_type == "IP_ADDRESS":
                    placeholder = f"ip_address_{count}"
                elif entity_type == "URL":
                    placeholder = f"url_{count}"
                elif entity_type == "PASSPORT":
                    placeholder = f"passport_{count}"
                elif entity_type == "DRIVER_LICENSE":
                    placeholder = f"driver_license_{count}"
                elif entity_type == "ACCOUNT_NUMBER":
                    placeholder = f"account_number_{count}"
                elif entity_type == "EMPLOYEE_ID":
                    placeholder = f"employee_id_{count}"
                elif entity_type == "APPLICATION_NUMBER":
                    placeholder = f"application_number_{count}"
                elif entity_type == "BANK_ACCOUNT":
                    placeholder = f"bank_account_{count}"
                elif entity_type == 'CHEQUE_NUMBER':
                    placeholder = f"cheque_{count}"
                elif entity_type == 'MICR':
                    placeholder = f"micr_{count}"
                elif entity_type == 'IFSC':
                    placeholder = f"ifsc_{count}"
                elif entity_type == 'BANK_AMOUNT':
                    placeholder = f"bank_amount_{count}"
                elif entity_type == 'AMOUNT_WORDS':
                    placeholder = f"amount_words_{count}"
                elif entity_type == 'ROUTING_NUMBER':
                    placeholder = f"routing_{count}"
                elif entity_type == 'IBAN':
                    placeholder = f"iban_{count}"
                elif entity_type == "FACILITY_NAME":
                    placeholder = f"facility_{count}"
                elif entity_type == "EVENT_NAME":
                    placeholder = f"event_{count}"
                elif entity_type == "LEGAL_DOCUMENT":
                    placeholder = f"document_{count}"
                elif entity_type == "NATIONALITY_GROUP":
                    placeholder = f"group_{count}"
                elif entity_type == "LANGUAGE_NAME":
                    placeholder = f"language_{count}"
                elif entity_type == "ARTWORK_TITLE":
                    placeholder = f"artwork_{count}"
                else:
                    # Generic pseudonym for other entity types with clean naming
                    clean_type = entity_type.lower().replace('_', '_').replace(' ', '_')
                    placeholder = f"{clean_type}_{count}"
                
                # Store mapping for reversibility and cache
                self.mappings[placeholder] = entity_text
                value_to_placeholder[cache_key] = placeholder
            
            # Replace in text with offset adjustment
            result = result[:start + offset] + placeholder + result[end + offset:]
            offset += len(placeholder) - (end - start)
        
        return result, self.mappings
    
    def mask(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Enhanced masking for complex PII entities with intelligent partial reveal.
        Partially mask PII while preserving structure and readability.
        
        Note: This is a ONE-WAY transformation for display purposes only.
        Masked text cannot be deanonymized back to original values.
        
        Args:
            text: Input text containing PII
            
        Returns:
            Tuple of (masked_text, empty_dict) - mappings not stored for mask mode
        """
        entities = self.detect_pii(text)
        
        result = text
        offset = 0
        
        for entity_text, entity_type, start, end in entities:
            # For mask mode we cannot store mappings, but respect allowed_labels if provided
            # If allowed_labels is None, mask everything detected; otherwise, skip those not allowed
            # Note: mask signature limited; we'll support an attribute on self for temporary allowed_labels
            allowed_labels = getattr(self, '_allowed_labels_temp', None)
            human_label = self.HUMAN_LABELS.get(entity_type, entity_type)
            if allowed_labels is not None and human_label not in allowed_labels:
                continue
            # Create intelligently masked version based on entity type
            if entity_type == 'EMAIL':
                # Show first char of username and full domain
                parts = entity_text.split('@')
                if len(parts) == 2:
                    username_len = len(parts[0])
                    if username_len > 3:
                        masked = f"{parts[0][:2]}{'*' * (username_len - 2)}@{parts[1]}"
                    else:
                        masked = f"{parts[0][0]}{'*' * (username_len - 1)}@{parts[1]}"
                else:
                    masked = entity_text[0] + '*' * (len(entity_text) - 1)
            
            elif entity_type == 'CREDIT_CARD':
                # Show first 4 and last 4 digits, mask middle
                clean_number = re.sub(r'[-\s]', '', entity_text)
                if len(clean_number) >= 8:
                    masked = clean_number[:4] + '-XXXX-XXXX-' + clean_number[-4:]
                else:
                    masked = clean_number[:2] + '*' * (len(clean_number) - 2)
            
            elif entity_type == 'PHONE':
                # Preserve area code format, mask number
                if re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', entity_text):
                    masked = re.sub(r'(?<=\d{3}[-.\s()])\d(?=.*\d{3})', 'X', entity_text)
                else:
                    masked = entity_text[:3] + 'X' * (len(entity_text) - 3)
            
            elif entity_type == 'SSN':
                # Show first 3 digits, mask rest
                if '-' in entity_text:
                    parts = entity_text.split('-')
                    masked = f"{parts[0]}-XX-XXXX"
                else:
                    masked = entity_text[:3] + 'X' * (len(entity_text) - 3)
            
            elif entity_type == 'ZIP_CODE':
                # Mask last 2 digits of ZIP code
                if '-' in entity_text:
                    # Handle ZIP+4 format
                    parts = entity_text.split('-')
                    masked = f"{parts[0][:3]}**-****"
                else:
                    # Standard 5-digit ZIP
                    masked = entity_text[:3] + '**'
            
            elif entity_type == 'ACCOUNT_ID':
                # Show prefix and last few chars, mask middle
                if len(entity_text) > 6:
                    # Find where numbers start
                    digit_start = next((i for i, c in enumerate(entity_text) if c.isdigit()), 0)
                    if digit_start > 0:
                        prefix = entity_text[:digit_start]
                        rest = entity_text[digit_start:]
                        if len(rest) > 4:
                            masked = prefix + '*' * (len(rest) - 1) + rest[-1]
                        else:
                            masked = prefix + '*' * len(rest)
                    else:
                        masked = entity_text[:2] + '*' * (len(entity_text) - 3) + entity_text[-1]
                else:
                    masked = entity_text[0] + '*' * (len(entity_text) - 1)
            
            elif entity_type in ['PERSON_NAME', 'ORGANIZATION']:
                # Show first letter of each word, mask rest
                words = entity_text.split()
                masked_words = []
                for word in words:
                    if len(word) > 2:
                        masked_words.append(word[0] + '*' * (len(word) - 1))
                    elif len(word) == 2:
                        masked_words.append(word[0] + '*')
                    else:
                        masked_words.append('*')
                masked = ' '.join(masked_words)
            
            elif entity_type == 'ADDRESS':
                # Show street number and first letter of street name
                address_parts = entity_text.split()
                if len(address_parts) > 1 and address_parts[0].isdigit():
                    masked_parts = [address_parts[0]]  # Keep street number
                    for part in address_parts[1:]:
                        if len(part) > 1:
                            masked_parts.append(part[0] + '*' * (len(part) - 1))
                        else:
                            masked_parts.append('*')
                    masked = ' '.join(masked_parts)
                else:
                    # Fallback to first letter masking
                    words = entity_text.split()
                    masked_words = [w[0] + '*' * (len(w) - 1) if len(w) > 1 else '*' for w in words]
                    masked = ' '.join(masked_words)
            
            elif entity_type == 'IP_ADDRESS':
                # Show first octet, mask rest
                octets = entity_text.split('.')
                if len(octets) == 4:
                    masked = f"{octets[0]}.XXX.XXX.XXX"
                else:
                    masked = entity_text[:3] + '*' * (len(entity_text) - 3)
            
            elif entity_type == 'URL':
                # Show domain, mask path
                if '://' in entity_text:
                    protocol, rest = entity_text.split('://', 1)
                    if '/' in rest:
                        domain, path = rest.split('/', 1)
                        masked = f"{protocol}://{domain}/***"
                    else:
                        masked = entity_text
                else:
                    masked = entity_text[:5] + '*' * max(0, len(entity_text) - 5)
            
            else:
                # Generic masking: show first character of each word
                words = entity_text.split()
                if len(words) > 1:
                    masked_words = [w[0] + '*' * (len(w) - 1) if len(w) > 1 else '*' for w in words]
                    masked = ' '.join(masked_words)
                else:
                    # Single word: show first and last char if long enough
                    if len(entity_text) > 3:
                        masked = entity_text[0] + '*' * (len(entity_text) - 2) + entity_text[-1]
                    elif len(entity_text) > 1:
                        masked = entity_text[0] + '*' * (len(entity_text) - 1)
                    else:
                        masked = '*'
            
            # Replace in text (no mapping stored - this is irreversible)
            result = result[:start + offset] + masked + result[end + offset:]
            offset += len(masked) - (end - start)
        
        return result, {}
    
    def replace(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Enhanced replacement with human-friendly entity type labels.
        Replace PII with descriptive entity labels using industry standards.
        
        Note: This is a ONE-WAY transformation for display purposes only.
        Replaced text cannot be deanonymized back to original values.
        
        Args:
            text: Input text containing PII
            
        Returns:
            Tuple of (replaced_text, empty_dict) - mappings not stored for replace mode
        """
        entities = self.detect_pii(text)
        
        result = text
        offset = 0
        
        for entity_text, entity_type, start, end in entities:
            # Respect allowed_labels if set temporarily on the instance
            allowed_labels = getattr(self, '_allowed_labels_temp', None)
            human_label = self.HUMAN_LABELS.get(entity_type, entity_type)
            if allowed_labels is not None and human_label not in allowed_labels:
                continue
            # Use human-friendly labels from our mapping
            human_label = self.HUMAN_LABELS.get(entity_type, entity_type.replace('_', ' ').title())
            placeholder = f"[{human_label}]"
            
            # Replace in text (no mapping stored - this is irreversible)
            result = result[:start + offset] + placeholder + result[end + offset:]
            offset += len(placeholder) - (end - start)
        
        return result, {}
    
    def get_detection_stats(self, text: str) -> Dict[str, int]:
        """
        Get statistics about PII entities detected in the text.
        Useful for understanding what types of sensitive data are present.
        
        Args:
            text: Input text to analyze
            
        Returns:
            Dictionary with entity counts by type
        """
        entities = self.detect_pii(text)
        stats = {}
        
        for _, entity_type, _, _ in entities:
            human_label = self.HUMAN_LABELS.get(entity_type, entity_type)
            stats[human_label] = stats.get(human_label, 0) + 1
        
        return stats
    
    def preview_detection(self, text: str, max_examples: int = 3) -> Dict[str, List[str]]:
        """
        Preview what entities would be detected without anonymizing.
        Useful for validation before applying anonymization.
        
        Args:
            text: Input text to analyze
            max_examples: Maximum number of examples to show per entity type
            
        Returns:
            Dictionary mapping entity types to example detected entities
        """
        entities = self.detect_pii(text)
        preview = {}
        
        for entity_text, entity_type, _, _ in entities:
            human_label = self.HUMAN_LABELS.get(entity_type, entity_type)
            
            if human_label not in preview:
                preview[human_label] = []
            
            # Add unique examples up to max_examples
            if entity_text not in preview[human_label] and len(preview[human_label]) < max_examples:
                preview[human_label].append(entity_text)
        
        return preview
    
    def anonymize(self, text: str, mode: str = 'pseudonymize') -> Tuple[str, Dict[str, str]]:
        """
        Anonymize text using specified mode.
        
        Args:
            text: Input text containing PII
            mode: Anonymization mode
                - 'pseudonymize': Reversible, creates mappings for deanonymization
                - 'mask': Irreversible, partial masking for display
                - 'replace': Irreversible, human-friendly labels for display
            
        Returns:
            Tuple of (anonymized_text, mappings_dict)
            Note: mappings_dict is empty for 'mask' and 'replace' modes
        """
        if mode == 'pseudonymize':
            return self.pseudonymize(text)
        elif mode == 'mask':
            return self.mask(text)
        elif mode == 'replace':
            return self.replace(text)
        else:
            raise ValueError(f"Unknown anonymization mode: {mode}")
    
    def deanonymize(self, text: str, mappings: Dict[str, str]) -> str:
        """
        Restore original PII using stored mappings.
        
        Note: Only works with text from 'pseudonymize' mode.
        Text from 'mask' or 'replace' modes cannot be deanonymized.
        
        Args:
            text: Pseudonymized text (from pseudonymize mode)
            mappings: Dictionary of placeholder -> original value
            
        Returns:
            Deanonymized text with original PII restored
        """
        result = text

        # Sort mappings by key length (longest first) to avoid partial replacements
        sorted_mappings = sorted(mappings.items(), key=lambda x: len(x[0]), reverse=True)

        # Use word-boundary, case-insensitive replacement to catch variants like 'Name_1' or 'NAME_1'
        for placeholder, original in sorted_mappings:
            try:
                pattern = re.compile(r"\b" + re.escape(placeholder) + r"\b", flags=re.IGNORECASE)

                def _replace(match):
                    matched_text = match.group(0)
                    # If the placeholder was all uppercase, preserve that style
                    if matched_text.isupper():
                        return original.upper()
                    # If the placeholder starts with uppercase (e.g., 'Name_1') return original as-is
                    if matched_text[0].isupper():
                        return original
                    # Default: return original
                    return original

                result = pattern.sub(_replace, result)
            except re.error:
                # Fallback to simple replace if regex fails for any reason
                result = result.replace(placeholder, original)

        return result
