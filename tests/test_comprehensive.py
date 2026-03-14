"""
Comprehensive Test Suite for PII Anonymizer
Tests all entity types, edge cases, and potential false positives
"""

import sys
import os

# Ensure repo root is on sys.path so we can import apps.*
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from apps.api.anonymizer import PIIAnonymizer

def run_test(name, text, expected_types, unexpected_values=None):
    """Run a single test case and return results"""
    a = PIIAnonymizer()
    result = a.pseudonymize(text)
    detected = result[1]
    
    # Check expected types
    passed = True
    issues = []
    
    for exp_type in expected_types:
        found = any(exp_type in k for k in detected.keys())
        if not found:
            passed = False
            issues.append(f"Missing: {exp_type}")
    
    # Check for false positives
    if unexpected_values:
        for uv in unexpected_values:
            if uv in str(detected.values()):
                passed = False
                issues.append(f"False positive: {uv}")
    
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}")
    if not passed:
        print(f"       Issues: {issues}")
        print(f"       Detected: {detected}")
    return passed


def main():
    print("=" * 70)
    print("COMPREHENSIVE PII ANONYMIZER TEST SUITE")
    print("=" * 70)
    print()
    
    results = []
    
    # ==================== CATEGORY 1: BASIC PII ====================
    print("--- CATEGORY 1: BASIC PII TYPES ---")
    
    # 1.1 Email
    results.append(run_test(
        "1.1 Email - Standard format",
        "Contact: john.smith@example.com",
        ["email"]
    ))
    
    results.append(run_test(
        "1.2 Email - Complex domain",
        "Email: user.name+tag@subdomain.domain.co.uk",
        ["email"]
    ))
    
    # 1.3 Phone Numbers
    results.append(run_test(
        "1.3 Phone - US format with parentheses",
        "Phone: (555) 123-4567",
        ["mobNo"]
    ))
    
    results.append(run_test(
        "1.4 Phone - US format with country code",
        "Phone: +1 (555) 123-4567",
        ["mobNo"]
    ))
    
    results.append(run_test(
        "1.5 Phone - US format with dashes",
        "Phone: 555-123-4567",
        ["mobNo"]
    ))
    
    # 1.6 Names
    results.append(run_test(
        "1.6 Name - Simple two-word",
        "Name: John Smith",
        ["name"]
    ))
    
    results.append(run_test(
        "1.7 Name - With title",
        "Dr. Robert Johnson attended the meeting",
        ["name"]
    ))
    
    # ==================== CATEGORY 2: US-SPECIFIC ====================
    print()
    print("--- CATEGORY 2: US-SPECIFIC PII ---")
    
    results.append(run_test(
        "2.1 SSN - Standard format",
        "SSN: 123-45-6789",
        ["ssn"]
    ))
    
    results.append(run_test(
        "2.2 SSN - No dashes",
        "SSN: 123456789",
        ["ssn"]
    ))
    
    results.append(run_test(
        "2.3 ZIP Code - 5 digits",
        "ZIP: 90210",
        ["zipcode"]
    ))
    
    results.append(run_test(
        "2.4 ZIP Code - ZIP+4",
        "ZIP: 90210-1234",
        ["zipcode"]
    ))
    
    results.append(run_test(
        "2.5 Credit Card - Visa",
        "Card: 4111-1111-1111-1111",
        ["credit_card"]
    ))
    
    results.append(run_test(
        "2.6 Credit Card - Mastercard",
        "Card: 5500-0000-0000-0004",
        ["credit_card"]
    ))
    
    results.append(run_test(
        "2.7 Credit Card - Amex",
        "Card: 3782-822463-10005",
        ["credit_card"]
    ))
    
    # ==================== CATEGORY 3: UK-SPECIFIC ====================
    print()
    print("--- CATEGORY 3: UK-SPECIFIC PII ---")
    
    results.append(run_test(
        "3.1 UK NIN - Standard",
        "NIN: AB123456C",
        ["uk_nin"]
    ))
    
    results.append(run_test(
        "3.2 UK NIN - With spaces",
        "NIN: AB 12 34 56 C",
        ["uk_nin"]
    ))
    
    results.append(run_test(
        "3.3 UK Postcode - London",
        "Postcode: SW1A 1AA",
        ["uk_postcode"]
    ))
    
    results.append(run_test(
        "3.4 UK Postcode - Manchester",
        "Postcode: M1 1AE",
        ["uk_postcode"]
    ))
    
    results.append(run_test(
        "3.5 UK NHS Number",
        "NHS Number: 943 476 5919",
        ["uk_nhs"]
    ))
    
    results.append(run_test(
        "3.6 UK VAT Number",
        "VAT: GB123456789",
        ["uk_vat"]
    ))
    
    results.append(run_test(
        "3.7 UK Phone",
        "Phone: +44 20 7946 0958",
        ["mobNo"]
    ))
    
    # ==================== CATEGORY 4: INDIA-SPECIFIC ====================
    print()
    print("--- CATEGORY 4: INDIA-SPECIFIC PII ---")
    
    results.append(run_test(
        "4.1 India PAN",
        "PAN: ABCPK1234D",
        ["india_pan"]
    ))
    
    results.append(run_test(
        "4.2 India Aadhaar",
        "Aadhaar: 2345 6789 0123",
        ["india_aadhaar"]
    ))
    
    results.append(run_test(
        "4.3 India IFSC",
        "IFSC: HDFC0001234",
        ["ifsc_code"]
    ))
    
    results.append(run_test(
        "4.4 India PIN Code",
        "PIN Code: 400001",
        ["pincode"]
    ))
    
    results.append(run_test(
        "4.5 India Vehicle Registration",
        "Vehicle: MH01AB1234",
        ["india_vehicle"]
    ))
    
    results.append(run_test(
        "4.6 India Phone",
        "Phone: +91-98765-43210",
        ["mobNo"]
    ))
    
    results.append(run_test(
        "4.7 India Bank Account",
        "Bank Account No: 12345678901234",
        ["bank_account"]
    ))
    
    # ==================== CATEGORY 5: CANADA-SPECIFIC ====================
    print()
    print("--- CATEGORY 5: CANADA-SPECIFIC PII ---")
    
    results.append(run_test(
        "5.1 Canada SIN - With dashes",
        "SIN: 046-454-286",
        ["canada_sin"]
    ))
    
    results.append(run_test(
        "5.2 Canada Postal Code",
        "Postal Code: K1A 0B1",
        ["canada_postcode"]
    ))
    
    results.append(run_test(
        "5.3 Canada Phone",
        "Phone: +1-416-555-1234",
        ["mobNo"]
    ))
    
    # ==================== CATEGORY 6: AUSTRALIA-SPECIFIC ====================
    print()
    print("--- CATEGORY 6: AUSTRALIA-SPECIFIC PII ---")
    
    results.append(run_test(
        "6.1 Australia TFN",
        "TFN: 123 456 782",
        ["australia_tfn"]
    ))
    
    results.append(run_test(
        "6.2 Australia ABN",
        "ABN: 51 824 753 556",
        ["australia_abn"]
    ))
    
    results.append(run_test(
        "6.3 Australia Postcode",
        "Postcode: 2000",
        ["australia_postcode"]
    ))
    
    results.append(run_test(
        "6.4 Australia Phone",
        "Phone: +61 2 1234 5678",
        ["mobNo"]
    ))
    
    # ==================== CATEGORY 7: GERMANY-SPECIFIC ====================
    print()
    print("--- CATEGORY 7: GERMANY-SPECIFIC PII ---")
    
    results.append(run_test(
        "7.1 Germany Steuer-ID",
        "Steuer-ID: 12 345 678 903",
        ["germany_steuerid"]
    ))
    
    results.append(run_test(
        "7.2 Germany PLZ",
        "PLZ: 80331",
        ["zipcode"]
    ))
    
    results.append(run_test(
        "7.3 Germany Phone",
        "Phone: +49 89 12345678",
        ["mobNo"]
    ))
    
    # ==================== CATEGORY 8: OTHER COUNTRIES ====================
    print()
    print("--- CATEGORY 8: OTHER COUNTRIES ---")
    
    results.append(run_test(
        "8.1 France Phone",
        "Phone: +33 1 23 45 67 89",
        ["mobNo"]
    ))
    
    results.append(run_test(
        "8.2 Japan Phone",
        "Phone: +81 3 1234 5678",
        ["mobNo"]
    ))
    
    results.append(run_test(
        "8.3 China Phone",
        "Phone: +86 10 1234 5678",
        ["mobNo"]
    ))
    
    # ==================== CATEGORY 9: INTERNATIONAL BANKING ====================
    print()
    print("--- CATEGORY 9: INTERNATIONAL BANKING ---")
    
    results.append(run_test(
        "9.1 IBAN - Germany",
        "IBAN: DE89370400440532013000",
        ["iban"]
    ))
    
    results.append(run_test(
        "9.2 IBAN - UK",
        "IBAN: GB82WEST12345698765432",
        ["iban"]
    ))
    
    results.append(run_test(
        "9.3 SWIFT/BIC Code",
        "SWIFT/BIC: DEUTDEFF",
        ["swift_bic"]
    ))
    
    results.append(run_test(
        "9.4 EU VAT - Germany",
        "EU VAT: DE123456789",
        ["eu_vat"]
    ))
    
    results.append(run_test(
        "9.5 EU VAT - Netherlands",
        "VAT: NL123456789B01",
        ["eu_vat"]
    ))
    
    # ==================== CATEGORY 10: NETWORK/TECHNICAL ====================
    print()
    print("--- CATEGORY 10: NETWORK/TECHNICAL ---")
    
    results.append(run_test(
        "10.1 IPv4 Address",
        "IP: 192.168.1.100",
        ["ip_address"]
    ))
    
    results.append(run_test(
        "10.2 MAC Address",
        "MAC: AA:BB:CC:DD:EE:FF",
        ["mac_address"]
    ))
    
    results.append(run_test(
        "10.3 URL",
        "URL: https://example.com/page?id=123",
        ["url"]
    ))
    
    # ==================== CATEGORY 11: FORM FIELDS & IDS ====================
    print()
    print("--- CATEGORY 11: FORM FIELDS & IDS ---")
    
    results.append(run_test(
        "11.1 Employee ID with hyphen",
        "Employee ID: EMP-12345",
        ["employee_id"]
    ))
    
    results.append(run_test(
        "11.2 Application Number",
        "Application Number: APP-98765",
        ["application_number"]
    ))
    
    results.append(run_test(
        "11.3 Account Number",
        "Account Number: 123456789012",
        ["account"]
    ))
    
    # ==================== CATEGORY 12: FALSE POSITIVE PREVENTION ====================
    print()
    print("--- CATEGORY 12: FALSE POSITIVE PREVENTION ---")
    
    results.append(run_test(
        "12.1 Department should NOT be EU VAT",
        "Department: Engineering",
        [],
        unexpected_values=["Department", "Engineering"]
    ))
    
    results.append(run_test(
        "12.2 Section headers should NOT be detected",
        "--- USA ---\n--- UK ---\n--- NETWORK ---",
        [],
        unexpected_values=["USA", "UK", "NETWORK"]
    ))
    
    results.append(run_test(
        "12.3 Form labels should NOT be names",
        "SSN: 123-45-6789\nPhone Number: +1-555-123-4567",
        ["ssn", "mobNo"],
        unexpected_values=["SSN", "Phone Number"]
    ))
    
    # Test 12.4 - Check that EMP-12345 is captured fully, not split
    a_test = PIIAnonymizer()
    test_result = a_test.pseudonymize("Employee ID: EMP-12345")
    # Check that employee_id value is the full ID, not just part
    emp_values = [v for k, v in test_result[1].items() if 'employee_id' in k]
    test_12_4_pass = len(emp_values) == 1 and emp_values[0] == 'EMP-12345'
    # Also check no standalone zipcode detected
    zip_detected = any('zipcode' in k for k in test_result[1].keys())
    test_12_4_pass = test_12_4_pass and not zip_detected
    print(f"[{'PASS' if test_12_4_pass else 'FAIL'}] 12.4 Employee ID should NOT split into ZIP")
    if not test_12_4_pass:
        print(f"       Detected: {test_result[1]}")
    results.append(test_12_4_pass)
    
    # ==================== CATEGORY 13: REVERSIBILITY ====================
    print()
    print("--- CATEGORY 13: REVERSIBILITY ---")
    
    a = PIIAnonymizer()
    original = "Contact John Doe at john@email.com or +1-555-123-4567. SSN: 123-45-6789"
    pseudo, mapping = a.pseudonymize(original)
    reversed_text = a.deanonymize(pseudo, mapping)
    rev_pass = original == reversed_text
    print(f"[{'PASS' if rev_pass else 'FAIL'}] 13.1 Full reversibility test")
    if not rev_pass:
        print(f"       Original:  {original}")
        print(f"       Reversed:  {reversed_text}")
    results.append(rev_pass)
    
    # ==================== CATEGORY 14: EDGE CASES ====================
    print()
    print("--- CATEGORY 14: EDGE CASES ---")
    
    results.append(run_test(
        "14.1 Empty string",
        "",
        []
    ))
    
    results.append(run_test(
        "14.2 No PII content",
        "This is a simple sentence with no personal data.",
        []
    ))
    
    results.append(run_test(
        "14.3 Multiple same-type entities",
        "Email1: a@b.com, Email2: c@d.com, Email3: e@f.com",
        ["email"]
    ))
    
    results.append(run_test(
        "14.4 Mixed international PII",
        "UK NIN: AB123456C, India PAN: ABCPK1234D, Canada SIN: 046-454-286",
        ["uk_nin", "india_pan", "canada_sin"]
    ))
    
    # ==================== SUMMARY ====================
    print()
    print("=" * 70)
    total = len(results)
    passed = sum(results)
    failed = total - passed
    print(f"SUMMARY: {passed}/{total} tests passed, {failed} failed")
    print("=" * 70)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
