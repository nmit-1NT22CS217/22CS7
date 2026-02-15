#!/usr/bin/env python3
"""
Test to demonstrate reversibility behavior of different anonymization modes.
"""

from anonymizer import PIIAnonymizer

def test_reversibility():
    """Test which modes are reversible and which are not."""
    
    anonymizer = PIIAnonymizer()
    
    text = "Hello, I'm Priya Mehta. Call me at +1 (555) 123-4567."
    
    print("="*70)
    print("ORIGINAL TEXT:")
    print("="*70)
    print(text)
    print()
    
    # Test 1: Pseudonymize (REVERSIBLE)
    print("="*70)
    print("1. PSEUDONYMIZE MODE (REVERSIBLE)")
    print("="*70)
    pseudo_text, pseudo_mappings = anonymizer.pseudonymize(text)
    print(f"Anonymized: {pseudo_text}")
    print(f"Mappings: {pseudo_mappings}")
    print(f"Reversible: {len(pseudo_mappings) > 0}")
    
    if pseudo_mappings:
        deanonymized = anonymizer.deanonymize(pseudo_text, pseudo_mappings)
        print(f"Deanonymized: {deanonymized}")
        print(f"✅ Successfully restored: {deanonymized == text}")
    print()
    
    # Test 2: Mask (IRREVERSIBLE)
    print("="*70)
    print("2. MASK MODE (IRREVERSIBLE - DISPLAY ONLY)")
    print("="*70)
    masked_text, masked_mappings = anonymizer.mask(text)
    print(f"Masked: {masked_text}")
    print(f"Mappings: {masked_mappings}")
    print(f"Reversible: {len(masked_mappings) > 0}")
    print("❌ This mode is for display only - cannot be reversed")
    print()
    
    # Test 3: Replace (IRREVERSIBLE)
    print("="*70)
    print("3. REPLACE MODE (IRREVERSIBLE - DISPLAY ONLY)")
    print("="*70)
    replaced_text, replaced_mappings = anonymizer.replace(text)
    print(f"Replaced: {replaced_text}")
    print(f"Mappings: {replaced_mappings}")
    print(f"Reversible: {len(replaced_mappings) > 0}")
    print("❌ This mode is for display only - cannot be reversed")
    print()
    
    print("="*70)
    print("SUMMARY:")
    print("="*70)
    print("✅ Pseudonymize: REVERSIBLE - stores mappings for deanonymization")
    print("❌ Mask: IRREVERSIBLE - partial masking for display purposes")
    print("❌ Replace: IRREVERSIBLE - human-friendly labels for display")
    print()
    print("Industry Standard: Only pseudonymization is meant to be reversible.")
    print("Masking and replacement are one-way transformations for privacy.")

if __name__ == "__main__":
    test_reversibility()
