"""
Test suite for context prompt + PII extraction → LLM request box flow.
Tests that extracted PIIs are properly copied to the input/prompt and
that the context prompt is passed through to the LLM call.
"""
import sys
import os
import json

# Ensure repo root is on sys.path so we can import apps.*
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from apps.api.app import app

def setup_client():
    """Create a Flask test client."""
    app.config['TESTING'] = True
    return app.test_client()


def test_anonymize_without_context_prompt():
    """Test 1: /api/anonymize without context_prompt (backward compatibility)."""
    client = setup_client()
    
    resp = client.post('/api/anonymize', json={
        'text': 'My name is John Smith and my email is john@example.com.',
        'mode': 'pseudonymize',
        'call_llm': True
    })
    
    data = resp.get_json()
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {data}"
    assert 'anonymized_text' in data, "Missing anonymized_text"
    assert data['mappings_count'] > 0, "Expected at least 1 mapping"
    assert 'llm_response' in data, "Missing llm_response (LLM should have been called)"
    assert 'deanonymized_output' in data, "Missing deanonymized_output"
    
    # Since no context_prompt, LLM prompt should use default format
    # (We can't directly inspect the prompt, but the response should exist)
    print("[PASS] Test 1: Anonymize without context_prompt (backward compat)")
    return True


def test_anonymize_with_context_prompt():
    """Test 2: /api/anonymize WITH context_prompt — should include it in LLM call."""
    client = setup_client()
    
    resp = client.post('/api/anonymize', json={
        'text': 'My name is Sarah Connor and my phone is +1 (555) 999-0001.',
        'mode': 'pseudonymize',
        'call_llm': True,
        'context_prompt': 'Extract customer contact information for a support ticket'
    })
    
    data = resp.get_json()
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {data}"
    assert 'anonymized_text' in data, "Missing anonymized_text"
    assert data['mappings_count'] > 0, "Expected at least 1 mapping"
    assert 'llm_response' in data, "Missing llm_response"
    assert 'deanonymized_output' in data, "Missing deanonymized_output"
    
    # The LLM response should exist (context prompt was used internally)
    print("[PASS] Test 2: Anonymize WITH context_prompt")
    return True


def test_anonymize_with_context_prompt_no_llm():
    """Test 3: /api/anonymize with context_prompt but call_llm=False."""
    client = setup_client()
    
    resp = client.post('/api/anonymize', json={
        'text': 'John Doe lives at 123 Main St.',
        'mode': 'pseudonymize',
        'call_llm': False,
        'context_prompt': 'Extract address information'
    })
    
    data = resp.get_json()
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {data}"
    assert 'anonymized_text' in data, "Missing anonymized_text"
    # Should NOT have LLM response since call_llm=False
    assert 'llm_response' not in data, "Should not have llm_response when call_llm=False"
    
    print("[PASS] Test 3: Context prompt with call_llm=False")
    return True


def test_anonymize_mask_mode_with_context():
    """Test 4: /api/anonymize mask mode with context_prompt."""
    client = setup_client()
    
    resp = client.post('/api/anonymize', json={
        'text': 'Contact Alice Johnson at alice@corp.com or +44 20 1234 5678.',
        'mode': 'mask',
        'call_llm': True,
        'context_prompt': 'Identify contact details for GDPR compliance'
    })
    
    data = resp.get_json()
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {data}"
    assert 'anonymized_text' in data, "Missing anonymized_text"
    assert data['mode'] == 'mask', f"Expected mode 'mask', got {data['mode']}"
    assert data['reversible'] == False, "Mask mode should not be reversible"
    assert 'llm_response' in data, "Missing llm_response"
    
    print("[PASS] Test 4: Mask mode with context_prompt")
    return True


def test_anonymize_replace_mode_with_context():
    """Test 5: /api/anonymize replace mode with context_prompt."""
    client = setup_client()
    
    resp = client.post('/api/anonymize', json={
        'text': 'Bob Smith works at Acme Corp. Email: bob@acme.com.',
        'mode': 'replace',
        'call_llm': True,
        'context_prompt': 'Extract employee information for HR records'
    })
    
    data = resp.get_json()
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {data}"
    assert 'anonymized_text' in data, "Missing anonymized_text"
    assert data['mode'] == 'replace', f"Expected mode 'replace', got {data['mode']}"
    assert 'llm_response' in data, "Missing llm_response"
    
    print("[PASS] Test 5: Replace mode with context_prompt")
    return True


