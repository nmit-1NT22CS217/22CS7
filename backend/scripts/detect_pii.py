"""
detect_pii.py
-------------
PII detection module.

Responsibilities:
 - Detect common PII types using robust regex patterns:
     EMAIL, PHONE, CREDIT_CARD, IP_ADDRESS, SSN, NAME (heuristic)
 - Provide structured detection entries with start/end offsets and confidence score
 - Avoid overlapping detections by preferring longer / higher-confidence matches
 - Export detect_pii_in_text(text) function for pipeline integration
"""

import os
import sys
# ------------------ Permanent import fix ------------------
# ensures `from scripts.utils import ...` works when running scripts directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# ----------------------------------------------------------

import re
from typing import List, Dict, Any, Tuple
from scripts.utils import get_logger, sanitize_for_log

logger = get_logger("detect_pii")

# -----------------------------------------------------------------------------
# 1) Regex patterns and simple confidence heuristics
# -----------------------------------------------------------------------------
# Note: these patterns prioritize precision. You can relax them for recall if needed.
_PATTERNS: Dict[str, Dict[str, Any]] = {
    "EMAIL": {
        "pattern": re.compile(
            r"(?P<email>[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})",
            re.IGNORECASE,
        ),
        "base_confidence": 0.98,
        "rule": "email_regex",
    },
    "PHONE": {
        # Strict pattern: must have 7–15 digits and typical separators
        "pattern": re.compile(
            r"(?P<phone>(?:\+?\d{1,3}[\s\-\.])?(?:\(?\d{2,4}\)?[\s\-\.])?\d{3,4}[\s\-\.]?\d{3,4})(?!\d)"
        ),
        "base_confidence": 0.85,
        "rule": "phone_regex",
    },
    "CREDIT_CARD": {
        # Visa/Mastercard/Amex naive patterns: groups of 13-16 digits possibly separated by spaces/dashes
        "pattern": re.compile(r"(?P<cc>(?:\d[ -]*?){13,19})"),
        "base_confidence": 0.75,
        "rule": "creditcard_generic",
    },
    "IP_ADDRESS": {
        # IPv4 only (simple)
        "pattern": re.compile(
            r"(?P<ip>(?:\b25[0-5]|\b2[0-4]\d|\b1?\d{1,2})(?:\.(?:25[0-5]|2[0-4]\d|1?\d{1,2})){3})"
        ),
        "base_confidence": 0.95,
        "rule": "ipv4_regex",
    },
    "SSN": {
        # US SSN forms: 123-45-6789 or 123456789
        "pattern": re.compile(r"(?P<ssn>\b\d{3}-?\d{2}-?\d{4}\b)"),
        "base_confidence": 0.9,
        "rule": "ssn_regex",
    },
    "NAME": {
        # Sequences of capitalized words (2–3 tokens) — heuristic
        "pattern": re.compile(r"\b([A-Z][a-z]{1,}\s+[A-Z][a-z]{1,}(?:\s+[A-Z][a-z]{1,})?)\b"),
        "base_confidence": 0.45,
        "rule": "name_heuristic",
    },
}

# -----------------------------------------------------------------------------
# 2) Helpers: confidence adjusters and overlap resolver
# -----------------------------------------------------------------------------
def _score_credit_card(candidate: str) -> float:
    """Heuristic Luhn-like check for credit-card-like strings."""
    digits = re.sub(r"\D", "", candidate)
    if len(digits) < 13 or len(digits) > 19:
        return 0.0
    try:
        total = 0
        reverse_digits = digits[::-1]
        for i, ch in enumerate(reverse_digits):
            d = int(ch)
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        if total % 10 == 0:
            return 0.95
    except Exception:
        pass
    if 13 <= len(digits) <= 19:
        return 0.78
    return 0.0


def _normalize_span(start: int, end: int, text_len: int) -> Tuple[int, int]:
    """Clamp spans to text boundaries."""
    return max(0, start), min(end, text_len)


