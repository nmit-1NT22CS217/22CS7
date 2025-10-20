"""
extract_text.py
---------------
The Data Extraction Layer.

Responsibilities:
    ✅ Read and normalize raw content from various file types
    ✅ Convert structured or binary input (e.g. JSON, PCAP) into plain text
    ✅ Ensure UTF-8 safety and consistent normalization
    ✅ Provide clean text for the PII detection module

Supported formats:
    - .txt
    - .json
    - .pcap  (requires Scapy)
"""
from __future__ import annotations
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import json
import re
from typing import List, Dict, Any

# External dependency: scapy (for .pcap)
try:
    from scapy.all import rdpcap, Raw
except ImportError:
    rdpcap = None

from scripts.utils import get_logger, read_text_file, sanitize_for_log

logger = get_logger("extract_text")

# -----------------------------------------------------------------------------
# 1️⃣ Normalization Utilities
# -----------------------------------------------------------------------------
def normalize_text(text: str) -> str:
    """
    Normalize extracted text:
      - Convert to UTF-8 clean text
      - Remove excessive whitespace and control chars
      - Replace newlines with single space
    """
    if not text:
        return ""
    text = text.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


# -----------------------------------------------------------------------------
# 2️⃣ TXT Extraction
# -----------------------------------------------------------------------------
def extract_from_text_file(path: str) -> str:
    """Extract plain text from a .txt file."""
    logger.info(f"📄 Extracting from text file: {sanitize_for_log(path)}")
    text = read_text_file(path)
    return normalize_text(text)


# -----------------------------------------------------------------------------
# 3️⃣ JSON Extraction
# -----------------------------------------------------------------------------
def extract_from_json_file(path: str) -> str:
    """
    Extract key-value pairs from JSON file into flat text.

    Example:
        {"name": "John", "email": "john@example.com"}
        → "name: John | email: john@example.com"
    """
    logger.info(f"🧾 Extracting from JSON: {sanitize_for_log(path)}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"❌ Failed to parse JSON file: {path} ({e})")
        return ""

    lines = []

    def recurse(obj, prefix=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                recurse(v, f"{prefix}{k}.")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                recurse(v, f"{prefix}[{i}].")
        else:
            lines.append(f"{prefix.strip('.')}: {str(obj)}")

    recurse(data)
    combined = " | ".join(lines)
    return normalize_text(combined)


# -----------------------------------------------------------------------------
# 4️⃣ PCAP Extraction
# -----------------------------------------------------------------------------
def extract_from_pcap(path: str, max_packets: int = 500) -> List[Dict[str, Any]]:
    """
    Extract application-layer payloads from a PCAP file.

    Returns list of {packet_no, src, dst, text}.
    Each payload is normalized plain text.

    Requires: scapy (pip install scapy)
    """
    if rdpcap is None:
        logger.warning("⚠️ Scapy not installed. Skipping PCAP extraction.")
        return []

    logger.info(f"🔍 Extracting payloads from PCAP: {sanitize_for_log(path)}")
    packets = rdpcap(path)
    results = []

    for i, pkt in enumerate(packets[:max_packets]):
        try:
            if Raw in pkt:
                payload = pkt[Raw].load.decode("utf-8", errors="ignore")
                clean = normalize_text(payload)
                if clean:
                    results.append({
                        "packet_no": i + 1,
                        "src": pkt[0][1].src if hasattr(pkt[0][1], "src") else "unknown",
                        "dst": pkt[0][1].dst if hasattr(pkt[0][1], "dst") else "unknown",
                        "text": clean
                    })
        except Exception as e:
            logger.debug(f"Skipping packet {i}: {e}")

    logger.info(f"✅ Extracted {len(results)} readable payloads.")
    return results


# -----------------------------------------------------------------------------
# 5️⃣ Auto Dispatcher
# -----------------------------------------------------------------------------
def extract_text_from_file(path: str) -> str:
    """
    Automatically determine file type and extract accordingly.
    """
    ext = os.path.splitext(path)[1].lower()

    if ext == ".txt":
        return extract_from_text_file(path)
    elif ext == ".json":
        return extract_from_json_file(path)
    elif ext == ".pcap":
        payloads = extract_from_pcap(path)
        return " ".join([p["text"] for p in payloads])
    else:
        logger.warning(f"⚠️ Unsupported file type: {path}")
        return ""


# -----------------------------------------------------------------------------
# ✅ Self-Test (Run: python scripts/extract_text.py)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    from scripts.utils import write_text_file

    logger.info("🚀 Running extract_text self-test...")

    # --- 1. Text file ---
    path_txt = "backend/uploads/sample.txt"
    os.makedirs(os.path.dirname(path_txt), exist_ok=True)
    write_text_file(path_txt, "Name: John Doe\nEmail: john@example.com\nPhone: 9876543210")
    print("\nTXT Output:")
    print(extract_text_from_file(path_txt))

    # --- 2. JSON file ---
    path_json = "backend/uploads/sample.json"
    with open(path_json, "w", encoding="utf-8") as f:
        json.dump({"user": {"name": "Alice", "email": "alice@abc.com"}}, f)
    print("\nJSON Output:")
    print(extract_text_from_file(path_json))

    # --- 3. PCAP (optional) ---
    if rdpcap:
        print("\nPCAP Output:")
        print(extract_from_pcap("backend/uploads/sample.pcap"))
    else:
        print("\n[SKIP] PCAP extraction test (scapy not installed)")

    logger.info("✅ extract_text.py self-test completed.")