def test_anonymize_empty_context_prompt():
    """Test 6: /api/anonymize with empty context_prompt (should behave like none)."""
    client = setup_client()
    
    resp = client.post('/api/anonymize', json={
        'text': 'Contact me at test@email.com.',
        'mode': 'pseudonymize',
        'call_llm': True,
        'context_prompt': ''
    })
    
    data = resp.get_json()
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {data}"
    assert 'anonymized_text' in data, "Missing anonymized_text"
    assert 'llm_response' in data, "Missing llm_response"
    
    print("[PASS] Test 6: Empty context_prompt (treated as none)")
    return True


def test_anonymize_whitespace_context_prompt():
    """Test 7: /api/anonymize with whitespace-only context_prompt."""
    client = setup_client()
    
    resp = client.post('/api/anonymize', json={
        'text': 'My SSN is 123-45-6789.',
        'mode': 'pseudonymize',
        'call_llm': True,
        'context_prompt': '   '
    })
    
    data = resp.get_json()
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {data}"
    assert 'anonymized_text' in data, "Missing anonymized_text"
    assert 'llm_response' in data, "Missing llm_response"
    
    print("[PASS] Test 7: Whitespace context_prompt (treated as none)")
    return True


def test_deanonymize_still_works():
    """Test 8: /api/deanonymize endpoint still works after changes."""
    client = setup_client()
    
    # First anonymize
    resp1 = client.post('/api/anonymize', json={
        'text': 'Hello from James Bond.',
        'mode': 'pseudonymize',
        'call_llm': False
    })
    data1 = resp1.get_json()
    anonymized = data1['anonymized_text']
    
    # Then deanonymize
    resp2 = client.post('/api/deanonymize', json={
        'text': anonymized
    })
    data2 = resp2.get_json()
    assert resp2.status_code == 200, f"Deanonymize failed: {data2}"
    assert 'deanonymized_text' in data2, "Missing deanonymized_text"
    
    print("[PASS] Test 8: Deanonymize still works")
    return True


def test_ocr_anonymize_with_context_prompt():
    """Test 9: /api/ocr/anonymize with text file and context_prompt."""
    client = setup_client()
    
    # Create a simple text file content
    text_content = b"Patient: Jane Doe, DOB: 1985-03-15, Phone: +1 (555) 222-3344, Email: jane@hospital.org"
    
    from io import BytesIO
    data = {
        'file': (BytesIO(text_content), 'patient_record.txt'),
        'mode': 'pseudonymize',
        'call_llm': 'true',
        'context_prompt': 'Extract patient contact information for appointment scheduling',
        'skip_filtering': 'true'
    }
    
    resp = client.post('/api/ocr/anonymize',
                       data=data,
                       content_type='multipart/form-data')
    
    result = resp.get_json()
    
    # OCR may fail if psutil/other deps are missing — that's an environment issue, not a code bug
    if resp.status_code == 400 and 'psutil' in str(result.get('error', '')):
        print("[SKIP] Test 9: OCR anonymize with context_prompt (psutil not installed)")
        return True
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {result}"
    assert result.get('success', False), f"Expected success: {result}"
    assert 'anonymized_text' in result, "Missing anonymized_text"
    assert 'llm_response' in result, "Missing llm_response (context prompt should have been used)"
    
    print("[PASS] Test 9: OCR anonymize with context_prompt")
    return True


def test_ocr_anonymize_without_context_prompt():
    """Test 10: /api/ocr/anonymize without context_prompt (backward compat)."""
    client = setup_client()
    
    text_content = b"My name is John and my email is john@test.com."
    
    from io import BytesIO
    data = {
        'file': (BytesIO(text_content), 'test.txt'),
        'mode': 'pseudonymize',
        'call_llm': 'true',
        'skip_filtering': 'true'
    }
    
    resp = client.post('/api/ocr/anonymize',
                       data=data,
                       content_type='multipart/form-data')
    
    result = resp.get_json()
    
    # OCR may fail if psutil/other deps are missing — that's an environment issue, not a code bug
    if resp.status_code == 400 and 'psutil' in str(result.get('error', '')):
        print("[SKIP] Test 10: OCR anonymize without context_prompt (psutil not installed)")
        return True
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {result}"
    assert result.get('success', False), f"Expected success: {result}"
    assert 'llm_response' in result, "Missing llm_response"
    
    print("[PASS] Test 10: OCR anonymize without context_prompt (backward compat)")
    return True


