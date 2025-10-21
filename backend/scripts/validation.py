"""
validate.py
------------
Validation and consistency checks for anonymization → LLM → denormalization pipeline.

Responsibilities:
  ✅ Verify anonymized text contains no unmasked PII.
  ✅ Verify denormalized text contains no pseudonyms.
  ✅ Validate pseudomap integrity (no duplicate or missing entries).
  ✅ Generate validation report for auditing.

This ensures that:
  - Anonymization truly protected sensitive data before LLM exposure.
  - Denormalization correctly restored data using authorized mapping.
"""

from __future__ import annotations
import os
import sys
from typing import Dict, List, Any

# --- Permanent import fix ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.utils import get_logger, write_json_file, ensure_dir
from scripts.detect_pii import detect_pii_in_text
from scripts.denormalize import find_remaining_pseudonyms
from scripts.pseudomap import load_map

logger = get_logger("validate")


# -----------------------------------------------------------------------------
# 1️⃣ Validate Anonymized Text (PII Check)
# -----------------------------------------------------------------------------
def validate_anonymized_text(text: str) -> Dict[str, Any]:
    """
    Re-run PII detector to confirm anonymization removed all PII.
    """
    detections = detect_pii_in_text(text)
    passed = len(detections) == 0

    return {
        "passed": passed,
        "pii_detected": len(detections),
        "detections": detections,
        "message": "No PII detected ✅" if passed else f"{len(detections)} PII instances still present ❌"
    }


# -----------------------------------------------------------------------------
# 2️⃣ Validate Denormalized Text (Residual Pseudonym Check)
# -----------------------------------------------------------------------------
def validate_denormalized_text(text: str, mapping: Dict[str, str]) -> Dict[str, Any]:
    """
    Check that no pseudonyms remain in the denormalized text.
    """
    remaining = find_remaining_pseudonyms(text, mapping)
    passed = len(remaining) == 0

    return {
        "passed": passed,
        "remaining_pseudos": remaining,
        "message": "No pseudonyms remaining ✅" if passed else f"Residual pseudonyms found: {list(remaining.keys())}"
    }


# -----------------------------------------------------------------------------
# 3️⃣ Validate Pseudomap Integrity
# -----------------------------------------------------------------------------
def validate_pseudomap(mapping: Dict[str, str]) -> Dict[str, Any]:
    """
    Ensure pseudomap is consistent (unique values, no nulls).
    """
    invalid_entries = [k for k, v in mapping.items() if not k or not v]
    duplicate_values = {v for v in mapping.values() if list(mapping.values()).count(v) > 1}
    passed = not invalid_entries and not duplicate_values

    return {
        "passed": passed,
        "invalid_entries": invalid_entries,
        "duplicate_pseudonyms": list(duplicate_values),
        "message": "Mapping integrity OK ✅" if passed else "Mapping contains invalid or duplicate entries ❌"
    }


# -----------------------------------------------------------------------------
# 4️⃣ Unified Validation Entry Point
# -----------------------------------------------------------------------------
def run_validation(
    run_id: str,
    anonymized_text: str,
    denormalized_text: str
) -> Dict[str, Any]:
    """
    Run all validation checks and persist a structured report.

    Args:
        run_id: unique identifier of the processing session
        anonymized_text: text sent to the LLM
        denormalized_text: text restored from LLM output

    Returns:
        A dict containing full validation summary
    """
    mapping = load_map(run_id)

    results = {
        "run_id": run_id,
        "anonymized_validation": validate_anonymized_text(anonymized_text),
        "denormalized_validation": validate_denormalized_text(denormalized_text, mapping),
        "pseudomap_validation": validate_pseudomap(mapping),
    }

    # Overall pass/fail summary
    all_passed = all([
        results["anonymized_validation"]["passed"],
        results["denormalized_validation"]["passed"],
        results["pseudomap_validation"]["passed"]
    ])
    results["overall_status"] = "PASS ✅" if all_passed else "FAIL ❌"

    # Save validation report
    output_dir = os.path.join(os.path.dirname(__file__), "..", "outputs", run_id)
    ensure_dir(output_dir)
    report_path = os.path.join(output_dir, "validation_report.json")
    write_json_file(results, report_path)

    logger.info(f"🧾 Validation report saved at: {report_path}")
    return results


# -----------------------------------------------------------------------------
# 5️⃣ Self-Test
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    from scripts.pseudomap import create_map_for_detections, save_map, generate_run_id
    from scripts.anonymize import anonymize_text

    logger.info("Running validate.py self-test...")

    # --- Create a test sample ---
    text = "Contact alice@example.com or call +1-555-111-2222 for details."
    detections = [
        {"type": "EMAIL", "value": "alice@example.com", "start": 8, "end": 27},
        {"type": "PHONE", "value": "+1-555-111-2222", "start": 37, "end": 52},
    ]

    # --- Anonymize (simulate sending to LLM) ---
    run_id = generate_run_id()
    mapping = create_map_for_detections(detections)
    save_map(run_id, mapping)
    anonymized = anonymize_text(text, detections, policy="pseudonymize")

    # --- Simulate LLM output (same pseudonyms, reversed order) ---
    pseudo_values = list(mapping.values())
    simulated_llm_output = f"{pseudo_values[1]} and {pseudo_values[0]} are both valid contacts."

    # --- Denormalize ---
    from scripts.denormalize import denormalize_by_run_id
    denormalized = denormalize_by_run_id(simulated_llm_output, run_id, backup_originals=False)

    # --- Run validations ---
    results = run_validation(run_id, anonymized, denormalized)
    print("\n=== VALIDATION REPORT ===")
    import json
    print(json.dumps(results, indent=2, ensure_ascii=False))

    logger.info("validate.py self-test complete ✅")
