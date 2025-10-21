"""
logger.py
----------
Centralized logger utility for the entire backend.

Provides:
  ✅ Consistent log formatting across all modules.
  ✅ Automatic timestamping.
  ✅ Windows-safe encoding (no emoji errors).
  ✅ Info, Warning, Error level support.
"""

import logging
import sys

def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured logger instance with consistent formatting.
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers if called multiple times
    if logger.hasHandlers():
        return logger

    handler = logging.StreamHandler(sys.stdout)

    formatter = logging.Formatter(
        fmt="[%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    # 🔒 Fix for Windows encoding (avoids UnicodeEncodeError)
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    return logger