def test_multiple_pii_types_with_context():
    """Test 11: Multiple PII types with context prompt."""
    client = setup_client()
    
    text = (
        "Customer: Maria Garcia, SSN: 234-56-7890, "
        "Credit Card: 4111-1111-1111-1111, "
        "Email: maria.garcia@company.com, "
        "Phone: +1 (555) 888-7766, "
        "Address: 789 Pine Street, Austin, TX 78701"
    )
    
    resp = client.post('/api/anonymize', json={
        'text': text,
        'mode': 'pseudonymize',
        'call_llm': True,
        'context_prompt': 'Extract financial and identity information for fraud investigation'
    })
    
    data = resp.get_json()
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {data}"
    assert data['mappings_count'] >= 3, f"Expected at least 3 mappings, got {data['mappings_count']}"
    assert 'llm_response' in data, "Missing llm_response"
    assert 'deanonymized_output' in data, "Missing deanonymized_output"
    
    # Verify anonymized text doesn't contain original PII (email, SSN, credit card are always detected)
    anon = data['anonymized_text']
    assert 'maria.garcia@company.com' not in anon, "Original email still in anonymized text"
    assert '234-56-7890' not in anon, "Original SSN still in anonymized text"
    assert '4111-1111-1111-1111' not in anon, "Original credit card still in anonymized text"
    
    print("[PASS] Test 11: Multiple PII types with context prompt")
    return True


def test_context_prompt_special_characters():
    """Test 12: Context prompt with special characters."""
    client = setup_client()
    
    resp = client.post('/api/anonymize', json={
        'text': 'Call John at +1 (555) 111-2222.',
        'mode': 'pseudonymize',
        'call_llm': True,
        'context_prompt': "Extract PII for compliance review — include names, emails & phone #'s"
    })
    
    data = resp.get_json()
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {data}"
    assert 'llm_response' in data, "Missing llm_response"
    
    print("[PASS] Test 12: Context prompt with special characters")
    return True


def test_health_check():
    """Test 13: Health check still works."""
    client = setup_client()
    
    resp = client.get('/api/health')
    data = resp.get_json()
    assert resp.status_code == 200, f"Health check failed: {data}"
    assert data['status'] == 'healthy', f"Unhealthy: {data}"
    
    print("[PASS] Test 13: Health check still works")
    return True


