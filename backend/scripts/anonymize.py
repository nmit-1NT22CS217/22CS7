"""
anonymize.py
------------
PII anonymization utilities.

Responsibilities:
  - Support multiple anonymization policies:
      * mask         => replace characters with mask char (preserve last N)
      * replace      => replace with descriptive placeholder like "<EMAIL>"
      * pseudonymize => deterministic pseudonym (reversible using mapping)
  - Deterministic pseudonym generation (SHA-256 + salt)
  - Safe substring replacement (process detections in reverse order)
  - Batch anonymization helper
  - Self-test when run as main

Notes:
  - This module intentionally does not persist mappings; mapping creation/persistence
    is handled by `pseudomap.py` (so that mapping storage strategy remains modular).
  - Use `pseudonymize_value` with same salt across a run to ensure deterministic outputs.
"""

from __future__ import annotations
import os
import sys
# permanent import path fix so scripts.* imports always work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import re
import hashlib
from typing import List, Dict, Any, Optional
from scripts.utils import get_logger, sanitize_for_log, ensure_dir, write_text_file, write_json_file

logger = get_logger("anonymize")

# ----------------------------
# Default config (can be overridden by .env or callers)
# ----------------------------
DEFAULT_MASK_CHAR = os.getenv("DEFAULT_MASK_CHAR", "*")
DEFAULT_PRESERVE_LAST_N = int(os.getenv("DEFAULT_PRESERVE_LAST_N", "4"))
DEFAULT_PSEUDO_SALT = os.getenv("PSEUDO_SALT", "project_default_salt")


# ----------------------------
# 1) Low-level helpers
# ----------------------------
def mask_value(value: str, mask_char: Optional[str] = None, preserve_last_n: Optional[int] = None) -> str:
    """
    Mask a detected PII value.

    - If value contains '@' (email), mask entire value length.
    - Otherwise mask all but last `preserve_last_n` characters.
    """
    mask_char = mask_char or DEFAULT_MASK_CHAR
    preserve_n = preserve_last_n if preserve_last_n is not None else DEFAULT_PRESERVE_LAST_N

    try:
        if "@" in value:
            return mask_char * len(value)
        if len(value) <= preserve_n:
            return mask_char * len(value)
        return mask_char * (len(value) - preserve_n) + value[-preserve_n:]
    except Exception as e:
        logger.warning(f"mask_value error for {sanitize_for_log(value, 60)}: {e}")
        return mask_char * max(1, len(value))


def replace_value(label: str) -> str:
    """
    Replace detected PII with a descriptive placeholder.
    Example: label='EMAIL' -> '<EMAIL>'
    """
    return f"<{label}>"


def pseudonymize_value(value: str, salt: Optional[str] = None, prefix: str = "PSEUDO") -> str:
    """
    Deterministic pseudonym using SHA-256 of (value + salt).
    Returns e.g. PSEUDO_ab12cd34ef
    """
    salt = salt or DEFAULT_PSEUDO_SALT
    token = hashlib.sha256((value + salt).encode("utf-8", errors="ignore")).hexdigest()
    # short deterministic token (first 12 chars)
    return f"{prefix}_{token[:12]}"


# ----------------------------
# 2) Core anonymization function
# ----------------------------
def anonymize_text(
    text: str,
    detections: List[Dict[str, Any]],
    policy: str = "mask",
    mask_char: Optional[str] = None,
    preserve_last_n: Optional[int] = None,
    pseudo_salt: Optional[str] = None,
) -> str:
    """
    Apply anonymization to input text according to chosen policy.

    Args:
      text: original input text
      detections: list of detection dicts with keys 'start','end','value','type'
      policy: one of 'mask', 'replace', 'pseudonymize'
      mask_char, preserve_last_n: policy-specific parameters
      pseudo_salt: optional salt for deterministic pseudonymization

    Returns:
      anonymized text (string)
    """
    if not detections:
        return text

    policy = (policy or "mask").lower()
    logger.info(f"Applying anonymization policy='{policy}' ({len(detections)} items)")

    # Work on a mutable copy
    new_text = text

    # Sort detections descending by start index so replacements won't shift later spans
    sorted_detections = sorted(detections, key=lambda d: d.get("start", 0), reverse=True)

    for d in sorted_detections:
        try:
            start = int(d.get("start", 0))
            end = int(d.get("end", 0))
            value = d.get("value", "")
            pii_type = d.get("type", "PII")

            if start < 0 or end > len(new_text) or start >= end:
                # Fallback: try to locate the first occurrence of value near start
                idx = new_text.find(value)
                if idx != -1:
                    start, end = idx, idx + len(value)
                else:
                    logger.debug(f"Skipping invalid span for detection {d}")
                    continue

            if policy == "mask":
                replacement = mask_value(value, mask_char=mask_char, preserve_last_n=preserve_last_n)
            elif policy == "replace":
                replacement = replace_value(pii_type)
            elif policy == "pseudonymize":
                replacement = pseudonymize_value(value, salt=pseudo_salt)
            else:
                raise ValueError(f"Unknown anonymization policy: {policy}")

            # Do the substitution on the current string
            new_text = new_text[:start] + replacement + new_text[end:]
        except Exception as e:
            logger.warning(f"Failed to anonymize detection {d}: {e}")

    return new_text


