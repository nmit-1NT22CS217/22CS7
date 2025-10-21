"""
llm_workflow.py
---------------
Full orchestration of the anonymization → LLM → denormalization → validation pipeline.

Responsibilities:
  ✅ Detect PII in user text.
  ✅ Create pseudonym map and anonymize sensitive data.
  ✅ Send anonymized text *as-is* to Gemini LLM (no context, no structured prompt).
  ✅ Receive natural-language response and denormalize pseudonyms → real values.
  ✅ Validate that no pseudonyms remain and no original PII leaks.
  ✅ Persist all artifacts in outputs/<run_id>/ for full auditability.
"""

from __future__ import annotations
import os
import sys
import json
import re
from datetime import datetime
from typing import Dict, Any

# --- Ensure proper path imports for local scripts ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# --- Core dependencies ---
from scripts.detect_pii import detect_pii_in_text
from scripts.anonymize import anonymize_text
from scripts.pseudomap import create_map_for_detections, save_map, generate_run_id
from scripts.llm_client import call_llm
from scripts.denormalize import denormalize_by_run_id
from scripts.validation import run_validation
from scripts.utils import get_logger, ensure_dir, write_text_file, write_json_file

logger = get_logger("llm_workflow")


# -------------------------------------------------------------------------
# Helper: Safe JSON extraction (retained for compatibility)
# -------------------------------------------------------------------------
def extract_json_from_text(text: str) -> Dict[str, Any] | None:
    """Try to extract JSON from LLM text output if it exists."""
    if not text:
        return None
    try:
        clean = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()
        return json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                return None
        return None


# -------------------------------------------------------------------------
# Main Orchestration Function
# -------------------------------------------------------------------------
def process_text_with_llm(
    text: str,
    model: str | None = None,
    temperature: float = 0.4,
    max_tokens: int = 512,
) -> Dict[str, Any]:
    """
    Executes the entire workflow pipeline:
      1️⃣ Detect PII
      2️⃣ Create pseudonym mapping and anonymize text
      3️⃣ Send anonymized text directly to LLM (no context, no special formatting)
      4️⃣ Receive natural text response (with pseudonyms)
      5️⃣ Replace pseudonyms with original values (denormalization)
      6️⃣ Validate pipeline integrity
      7️⃣ Save all intermediate + final results
    """

    # --- Step 0: Setup run folder for outputs ---
    run_id = generate_run_id()
    output_dir = os.path.join(os.path.dirname(__file__), "..", "outputs", run_id)
    ensure_dir(output_dir)
    logger.info(f"🚀 Starting workflow for run_id={run_id}")

    # -----------------------------------------------------------------
    # 1️⃣ Detect PII
    # -----------------------------------------------------------------
    detections = detect_pii_in_text(text)
    logger.info(f"🔍 Detected {len(detections)} PII entities")

    if not detections:
        # Case: No sensitive data → No need to anonymize
        logger.warning("No PII detected — skipping anonymization.")
        result = {
            "ok": True,
            "run_id": run_id,
            "message": "No PII found in input text.",
            "detections": [],
            "anonymized_text": text,
            "llm_text": None,
            "llm_denormalized": None,
            "validation": None,
        }
        write_json_file(result, os.path.join(output_dir, "final_report.json"))
        return result

    # -----------------------------------------------------------------
    # 2️⃣ Create pseudonym map and anonymize
    # -----------------------------------------------------------------
    mapping = create_map_for_detections(detections)
    save_map(run_id, mapping)

    anonymized_text = anonymize_text(text, detections, policy="pseudonymize")
    write_text_file(os.path.join(output_dir, "anonymized.txt"), anonymized_text)
    logger.info("🔒 Text anonymized and pseudonym map saved.")

    # -----------------------------------------------------------------
    # 3️⃣ Send anonymized text to Gemini (NO CONTEXT)
    # -----------------------------------------------------------------
    logger.info("🧠 Sending anonymized text directly to Gemini LLM (no context, plain prompt).")

    # 💡 The anonymized text is sent *as-is*. Gemini will see PSEUDO_* values
    #     and respond naturally using them in its reply.
    prompt = anonymized_text.strip()

    llm_response = call_llm(
        prompt=prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    if not llm_response.get("ok"):
        logger.error(f"❌ LLM API call failed: {llm_response.get('text')}")
        return {
            "ok": False,
            "run_id": run_id,
            "error": llm_response.get("text", "LLM API error"),
        }

    llm_text = llm_response.get("text", "").strip()
    write_text_file(os.path.join(output_dir, "llm_raw_with_pseudos.txt"), llm_text)
    logger.info("✅ LLM raw response received and saved (contains pseudonyms).")

    # -----------------------------------------------------------------
    # 4️⃣ Denormalize (replace pseudonyms → originals)
    # -----------------------------------------------------------------
    logger.info("🔁 Running denormalization (replace pseudonyms with actual values).")
    llm_denormalized = denormalize_by_run_id(llm_text, run_id, backup_originals=True)
    write_text_file(os.path.join(output_dir, "llm_denormalized.txt"), llm_denormalized)
    logger.info("✅ Denormalization complete — pseudonyms replaced with original data.")

    # -----------------------------------------------------------------
    # 5️⃣ Validation
    # -----------------------------------------------------------------
    logger.info("🧾 Validating data integrity post-denormalization.")
    validation_results = run_validation(run_id, anonymized_text, llm_denormalized)
    logger.info(f"✅ Validation completed: {validation_results.get('overall_status')}")

    # -----------------------------------------------------------------
    # 6️⃣ Save final metadata report
    # -----------------------------------------------------------------
    result_data = {
        "ok": True,
        "run_id": run_id,
        "detections": detections,
        "anonymized_text": anonymized_text,
        "llm_text": llm_text,  # Raw LLM output (contains pseudonyms)
        "llm_denormalized": llm_denormalized,  # Final output (restored)
        "validation": validation_results,
    }

    write_json_file(result_data, os.path.join(output_dir, "final_report.json"))
    logger.info(f"🧩 Final report saved: outputs/{run_id}/final_report.json")

    return result_data


# -------------------------------------------------------------------------
# Self-Test Entry Point
# -------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("Running llm_workflow.py self-test...")

    sample_text = """
    Hi, I am Yashas. My email is yashas@example.com and my phone number is +1-555-123-9876.
    """

    result = process_text_with_llm(
        text=sample_text,
        model="gemini-2.5-flash",  # ✅ Ensure this matches your llm_client endpoint
        temperature=0.5,
        max_tokens=256,
    )

    print("\n=== WORKFLOW RESULT ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    logger.info("✅ llm_workflow self-test complete.")