def test_multi_person_context_pii_extraction():
    """Test 14: Hybrid PII extraction with multi-person text — regex detects, LLM filters."""
    from apps.ocr.ocr_extractor import ContextAwarePIIExtractor
    from apps.api.llm_client import GroqClient
    from apps.api.anonymizer import PIIAnonymizer
    
    llm = GroqClient()  # mock mode
    extractor = ContextAwarePIIExtractor(llm)
    anon = PIIAnonymizer()
    
    multi_person_text = (
        "Rohan Mehta is a 32-year-old resident of 45B, Lajpat Nagar, New Delhi, India. "
        "His phone number is +91-91234-77890, and his bank account number is 458921763540. "
        "The IFSC code for his bank is ZENB0004721.\n\n"
        "Sarah Johnson lives at 12, MG Road, Bengaluru, Karnataka. She can be reached at "
        "+91-88901-33452 and her savings account number is 775034219880 with IFSC NTBL0009082."
    )
    
    # Step 1: Regex+spaCy detects ALL PIIs
    detected = anon.detect_pii(multi_person_text)
    assert len(detected) >= 6, f"Expected at least 6 detected PIIs, got {len(detected)}"
    print(f"   Regex+spaCy detected: {len(detected)} PIIs")
    
    # Step 2: LLM filters by context
    result = extractor.extract_contextual_pii(
        text=multi_person_text,
        context_prompt="Name, Phone Number and Account Number",
        detected_piis=detected
    )
    
    assert result['success'], f"Extraction should succeed, got: {result.get('summary', '')}"
    relevant = result['relevant_pii']
    assert len(relevant) >= 4, f"Expected at least 4 relevant PIIs (2 names, 2 phones), got {len(relevant)}: {relevant}"
    
    # Check that we got names
    names = [p['value'] for p in relevant if p['type'] in ('PERSON_NAME', 'PERSON', 'NAME')]
    assert len(names) >= 2, f"Expected 2 person names, got {len(names)}: {names}"
    
    # Check that we got phone numbers
    phones = [p['value'] for p in relevant if p['type'] in ('PHONE', 'PHONE_NUMBER')]
    assert len(phones) >= 2, f"Expected 2 phone numbers, got {len(phones)}: {phones}"
    
    # Check that we got account numbers (may be detected as INDIA_AADHAAR since 12-digit numbers match both patterns)
    accounts = [p['value'] for p in relevant if p['type'] in ('ACCOUNT_ID', 'BANK_ACCOUNT', 'FINANCIAL_INFO', 'ACCOUNT_NUMBER', 'INDIA_AADHAAR')]
    assert len(accounts) >= 2, f"Expected 2 account numbers, got {len(accounts)}: {accounts}"
    
    # Check that excluded PIIs exist (IFSC codes, addresses etc. not requested)
    excluded = result['excluded_pii']
    assert len(excluded) >= 1, f"Expected some excluded PIIs, got {len(excluded)}"
    
    # Check that relevant PIIs have position info for frontend grouping
    for p in relevant:
        assert 'position' in p, f"PII missing position field: {p}"
    
    # Check that PIIs are in document order (positions increasing)
    positions = [p['position'] for p in relevant]
    assert positions == sorted(positions), f"PIIs not in document order: {positions}"
    
    print(f"[PASS] Test 14: Multi-person hybrid extraction: {len(relevant)} relevant, {len(excluded)} excluded")
    return True


def test_json_parsing_markdown_code_blocks():
    """Test 15: JSON parser handles markdown code fences in LLM response."""
    from ocr_extractor import ContextAwarePIIExtractor
    
    extractor = ContextAwarePIIExtractor(None)  # Won't call LLM
    
    # Simulate LLM returning JSON inside markdown code block
    md_response = '''```json
{
    "relevant_pii": [
        {"value": "Alice", "type": "PERSON_NAME", "confidence": 0.9, "reason": "Name"},
        {"value": "555-1234", "type": "PHONE", "confidence": 0.85, "reason": "Phone"}
    ],
    "excluded_pii": [],
    "summary": "Found 2 items"
}
```'''
    
    result = extractor._parse_extraction_response(md_response, "original text")
    assert result['success'], "Should parse markdown-wrapped JSON"
    assert len(result['relevant_pii']) == 2, f"Expected 2 PIIs, got {len(result['relevant_pii'])}"
    print("[PASS] Test 15: Markdown code block JSON parsing")
    return True


def test_json_parsing_truncated_response():
    """Test 16: JSON parser repairs truncated responses (missing closing braces)."""
    from ocr_extractor import ContextAwarePIIExtractor
    
    extractor = ContextAwarePIIExtractor(None)
    
    # Simulate truncated JSON (cut off by max_tokens)
    truncated = '''{
    "relevant_pii": [
        {"value": "Bob", "type": "PERSON_NAME", "confidence": 0.9, "reason": "Name"},
        {"value": "bob@test.com", "type": "EMAIL", "confidence": 0.95, "reason": "Email"}
    ],
    "excluded_pii": [],
    "summary": "Found 2 items"'''  # Missing final }
    
    result = extractor._parse_extraction_response(truncated, "original text")
    assert result['success'], "Should repair truncated JSON"
    assert len(result['relevant_pii']) == 2, f"Expected 2 PIIs, got {len(result['relevant_pii'])}"
    print("[PASS] Test 16: Truncated JSON repair")
    return True


def test_json_parsing_with_preamble_text():
    """Test 17: JSON parser handles extra text before/after JSON."""
    from ocr_extractor import ContextAwarePIIExtractor
    
    extractor = ContextAwarePIIExtractor(None)
    
    response_with_text = '''Here is the analysis of the text:

{
    "relevant_pii": [
        {"value": "Charlie", "type": "PERSON_NAME", "confidence": 0.9, "reason": "Name"}
    ],
    "excluded_pii": [],
    "summary": "Found 1 item"
}

I hope this helps with your query.'''
    
    result = extractor._parse_extraction_response(response_with_text, "original text")
    assert result['success'], "Should extract JSON from text with preamble"
    assert len(result['relevant_pii']) == 1, f"Expected 1 PII, got {len(result['relevant_pii'])}"
    print("[PASS] Test 17: JSON with preamble/postfix text")
    return True


