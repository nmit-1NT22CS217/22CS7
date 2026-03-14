"""
LLM Client for Groq API integration with mock fallback.
"""
import os
from typing import Optional

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("Groq library not installed. Run: pip install groq")


class GroqClient:
    """Client for interacting with Groq LLM API."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.3-70b-versatile"):
        """
        Initialize Groq client.
        
        Args:
            api_key: Groq API key
            model: Model to use (default: llama-3.3-70b-versatile)
        """
        self.api_key = api_key
        self.model = model
        self.mock_mode = not (api_key and GROQ_AVAILABLE)
        
        if not GROQ_AVAILABLE:
            print("Running in MOCK mode (Groq library not available)")
            self.client = None
        elif self.mock_mode:
            print("Running in MOCK mode (no API key provided)")
            self.client = None
        else:
            self.client = Groq(api_key=self.api_key)
            print(f"Running in API mode with Groq")
            print(f"   Model: {self.model}")
            print(f"   API Key: {self.api_key[:20]}...{self.api_key[-4:]}")
    
    def generate_response(self, prompt: str) -> str:
        """
        Generate LLM response for given prompt.
        
        Args:
            prompt: Input prompt text
            
        Returns:
            LLM generated response
        """
        if self.mock_mode:
            return self._mock_response(prompt)
        
        try:
            return self._call_groq_api(prompt)
        except Exception as e:
            print(f"Error calling Groq API: {e}")
            print("Falling back to mock response...")
            return self._mock_response(prompt)
    
    def _call_groq_api(self, prompt: str) -> str:
        """
        Call actual Groq API.
        
        Args:
            prompt: Input prompt text
            
        Returns:
            API response text
        """
        print(f"\nCalling Groq API...")
        print(f"   Model: {self.model}")
        print(f"   Prompt length: {len(prompt)} chars")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant. Respond naturally to the user's message."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=4096
            )
            
            generated_text = response.choices[0].message.content
            print(f"Generated text length: {len(generated_text)} chars")
            return generated_text
            
        except Exception as e:
            print(f"API call failed: {str(e)}")
            raise
    
    def _mock_response(self, prompt: str) -> str:
        """
        Generate mock LLM response for testing.
        
        Args:
            prompt: Input prompt text
            
        Returns:
            Mock response text
        """
        import json as _json
        import re as _re
        
        # Detect if this is a PII relevance filter request (hybrid approach)
        if 'relevant_indices' in prompt and 'DETECTED PII ITEMS' in prompt:
            return self._mock_pii_filter(prompt)
        
        # Detect if this is a context-aware PII extraction request (legacy)
        if 'relevant_pii' in prompt and 'excluded_pii' in prompt and 'TEXT TO ANALYZE' in prompt:
            return self._mock_pii_extraction(prompt)
        
        # Simple mock that echoes back with some context
        word_count = len(prompt.split())
        
        response = f"""[MOCK LLM RESPONSE]

I received your message with {word_count} words. 

Here's my response based on the anonymized input:

Thank you for your message. I understand you've shared some information with me. 
I can see references to various entities and details in your text. 

If this were a real LLM interaction, I would provide a thoughtful response 
based on the content you've shared, while being mindful that some information 
has been anonymized for privacy protection.

Is there anything specific you'd like me to help you with regarding this information?

