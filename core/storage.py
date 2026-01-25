"""
core/storage.py

Secure Mapping Storage & Reversible De-anonymization Layer.

This module:
- Stores reversible PII mappings created during anonymization
- Restores original values unconditionally
- Acts as the final privacy gate before data is returned

NOTE:
- Role-based restrictions are intentionally REMOVED
- This is suitable for demos, academic projects, and internal tools
"""

from typing import Dict

# -------------------------------------------------
# IN-MEMORY STORE
# (Can be replaced with DB / Redis / Vault later)
# -------------------------------------------------
_MAPPING_STORE: Dict[str, str] = {}


# =================================================
# STORE MAPPINGS
# =================================================
def store_mapping(mapping: Dict[str, str]) -> None:
    """
    Store anonymization mappings.

    Args:
        mapping: Dict of placeholder -> original value
    """
    if not mapping:
        return

    _MAPPING_STORE.update(mapping)


# =================================================
# RESTORE MAPPINGS (NO ROLE CHECK)
# =================================================
def restore_mapping(text: str) -> str:
    """
    Restore original values from placeholders.

    Args:
        text: Text containing anonymized placeholders

    Returns:
        Fully deanonymized text
    """
    restored_text = text

    # Replace longer placeholders first to avoid partial replacements
    for placeholder, original in sorted(
        _MAPPING_STORE.items(),
        key=lambda x: len(x[0]),
        reverse=True
    ):
        restored_text = restored_text.replace(placeholder, original)

    return restored_text


# =================================================
# MAINTENANCE / SAFETY
# =================================================
def clear_store() -> None:
    """
    Clear all stored mappings.
    """
    _MAPPING_STORE.clear()
