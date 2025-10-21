"""
pseudomap.py
------------
Handles creation, persistence, and retrieval of pseudonym mappings.

Responsibilities:
  - Generate deterministic pseudonym mappings for detected PII entities
  - Save and load pseudonym maps to/from JSON files
  - Ensure consistent pseudonymization for each run_id
  - Provide optional salt-based namespace control

Integration:
  Used by anonymization (to pseudonymize deterministically) and
  by LLM/deanonymization workflows to reverse pseudonyms back to originals.
"""

from __future__ import annotations
import os
import sys
# --- Permanent Import Fix ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# ----------------------------

import json
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime
from scripts.utils import ensure_dir, write_json_file, read_json_file, get_logger

logger = get_logger("pseudomap")

# -----------------------------------------------------------------------------
# 1️⃣ Helpers
# -----------------------------------------------------------------------------
DEFAULT_SALT = os.getenv("PSEUDO_SALT", "project_default_salt")
MAPPING_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")

def _hash_with_salt(value: str, salt: str) -> str:
    """Hash helper for deterministic pseudonyms."""
    return hashlib.sha256((value + salt).encode("utf-8", errors="ignore")).hexdigest()[:12]


# -----------------------------------------------------------------------------
# 2️⃣ Core Functions
# -----------------------------------------------------------------------------
def create_map_for_detections(
    detections: List[Dict[str, Any]],
    salt: Optional[str] = None,
    prefix: str = "PSEUDO"
) -> Dict[str, str]:
    """
    Build a mapping {original_value -> pseudonym}.
    Ensures unique deterministic pseudonyms for each PII entity.

    Args:
      detections: list of detected PII dicts
      salt: optional string salt for namespace separation
      prefix: optional pseudonym prefix
    """
    mapping: Dict[str, str] = {}
    salt = salt or DEFAULT_SALT

    for d in detections:
        val = d.get("value")
        if not val or val in mapping:
            continue

        token = _hash_with_salt(val, salt)
        mapping[val] = f"{prefix}_{token}"

    logger.info(f"✅ Created pseudomap for {len(mapping)} entries")
    return mapping


def save_map(run_id: str, mapping: Dict[str, str]) -> str:
    """
    Save pseudonym mapping under `outputs/<run_id>/mapping.json`.
    """
    folder = os.path.join(MAPPING_DIR, run_id)
    ensure_dir(folder)

    path = os.path.join(folder, "mapping.json")
    write_json_file(mapping, path)
    logger.info(f"💾 Mapping saved: {path}")
    return path


def load_map(run_id: str) -> Dict[str, str]:
    """
    Load a pseudonym mapping from the outputs directory.
    """
    path = os.path.join(MAPPING_DIR, run_id, "mapping.json")
    if not os.path.exists(path):
        logger.warning(f"⚠️ Mapping file not found for run_id={run_id}")
        return {}
    mapping = read_json_file(path)
    logger.info(f"📂 Loaded pseudomap with {len(mapping)} entries from {path}")
    return mapping


# -----------------------------------------------------------------------------
# 3️⃣ Utility Functions
# -----------------------------------------------------------------------------
def generate_run_id() -> str:
    """Create a timestamp-based unique run_id."""
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def pseudonymize_list(values: List[str], salt: Optional[str] = None, prefix: str = "PSEUDO") -> Dict[str, str]:
    """
    Convenience for bulk pseudonymization of arbitrary values.
    """
    salt = salt or DEFAULT_SALT
    return {v: f"{prefix}_{_hash_with_salt(v, salt)}" for v in values if v}


# -----------------------------------------------------------------------------
# 4️⃣ Self-Test
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("Running pseudomap.py self-test...")

    test_detections = [
        {"type": "EMAIL", "value": "alice@example.com"},
        {"type": "PHONE", "value": "+1-555-222-3333"},
        {"type": "IP_ADDRESS", "value": "192.168.0.1"},
    ]

    run_id = generate_run_id()
    salt = "demo_salt"

    mapping = create_map_for_detections(test_detections, salt=salt)
    print("\nGenerated Mapping:")
    print(json.dumps(mapping, indent=2))

    saved_path = save_map(run_id, mapping)
    print(f"\nMapping saved at: {saved_path}")

    loaded = load_map(run_id)
    print("\nLoaded Mapping:")
    print(json.dumps(loaded, indent=2))

    assert mapping == loaded, "❌ Mismatch between saved and loaded pseudomap!"
    logger.info("✅ pseudomap.py self-test passed.")