[This is a mock response. Configure GROQ_API_KEY in .env for real LLM integration]
"""
        return response
    
    def _mock_pii_filter(self, prompt: str) -> str:
        """
        Mock the hybrid filter response.
        Parses the detected PII list from the prompt, matches types against
        context keywords, and returns relevant_indices.
        """
        import json as _json
        import re as _re
        
        # Extract context query
        ctx_match = _re.search(r"USER'S CONTEXT/QUERY:\s*\"\"\"([\s\S]*?)\"\"\"", prompt)
        context = ctx_match.group(1).strip() if ctx_match else ''
        context_lower = context.lower()
        
        # Parse detected PII items: [i] Type: XXX, Value: "YYY"
        items = _re.findall(r'\[(\d+)\]\s*Type:\s*(\w+)', prompt)
        
        # Keyword mapping (mirrors ocr_extractor._keyword_fallback — all 63 types)
        type_keywords = {
            'name': {'PERSON_NAME', 'PERSON', 'NAME'},
            'person': {'PERSON_NAME', 'PERSON', 'NAME'},
            'identity': {'PERSON_NAME', 'PASSPORT', 'PASSPORT_US', 'PASSPORT_UK', 'PASSPORT_INDIA', 'DRIVER_LICENSE', 'INDIA_DL', 'SSN', 'INDIA_PAN', 'INDIA_AADHAAR', 'UK_NIN', 'CANADA_SIN', 'AUSTRALIA_TFN'},
            'nationality': {'NATIONALITY_GROUP'},
            'language': {'LANGUAGE_NAME'},
            'phone': {'PHONE', 'PHONE_NUMBER', 'MOBILE'},
            'mobile': {'PHONE', 'PHONE_NUMBER', 'MOBILE'},
            'contact': {'PHONE', 'EMAIL', 'PHONE_NUMBER', 'ADDRESS', 'LOCALITY'},
            'email': {'EMAIL', 'EMAIL_ADDRESS'},
            'mail': {'EMAIL', 'EMAIL_ADDRESS'},
            'address': {'ADDRESS', 'LOCALITY', 'PIN_CODE', 'ZIP_CODE', 'UK_POSTCODE'},
            'location': {'LOCATION', 'ADDRESS', 'LOCALITY'},
            'locality': {'LOCALITY', 'ADDRESS'},
            'postcode': {'UK_POSTCODE', 'CANADA_POSTCODE', 'AUSTRALIA_POSTCODE', 'FRANCE_POSTCODE', 'NETHERLANDS_POSTCODE', 'JAPAN_POSTCODE', 'GERMANY_PLZ', 'BRAZIL_CEP'},
            'zip': {'ZIP_CODE'},
            'pin code': {'PIN_CODE'},
            'plz': {'GERMANY_PLZ'},
            'cep': {'BRAZIL_CEP'},
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
            'passport': {'PASSPORT', 'PASSPORT_US', 'PASSPORT_UK', 'PASSPORT_INDIA'},
            'driver': {'DRIVER_LICENSE', 'INDIA_DL'},
            'license': {'DRIVER_LICENSE', 'INDIA_DL'},
            'driving': {'DRIVER_LICENSE', 'INDIA_DL'},
            'nhs': {'UK_NHS'},
            'medicare': {'US_MEDICARE'},
            'medical': {'MEDICAL_ID', 'US_MEDICARE', 'UK_NHS'},
            'health': {'MEDICAL_ID', 'US_MEDICARE', 'UK_NHS'},
            'national insurance': {'UK_NIN'},
            'nin': {'UK_NIN'},
            'ip': {'IP_ADDRESS', 'IPV6_ADDRESS'},
            'ipv6': {'IPV6_ADDRESS'},
            'mac': {'MAC_ADDRESS'},
            'url': {'URL'},
            'website': {'URL'},
            'link': {'URL'},
            'network': {'IP_ADDRESS', 'IPV6_ADDRESS', 'MAC_ADDRESS', 'URL'},
            'vehicle': {'UK_VEHICLE_REG', 'INDIA_VEHICLE_REG'},
            'registration': {'UK_VEHICLE_REG', 'INDIA_VEHICLE_REG'},
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
            'date': {'DATE_TIME'},
            'dob': {'DATE_TIME'},
            'time': {'DATE_TIME'},
            'birthday': {'DATE_TIME'},
            'all': None,
            'everything': None,
        }
        
        wanted = set()
        include_all = False
        for kw, types in type_keywords.items():
            if kw in context_lower:
                if types is None:
                    include_all = True
                    break
                wanted.update(types)
        
        if not wanted and not include_all:
            include_all = True
        
        relevant_indices = []
        for idx_str, pii_type in items:
            if include_all or pii_type in wanted:
                relevant_indices.append(int(idx_str))
        
        return _json.dumps({
            'relevant_indices': relevant_indices,
            'summary': f'Filtered {len(relevant_indices)} relevant items from {len(items)} detected PIIs'
        })
    
    def _mock_pii_extraction(self, prompt: str) -> str:
        """Generate a realistic mock JSON response for PII extraction prompts."""
        import json as _json
        import re as _re
        
        # Extract the text between TEXT TO ANALYZE markers
        text_match = _re.search(r'TEXT TO ANALYZE:\s*"""([\s\S]*?)"""', prompt)
        source_text = text_match.group(1).strip() if text_match else ''
        
        # Extract context query
        ctx_match = _re.search(r"USER'S CONTEXT/QUERY:\s*\"\"\"([\s\S]*?)\"\"\"", prompt)
        context = ctx_match.group(1).strip() if ctx_match else ''
        context_lower = context.lower()
        
        relevant = []
        excluded = []
        
        # Extract names (simple heuristic for mock)
        names = _re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', source_text)
        # Extract phone numbers
        phones = _re.findall(r'[\+]?[\d][\d\s\-\(\)]{7,}[\d]', source_text)
        # Extract emails
        emails = _re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', source_text)
        # Extract account/bank numbers (8+ digit sequences)
        accounts = _re.findall(r'\b\d{8,}\b', source_text)
        # Extract PAN numbers
        pans = _re.findall(r'\b[A-Z]{5}\d{4}[A-Z]\b', source_text)
        # Extract Aadhaar
        aadhaars = _re.findall(r'\b\d{4}\s?\d{4}\s?\d{4}\b', source_text)
        
        want_name = any(w in context_lower for w in ['name', 'person', 'all', 'everything'])
        want_phone = any(w in context_lower for w in ['phone', 'mobile', 'contact', 'number', 'all', 'everything'])
        want_email = any(w in context_lower for w in ['email', 'mail', 'contact', 'all', 'everything'])
        want_account = any(w in context_lower for w in ['account', 'bank', 'financial', 'all', 'everything'])
        want_pan = any(w in context_lower for w in ['pan', 'tax', 'all', 'everything'])
        want_aadhaar = any(w in context_lower for w in ['aadhaar', 'aadhar', 'id', 'all', 'everything'])
        
        seen_names = set()
        for name in names:
            name = name.strip()
            if name in seen_names or len(name) < 4:
                continue
            seen_names.add(name)
            entry = {'value': name, 'type': 'PERSON_NAME', 'confidence': 0.95, 'reason': 'Person name found in text'}
            if want_name:
                relevant.append(entry)
            else:
                excluded.append({'value': name, 'type': 'PERSON_NAME', 'reason_excluded': 'Not requested in context'})
        
        for phone in phones:
            phone = phone.strip()
            entry = {'value': phone, 'type': 'PHONE', 'confidence': 0.9, 'reason': 'Phone number found in text'}
            if want_phone:
                relevant.append(entry)
            else:
                excluded.append({'value': phone, 'type': 'PHONE', 'reason_excluded': 'Not requested in context'})
        
        for email in emails:
            entry = {'value': email, 'type': 'EMAIL', 'confidence': 0.95, 'reason': 'Email address found in text'}
            if want_email:
                relevant.append(entry)
            else:
                excluded.append({'value': email, 'type': 'EMAIL', 'reason_excluded': 'Not requested in context'})
        
        for acc in accounts:
            entry = {'value': acc, 'type': 'ACCOUNT_ID', 'confidence': 0.85, 'reason': 'Account number found in text'}
            if want_account:
                relevant.append(entry)
            else:
                excluded.append({'value': acc, 'type': 'ACCOUNT_ID', 'reason_excluded': 'Not requested in context'})
        
        for pan in pans:
            entry = {'value': pan, 'type': 'INDIA_PAN', 'confidence': 0.95, 'reason': 'PAN number found in text'}
            if want_pan:
                relevant.append(entry)
            else:
                excluded.append({'value': pan, 'type': 'INDIA_PAN', 'reason_excluded': 'Not requested in context'})
        
        for aad in aadhaars:
            entry = {'value': aad, 'type': 'INDIA_AADHAAR', 'confidence': 0.9, 'reason': 'Aadhaar number found in text'}
            if want_aadhaar:
                relevant.append(entry)
            else:
                excluded.append({'value': aad, 'type': 'INDIA_AADHAAR', 'reason_excluded': 'Not requested in context'})
        
        result = {
            'relevant_pii': relevant,
            'excluded_pii': excluded,
            'summary': f'Extracted {len(relevant)} relevant PII items based on context: {context}'
        }
        
        return _json.dumps(result, indent=2)
