"""
core/anonymizer.py

AI Orchestration Layer for Secure LLM Interaction.

ALL security decisions are NLP-driven.
NO regex.
NO hard-coded rules.
"""

from typing import Dict, Optional

# -------------------------------------------------
# NLP / AI MODELS
# -------------------------------------------------
from core.nlp_models import injection_detector, sensitivity_classifier

# -------------------------------------------------
# NLP PII EXECUTION ENGINE
# -------------------------------------------------
from core.analyzer import PIIAnonymizer

# -------------------------------------------------
# SECURE STORAGE
# -------------------------------------------------
from core.storage import store_mapping, restore_mapping

# -------------------------------------------------
# LLM CLIENT (UNTRUSTED)
# -------------------------------------------------
from core.llm_client import call_llm as call_llm_safe


# -------------------------------------------------
# GLOBAL NLP ENGINE
# -------------------------------------------------
pii_analyzer = PIIAnonymizer()

INJECTION_THRESHOLD = 0.85
LEAKAGE_THRESHOLD = 0.75


# =========================================================
# MAIN ENTRY POINT
# =========================================================
def process_prompt(
    text: str,
    role: str = "user",
    mode: str = "pseudonymize",
    call_llm: bool = True
) -> Dict[str, Optional[str]]:

    # -------------------------------------------------
    # 1️⃣ PROMPT INJECTION DETECTION (EXPLAINABLE NLP)
    # -------------------------------------------------
    analysis = injection_detector.analyze(text)

    if analysis["score"] >= INJECTION_THRESHOLD:
        reasons = "\n".join(
            f"- '{s['phrase']}' → {s['category']} (weight={s['weight']})"
            for s in analysis["signals"]
        )

        return {
            "anonymized_text": "[BLOCKED]",
            "llm_response": (
                "❌ Prompt blocked by AI injection detector.\n\n"
                "Detected signals:\n"
                f"{reasons}\n\n"
                f"Total Risk Score: {analysis['score']:.2f}"
            ),
            "deanonymized_text": None,
            "mappings_count": 0
        }

    # -------------------------------------------------
    # 2️⃣ NLP-ONLY PII ANONYMIZATION (INGRESS)
    # -------------------------------------------------
    if mode == "mask":
        anonymized_text, mappings = pii_analyzer.mask(text)
    elif mode == "replace":
        anonymized_text, mappings = pii_analyzer.replace(text)
    else:
        anonymized_text, mappings = pii_analyzer.pseudonymize(text)

    if mappings:
        store_mapping(mappings)

    # -------------------------------------------------
    # 3️⃣ ZERO-TRUST LLM CALL
    # -------------------------------------------------
    llm_response = None
    if call_llm:
        llm_response = call_llm_safe(anonymized_text, role)

    # -------------------------------------------------
    # 4️⃣ NLP OUTPUT LEAKAGE SCAN (EGRESS)
    # -------------------------------------------------
    safe_llm_response = llm_response

    if llm_response:
        leaked_entities = pii_analyzer.detect_pii(llm_response)

        for value, _, _, _ in leaked_entities:
            scores = sensitivity_classifier.predict(value)

            if (
                scores.get("confidential", 0) >= LEAKAGE_THRESHOLD
                or scores.get("restricted", 0) >= LEAKAGE_THRESHOLD
            ):
                safe_llm_response = safe_llm_response.replace(
                    value, "[REDACTED]"
                )

    # -------------------------------------------------
    # 5️⃣ DE-ANONYMIZATION (ALWAYS ALLOWED)
    # -------------------------------------------------
    deanonymized_text = None
    if safe_llm_response and mappings:
        deanonymized_text = restore_mapping(safe_llm_response)

    # -------------------------------------------------
    # FINAL STRUCTURED RESPONSE
    # -------------------------------------------------
    return {
        "anonymized_text": anonymized_text,
        "llm_response": safe_llm_response,
        "deanonymized_text": deanonymized_text,
        "mappings_count": len(mappings)
    }