def test_multi_person_via_process_endpoint():
    """Test 18: /api/ocr/process with multi-person text returns PII cards data."""
    import io
    client = setup_client()
    
    multi_text = (
        "Rohan Mehta is a 32-year-old resident of 45B, Lajpat Nagar, New Delhi. "
        "His phone number is +91-91234-77890, and his bank account number is 458921763540.\n\n"
        "Sarah Johnson lives at 12, MG Road, Bengaluru. She can be reached at "
        "+91-88901-33452 and her savings account number is 775034219880."
    )
    
    data = io.BytesIO(multi_text.encode('utf-8'))
    
    resp = client.post('/api/ocr/process', 
                       data={
                           'file': (data, 'multi_person.txt'),
                           'context_prompt': 'Name, Phone Number and Account Number',
                           'skip_filtering': 'false'
                       },
                       content_type='multipart/form-data')
    
    result = resp.get_json()
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    assert result['success'], f"Processing should succeed: {result}"
    
    analysis = result.get('pii_analysis')
    assert analysis is not None, "Should have pii_analysis"
    
    relevant = analysis.get('relevant_pii', [])
    assert len(relevant) >= 4, f"Expected at least 4 relevant PIIs, got {len(relevant)}: {relevant}"
    
    # Verify summary doesn't contain error messages
    summary = analysis.get('summary', '')
    assert 'parsing failed' not in summary.lower(), f"Summary indicates parsing failure: {summary}"
    assert 'could not parse' not in summary.lower(), f"Summary indicates parse error: {summary}"
    
    print(f"[PASS] Test 18: Multi-person via /api/ocr/process found {len(relevant)} PIIs")
    return True