# ----------------------------
# 3) Batch anonymization (file-based)
# ----------------------------
def anonymize_batch(
    texts_with_detections: Dict[str, List[Dict[str, Any]]],
    output_dir: Optional[str] = None,
    policy: str = "mask",
    pseudo_salt: Optional[str] = None
) -> Dict[str, str]:
    """
    Anonymize multiple named text entries (e.g., multiple files).
    Args:
      texts_with_detections: mapping name -> detections list
      output_dir: directory to write anonymized files (if provided)
      policy: policy to apply (same for all entries)
      pseudo_salt: salt used for pseudonymization
    Returns:
      mapping name -> anonymized_text
    """
    results: Dict[str, str] = {}
    output_dir = output_dir or os.getenv("OUTPUT_DIR", os.path.join(os.path.dirname(__file__), "..", "outputs"))

    for name, detections in texts_with_detections.items():
        try:
            # Try to read source text if available under UPLOAD_DIR or fallback to empty
            src_path = os.path.join(os.getenv("UPLOAD_DIR", os.path.join(os.path.dirname(__file__), "..", "uploads")), name)
            text = ""
            if os.path.exists(src_path):
                with open(src_path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            anonymized = anonymize_text(text, detections, policy=policy, pseudo_salt=pseudo_salt)
            results[name] = anonymized

            if output_dir:
                ensure_dir(output_dir)
                out_path = os.path.join(output_dir, f"{name}.anonymized.txt")
                write_text_file(out_path, anonymized)
                # optional: write report of detections
                report_path = os.path.join(output_dir, f"{name}.report.json")
                write_json_file({"detections": detections, "policy": policy}, report_path)
                logger.info(f"Wrote anonymized file & report for {name} -> {out_path}, {report_path}")

        except Exception as e:
            logger.error(f"anonymize_batch error for {name}: {e}")

    return results


# ----------------------------
# 4) Small convenience: create mapping from detections (value -> pseudo)
# ----------------------------
def create_pseudomap_from_detections(detections: List[Dict[str, Any]], salt: Optional[str] = None) -> Dict[str, str]:
    """
    Create a deterministic mapping: original_value -> pseudonym
    Useful for saving mapping.json before sending to LLM.
    """
    mapping: Dict[str, str] = {}
    salt = salt or DEFAULT_PSEUDO_SALT
    for d in detections:
        val = d.get("value")
        if val is None:
            continue
        if val in mapping:
            continue
        mapping[val] = pseudonymize_value(val, salt)
    return mapping


# ----------------------------
# 5) Self-test
# ----------------------------
if __name__ == "__main__":
    logger.info("Running anonymize.py self-test...")

    sample = "Contact John Doe at john.doe@example.com or call +1-555-987-6543. Card: 4111 1111 1111 1111"
    sample_detections = [
        {"type": "EMAIL", "value": "john.doe@example.com", "start": 21, "end": 42, "confidence": 0.98},
        {"type": "PHONE", "value": "+1-555-987-6543", "start": 53, "end": 69, "confidence": 0.88},
        {"type": "CREDIT_CARD", "value": "4111 1111 1111 1111", "start": 77, "end": 97, "confidence": 0.9},
    ]

    logger.info("Original: %s", sanitize_for_log(sample, 160))
    masked = anonymize_text(sample, sample_detections, policy="mask")
    logger.info("Masked : %s", sanitize_for_log(masked, 160))

    replaced = anonymize_text(sample, sample_detections, policy="replace")
    logger.info("Replaced: %s", sanitize_for_log(replaced, 160))

    pseudo = anonymize_text(sample, sample_detections, policy="pseudonymize", pseudo_salt="unit_test_salt")
    logger.info("Pseudonymized: %s", sanitize_for_log(pseudo, 160))

    mapping = create_pseudomap_from_detections(sample_detections, salt="unit_test_salt")
    logger.info("Pseudomap sample: %s", sanitize_for_log(str(mapping), 320))

    logger.info("anonymize.py self-test complete.")
