"""
denormalize.py
--------------
Reversible denormalization utilities.

Responsibilities:
  - Replace pseudonyms in LLM output using saved pseudomap.
  - Safe token-aware replacement (avoids partial matches).
  - Optional backup of both anonymized and restored versions.

Features:
  ✅ Mapping-based reversible transformation
  ✅ File persistence (outputs/<run_id>/llm_raw_with_pseudos.txt, llm_denormalized.txt)
  ✅ Collision-safe replacements using regex boundaries
"""

from __future__ import annotations
import os
import re
import sys
from typing import Dict, Optional

# --- Permanent import fix ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.utils import get_logger, sanitize_for_log, ensure_dir, write_text_file
from scripts.pseudomap import load_map

logger = get_logger("denormalize")


# ---------------------------------------------------------------------
# Regex helper
# ---------------------------------------------------------------------
def _build_token_regex(token: str) -> re.Pattern:
    """
    Build a regex that matches pseudonym as a standalone token.
    Prevents partial matches inside words.
    Example: token='PSEUDO_ab12' → pattern='(?<!\\w)PSEUDO_ab12(?!\\w)'
    """
    esc = re.escape(token)
    return re.compile(rf"(?<!\w){esc}(?!\w)")


# ---------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------
def denormalize_text(
    llm_text: str,
    mapping: Dict[str, str],
    run_id: Optional[str] = None,
    backup_originals: bool = False,
) -> str:
    """
    Replace pseudonyms in `llm_text` using mapping { original -> pseudo }.

    Args:
        llm_text:       Text returned from LLM (contains pseudonyms)
        mapping:        Dict { original_value -> pseudonym }
        run_id:         Unique run identifier (used for file output if backup=True)
        backup_originals: If True, saves both raw and denormalized versions under outputs/<run_id>/

    Returns:
        denormalized text
    """
    if not llm_text or not mapping:
        logger.warning("denormalize_text: missing text or mapping")
        return llm_text or ""

    # --- 1️⃣ Reverse mapping ---
    reverse_map = {pseudo: orig for orig, pseudo in mapping.items() if pseudo and orig}
    if not reverse_map:
        logger.warning("denormalize_text: reverse map empty")
        return llm_text

    # --- 2️⃣ Sort pseudonyms (avoid partial substring overlaps) ---
    pseudos_sorted = sorted(reverse_map.keys(), key=lambda s: len(s), reverse=True)

    result = llm_text
    replaced_count = 0

    # --- 3️⃣ Replace pseudonyms safely ---
    for pseudo in pseudos_sorted:
        orig = reverse_map[pseudo]
        regex = _build_token_regex(pseudo)
        new_result, n = regex.subn(lambda m: orig, result)
        if n > 0:
            replaced_count += n
            result = new_result
            logger.debug(f"🔁 {pseudo} → {sanitize_for_log(orig, 80)} ({n}x)")

    logger.info(f"✅ Denormalization complete — replaced {replaced_count} pseudonym(s)")

    # --- 4️⃣ Optional file backup ---
    if backup_originals and run_id:
        out_dir = os.path.join(os.path.dirname(__file__), "..", "outputs", run_id)
        ensure_dir(out_dir)

        raw_path = os.path.join(out_dir, "llm_raw_with_pseudos.txt")
        denorm_path = os.path.join(out_dir, "llm_denormalized.txt")

        try:
            write_text_file(raw_path, llm_text)
            write_text_file(denorm_path, result)
            logger.info(f"💾 Saved backups: \n  - {raw_path}\n  - {denorm_path}")
        except Exception as e:
            logger.warning(f"Failed to write backup files: {e}")

    return result


# ---------------------------------------------------------------------
# Convenience wrapper (auto-load mapping)
# ---------------------------------------------------------------------
def denormalize_by_run_id(
    llm_text: str,
    run_id: str,
    backup_originals: bool = True,
) -> str:
    """
    Load mapping for a given run_id and denormalize.
    Automatically saves backup copies of both LLM and restored text.
    """
    if not run_id:
        raise ValueError("run_id required")

    mapping = load_map(run_id)
    if not mapping:
        logger.warning(f"No mapping found for run_id={run_id}, returning original text")
        return llm_text

    return denormalize_text(llm_text, mapping, run_id=run_id, backup_originals=backup_originals)


# ---------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------
def find_remaining_pseudonyms(text: str, mapping: Dict[str, str]) -> Dict[str, int]:
    """
    Scan `text` for any remaining pseudonyms (post-denormalization).
    Returns dict pseudo -> count.
    """
    reverse_map = {pseudo: orig for orig, pseudo in mapping.items() if pseudo and orig}
    counts = {}
    for pseudo in reverse_map:
        regex = _build_token_regex(pseudo)
        found = regex.findall(text)
        if found:
            counts[pseudo] = len(found)
    return counts


# ---------------------------------------------------------------------
# Self-Test
# ---------------------------------------------------------------------
if __name__ == "__main__":
    from scripts.pseudomap import create_map_for_detections, save_map, generate_run_id

    logger.info("Running denormalize.py self-test (with backup mode)...")

    detections = [
        {"type": "EMAIL", "value": "alice@example.com"},
        {"type": "PHONE", "value": "+1-555-111-2222"},
    ]
    run_id = generate_run_id()
    mapping = create_map_for_detections(detections, salt="demo_salt")
    save_map(run_id, mapping)

    pseudo_values = list(mapping.values())
    llm_text = f"Contact {pseudo_values[0]} for support or call {pseudo_values[1]}."

    print("\n--- LLM (pseudonymized) Output ---")
    print(llm_text)

    restored = denormalize_by_run_id(llm_text, run_id, backup_originals=True)

    print("\n--- Denormalized Output ---")
    print(restored)

    print("\nRemaining pseudos:", find_remaining_pseudonyms(restored, mapping))
    logger.info("Self-test complete ✅")
