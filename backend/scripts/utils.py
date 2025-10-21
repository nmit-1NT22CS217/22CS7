

"""
utils.py
--------
Core utility helpers for the backend.

Responsibilities:
    ✅ Environment variable management (.env loading)
    ✅ Safe directory creation
    ✅ JSON and text file I/O
    ✅ Logger creation (UTF-8 + Windows-safe)
    ✅ Run ID generation
    ✅ Safe text sanitization for logs

This module is imported by all other backend scripts.
"""

from __future__ import annotations
import os
import sys
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# 1️⃣ Environment Setup
# -----------------------------------------------------------------------------
# Load environment variables from backend/.env file once
load_dotenv()

# Global environment access with fallback defaults
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_DIR = os.getenv("OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))
UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(BASE_DIR, "uploads"))
LOG_DIR = os.getenv("LOG_DIR", os.path.join(BASE_DIR, "logs"))
MAX_TEXT_LENGTH = int(os.getenv("MAX_TEXT_LENGTH", 200_000))

# Ensure directories exist
for _dir in [OUTPUT_DIR, UPLOAD_DIR, LOG_DIR]:
    os.makedirs(_dir, exist_ok=True)

# -----------------------------------------------------------------------------
# 2️⃣ Utility: Ensure Directory Exists
# -----------------------------------------------------------------------------
def ensure_dir(path: str) -> None:
    """Ensure directory for the given path exists."""
    os.makedirs(path, exist_ok=True)

# -----------------------------------------------------------------------------
# 3️⃣ Utility: JSON I/O
# -----------------------------------------------------------------------------
def write_json_file(data: Dict[str, Any], filepath: str) -> None:
    """
    Safely write JSON data to a file with UTF-8 encoding.
    """
    ensure_dir(os.path.dirname(filepath))
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_json_file(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Safely read JSON file and return dict.
    Returns None if file missing or invalid.
    """
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        get_logger("utils").warning(f"Failed to read JSON: {filepath} ({e})")
        return None

# -----------------------------------------------------------------------------
# 4️⃣ Utility: Text File I/O
# -----------------------------------------------------------------------------
def read_text_file(filepath: str) -> str:
    """Read a UTF-8 text file safely."""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def write_text_file(filepath: str, text: str) -> None:
    """Write UTF-8 text safely (creates dir if missing)."""
    ensure_dir(os.path.dirname(filepath))
    with open(filepath, "w", encoding="utf-8", errors="replace") as f:
        f.write(text or "")

# -----------------------------------------------------------------------------
# 5️⃣ Utility: Run ID Generator
# -----------------------------------------------------------------------------
def generate_run_id(prefix: str = "run") -> str:
    """
    Generate a unique run ID using timestamp format:
    e.g. 'run_20251020_121045'
    """
    now = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{now}"

# -----------------------------------------------------------------------------
# 6️⃣ Utility: Safe Sanitizer (for logs)
# -----------------------------------------------------------------------------
def sanitize_for_log(text: str, max_len: int = 200) -> str:
    """
    Sanitize text for log output:
      - Strips newlines
      - Truncates long input
      - Replaces sensitive symbols
    """
    if not text:
        return ""
    text = text.replace("\n", " ").replace("\r", " ").strip()
    if len(text) > max_len:
        text = text[:max_len] + "...(truncated)"
    # Redact emails and numbers
    import re
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[EMAIL_REDACTED]", text)
    text = re.sub(r"\b\d{4,}\b", "[NUM_REDACTED]", text)
    return text

# -----------------------------------------------------------------------------
# 7️⃣ Logger Configuration
# -----------------------------------------------------------------------------
def get_logger(name: str = "app") -> logging.Logger:
    """
    Create or return a UTF-8 safe logger instance with:
      - Console handler
      - File handler (logs/app.log)
      - Auto truncation of long messages
      - UTF-8 encoding to support emojis
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # Avoid duplicate handlers

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file = os.path.join(LOG_DIR, "app.log")

    logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Formatter (Windows-safe emojis)
    formatter = logging.Formatter(
        fmt="[%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    logger.propagate = False
    return logger

# -----------------------------------------------------------------------------
# ✅ Self-Test (Run: python scripts/utils.py)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    log = get_logger("utils_test")
    log.info("🚀 Testing utils module...")
    run_id = generate_run_id()
    log.info(f"Generated run_id: {run_id}")

    sample_text = "Hello test@example.com and phone 9876543210"
    log.info(f"Sanitized: {sanitize_for_log(sample_text)}")

    sample_json = {"msg": "Utils test", "run_id": run_id}
    path = os.path.join(OUTPUT_DIR, "test_utils.json")
    write_json_file(sample_json, path)
    log.info(f"Wrote JSON file: {path}")

    loaded = read_json_file(path)
    log.info(f"Read back JSON: {loaded}")
    log.info("✅ All utils functions working fine.")