def _resolve_overlaps(detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove overlapping detections by preferring:
      1) higher confidence
      2) longer span (if confidence equal)
    Returns sorted list by start index.
    """
    if not detections:
        return []

    detections_sorted = sorted(
        detections, key=lambda d: (d["start"], -d["confidence"], -(d["end"] - d["start"]))
    )

    chosen: List[Dict[str, Any]] = []
    for d in detections_sorted:
        overlap = False
        for c in chosen:
            if not (d["end"] <= c["start"] or d["start"] >= c["end"]):
                # overlap exists
                if d["confidence"] > c["confidence"] or (
                    d["confidence"] == c["confidence"] and (d["end"] - d["start"]) > (c["end"] - c["start"])
                ):
                    chosen.remove(c)
                    chosen.append(d)
                overlap = True
                break
        if not overlap:
            chosen.append(d)
    return sorted(chosen, key=lambda x: x["start"])


# -----------------------------------------------------------------------------
# 3) Main detection routine
# -----------------------------------------------------------------------------
def detect_pii_in_text(text: str) -> List[Dict[str, Any]]:
    """
    Detect PII in the supplied text and return structured results.
    """
    if not text:
        return []

    text_len = len(text)
    logger.info(f"Running PII detection on input (len={text_len})")
    candidates: List[Dict[str, Any]] = []

    for pii_type, meta in _PATTERNS.items():
        pat = meta["pattern"]
        base_conf = float(meta.get("base_confidence", 0.5))
        rule = meta.get("rule", "pattern")

        for m in pat.finditer(text):
            val = m.group(0)
            start, end = _normalize_span(m.start(0), m.end(0), text_len)

            confidence = base_conf

            # credit card check
            if pii_type == "CREDIT_CARD":
                confidence = max(confidence, _score_credit_card(val))
            # phone heuristics
            elif pii_type == "PHONE":
                digits = len(re.sub(r"\D", "", val))
                if digits < 7:
                    continue
                elif 7 <= digits <= 15:
                    confidence = max(confidence, 0.88)
                else:
                    confidence = min(confidence, 0.6)
            # name heuristics
            elif pii_type == "NAME":
                tokens = val.split()
                if len(tokens) >= 2 and all(len(tok) > 1 for tok in tokens):
                    confidence = max(confidence, 0.45)
                else:
                    confidence = 0.2

            if end - start < 2:
                continue

            candidates.append({
                "type": pii_type,
                "value": val,
                "start": start,
                "end": end,
                "confidence": round(float(confidence), 3),
                "rule": rule,
            })

    # Resolve overlaps
    final = _resolve_overlaps(candidates)

    # -------------------------------------------------------------------------
    # NEW: Filter out pseudonyms or any detection inside pseudonym spans
    # -------------------------------------------------------------------------
    pseudo_spans = [
        (m.start(), m.end())
        for m in re.finditer(r"PSEUDO_[0-9a-fA-F]+", text)
    ]

    def inside_pseudo(start: int, end: int) -> bool:
        for ps, pe in pseudo_spans:
            if start >= ps and end <= pe:
                return True
        return False

    cleaned: List[Dict[str, Any]] = []
    for d in final:
        val = d["value"]
        if inside_pseudo(d["start"], d["end"]):
            logger.debug(f"Ignoring detection inside pseudonym span: {val}")
            continue
        if "PSEUDO_" in val:
            logger.debug(f"Ignoring pseudonym-like detection: {val}")
            continue
        cleaned.append(d)

    logger.info(f"Detection complete: {len(cleaned)} valid items found (after cleaning).")
    return cleaned


# -----------------------------------------------------------------------------
# 4) Convenience wrapper
# -----------------------------------------------------------------------------
def detect_pii(text: str) -> List[Dict[str, Any]]:
    """Backwards-compatible wrapper name."""
    return detect_pii_in_text(text)


# -----------------------------------------------------------------------------
# Self-test (run: python scripts/detect_pii.py)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    sample = (
        "Contact John Doe (john.doe@example.com) or +1-555-987-6543. "
        "Customer SSN is 123-45-6789. Tester IP 192.168.1.100. Card: 4111 1111 1111 1111. "
        "PSEUDO_fa11579224fb should NOT be detected."
    )
    logger.info("Running detect_pii.py self-test...")
    results = detect_pii_in_text(sample)
    import json as _json

    print("\n=== SAMPLE INPUT ===")
    print(sample)
    print("\n=== DETECTIONS ===")
    print(_json.dumps(results, indent=2, ensure_ascii=False))
    logger.info("detect_pii self-test complete.")