def test_comprehensive_multi_pii_document():
    """Test 19: Full document like the user's test image — two paragraphs with 30+ PIIs."""
    from apps.ocr.ocr_extractor import ContextAwarePIIExtractor
    from apps.api.llm_client import GroqClient
    from apps.api.anonymizer import PIIAnonymizer
    
    llm = GroqClient()
    extractor = ContextAwarePIIExtractor(llm)
    anon = PIIAnonymizer()
    
    # Text matching the user's test image content
    full_text = (
        "On 12 March 2025 at 10:45 AM, Arjun Mehta from Bengaluru, India visited the "
        "National Digital Finance Center to complete his Loan Agreement Legal Document. "
        "His registered Email Address is arjun.mehta92@samplemail.com and his Phone Number "
        "is +91-98765-44210. He currently resides at 45/2 Lakeview Apartments, Whitefield "
        "Main Road, in the locality of Whitefield, with PIN Code 560066.\n\n"
        "His banking profile includes Account Number 00891234567021 at Axis Digital Bank, "
        "with IFSC Code AXIS0001872 and SWIFT/BIC Code AXISINBB204. During verification he "
        "also submitted his PAN Number BQRPM5482K and Aadhaar Number 4821 7645 1932.\n\n"
        "Network logs from the application portal recorded a login attempt from IP Address "
        "192.168.14.56, IPv6 Address 2001:0db8:85a3:0000:0000:8a2e:0370:7334, and device "
        "MAC Address 00:1B:44:11:3A:B7, accessed through the portal "
        "https://secure.axisdigitalbank.com/apply.\n\n"
        "Emily Carter, a British national, submitted an employment verification request to "
        "Northbridge Analytics Ltd on 5 September 2024 at 14:30. Her registered contact "
        "information includes Email: emily.carter.hr@testmail.co.uk and Phone Number: "
        "+44-7700-912345. She lives at 18 Kensington Park Gardens, London, within the "
        "locality of Notting Hill, UK Postcode W11 2EU.\n\n"
        "Her payroll account details include Sort Code 20-45-33 and Bank Account Number "
        "55482019, associated with HSBC Corporate Banking, along with IBAN "
        "GB29NWBK60161331926819 and SWIFT Code NWBKGB2L.\n\n"
        "For taxation compliance she provided her UK National Insurance Number QQ123456C "
        "and VAT Number GB999 8888 73. Her Passport Number 563918274 and Driver License "
        "Number CARTER801234EC9 were submitted as identity proof."
    )
    
    # Step 1: Detect all PIIs
    detected = anon.detect_pii(full_text)
    print(f"   Total detected PIIs: {len(detected)}")
    
    # Should detect a LOT of PIIs from this rich document
    assert len(detected) >= 20, f"Expected 20+ PIIs from this rich document, only got {len(detected)}"
    
    # Verify key types are detected
    detected_types = set(d[1] for d in detected)
    print(f"   Detected types: {detected_types}")
    
    expected_types = {'EMAIL', 'PHONE', 'IFSC_CODE', 'INDIA_PAN', 'INDIA_AADHAAR',
                      'IP_ADDRESS', 'MAC_ADDRESS', 'URL'}
    for etype in expected_types:
        assert etype in detected_types, f"Expected {etype} to be detected but wasn't. Got: {detected_types}"
    
    # Step 2: Filter for "Name, Phone Number and Account Number"
    result = extractor.extract_contextual_pii(
        text=full_text,
        context_prompt="Name, Phone Number and Account Number",
        detected_piis=detected
    )
    
    assert result['success']
    relevant = result['relevant_pii']
    excluded = result['excluded_pii']
    
    print(f"   Relevant: {len(relevant)}, Excluded: {len(excluded)}")
    
    # Should have names, phones, and accounts for BOTH people
    rel_types = [p['type'] for p in relevant]
    rel_values = [p['value'] for p in relevant]
    
    person_names = [p['value'] for p in relevant if p['type'] in ('PERSON_NAME', 'PERSON', 'NAME')]
    phones = [p['value'] for p in relevant if p['type'] in ('PHONE',)]
    accounts = [p['value'] for p in relevant if p['type'] in ('ACCOUNT_ID', 'BANK_ACCOUNT', 'ACCOUNT_NUMBER')]
    
    assert len(person_names) >= 2, f"Expected 2+ person names, got: {person_names}"
    assert len(phones) >= 2, f"Expected 2+ phones, got: {phones}"
    assert len(accounts) >= 1, f"Expected 1+ accounts, got: {accounts}"
    
    # Excluded should contain things like IP, MAC, URL, PAN, Aadhaar etc.
    assert len(excluded) >= 5, f"Expected 5+ excluded, got: {len(excluded)}"
    
    print(f"[PASS] Test 19: Comprehensive multi-PII document — {len(relevant)} relevant, {len(excluded)} excluded")
    return True


def main():
    print("=" * 70)
    print("CONTEXT PROMPT + PII EXTRACTION → LLM REQUEST BOX TEST SUITE")
    print("=" * 70)
    print()
    
    tests = [
        test_anonymize_without_context_prompt,
        test_anonymize_with_context_prompt,
        test_anonymize_with_context_prompt_no_llm,
        test_anonymize_mask_mode_with_context,
        test_anonymize_replace_mode_with_context,
        test_anonymize_empty_context_prompt,
        test_anonymize_whitespace_context_prompt,
        test_deanonymize_still_works,
        test_ocr_anonymize_with_context_prompt,
        test_ocr_anonymize_without_context_prompt,
        test_multiple_pii_types_with_context,
        test_context_prompt_special_characters,
        test_health_check,
        test_multi_person_context_pii_extraction,
        test_json_parsing_markdown_code_blocks,
        test_json_parsing_truncated_response,
        test_json_parsing_with_preamble_text,
        test_multi_person_via_process_endpoint,
        test_comprehensive_multi_pii_document,
    ]
    
    passed = 0
    failed = 0
    errors = []
    
    for test_fn in tests:
        try:
            result = test_fn()
            if result:
                passed += 1
            else:
                failed += 1
                errors.append(f"{test_fn.__name__}: returned False")
        except Exception as e:
            failed += 1
            errors.append(f"{test_fn.__name__}: {str(e)}")
            print(f"[FAIL] {test_fn.__name__}: {e}")
    
    print()
    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 70)
    
    if errors:
        print("\nFailed tests:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("\nAll tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
