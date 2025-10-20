"""
llm_workflow.py
---------------
Full orchestration of the anonymization → LLM → denormalization → validation pipeline.

Responsibilities:
  ✅ Detect PII in user text.
  ✅ Create pseudonym map and anonymize sensitive data.
  ✅ Send anonymized text to Gemini LLM via llm_client.
  ✅ Receive response and denormalize it back using stored mapping.
  ✅ Validate all steps (no leftover PII/pseudonyms).
  ✅ Persist all artifacts in outputs/<run_id>/ for auditability.
"""

from __future__ import annotations
import os
import sys
import json
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
# Main Orchestration Function (renamed for global use)
# -------------------------------------------------------------------------
def process_text_with_llm(
    text: str,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 512,
) -> Dict[str, Any]:
    """
    The master function that executes:
        1️⃣ PII Detection
        2️⃣ Pseudonymization
        3️⃣ LLM Processing
        4️⃣ Denormalization
        5️⃣ Validation + Reporting

    Returns a full structured result dictionary.
    """
    # --- Initialize run ID and folders ---
    run_id = generate_run_id()
    output_dir = os.path.join(os.path.dirname(__file__), "..", "outputs", run_id)
    ensure_dir(output_dir)
    logger.info(f"🚀 Starting workflow for run_id={run_id}")

    # -----------------------------------------------------------------
    # 1️⃣ Step 1: Detect PII
    # -----------------------------------------------------------------
    detections = detect_pii_in_text(text)
    logger.info(f"🔍 Detected {len(detections)} PII entities")

    if not detections:
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
    # 2️⃣ Step 2: Create pseudonym mapping and anonymize
    # -----------------------------------------------------------------
    mapping = create_map_for_detections(detections)
    save_map(run_id, mapping)

    anonymized_text = anonymize_text(text, detections, policy="pseudonymize")
    write_text_file(os.path.join(output_dir, "anonymized.txt"), anonymized_text)
    logger.info("🔒 Anonymization complete and mapping saved")

    # -----------------------------------------------------------------
    # 3️⃣ Step 3: Send anonymized text to Gemini API
    # -----------------------------------------------------------------
    logger.info("🧠 Sending anonymized text to Gemini LLM")
    llm_response = call_llm(
        prompt=(
            "Analyze this anonymized customer report. "
            "Provide a summary and two key recommendations:\n\n"
            f"{anonymized_text}"
        ),
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

    llm_text = llm_response.get("text", "")
    write_text_file(os.path.join(output_dir, "llm_raw_with_pseudos.txt"), llm_text)
    logger.info("✅ LLM response received and saved")

    # -----------------------------------------------------------------
    # 4️⃣ Step 4: Denormalize (replace pseudonyms → originals)
    # -----------------------------------------------------------------
    logger.info("🔁 Starting denormalization process")
    llm_denormalized = denormalize_by_run_id(llm_text, run_id, backup_originals=True)
    logger.info("✅ Denormalization complete")

    # -----------------------------------------------------------------
    # 5️⃣ Step 5: Validate pipeline integrity
    # -----------------------------------------------------------------
    logger.info("🧾 Running full validation checks")
    validation_results = run_validation(run_id, anonymized_text, llm_denormalized)

    # -----------------------------------------------------------------
    # 6️⃣ Step 6: Save full metadata report
    # -----------------------------------------------------------------
    result_data = {
        "ok": True,
        "run_id": run_id,
        "detections": detections,
        "anonymized_text": anonymized_text,
        "llm_text": llm_text,
        "llm_denormalized": llm_denormalized,
        "validation": validation_results,
    }

    write_json_file(result_data, os.path.join(output_dir, "final_report.json"))
    logger.info(f"🧩 Final report saved to outputs/{run_id}/final_report.json")

    return result_data


# -------------------------------------------------------------------------
# Self-Test Entry Point
# -------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("Running llm_workflow.py self-test...")

    sample_text = """
    Customer: Hello, my name is Alice Johnson. My email is alice.j@example.com and my phone number is +1-555-123-9876.
    I lost my credit card ending with 7890 yesterday in New York.
    """

    result = process_text_with_llm(
        text=sample_text,
        model="gemini-1.5-flash",
        temperature=0.4,
        max_tokens=256,
    )

    print("\n=== WORKFLOW RESULT ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    logger.info("✅ llm_workflow self-test complete.")
