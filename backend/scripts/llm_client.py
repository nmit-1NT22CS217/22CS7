# scripts/llm_client.py
"""
llm_client.py
-------------
Unified interface for calling Large Language Models (LLMs).
Supports:
  - ✅ Gemini (Google Generative Language REST API)
  - ✅ OpenAI-compatible APIs
  - ✅ Mock mode for offline testing / CI

Features:
  - Retries with exponential backoff (for 429 / 5xx errors)
  - Robust response extraction (Gemini + OpenAI)
  - Removes markdown/code fences from model output
  - Returns normalized dict: { ok, text, model, raw, error_code (optional) }
"""

from __future__ import annotations
import os
import json
import re
import time
from typing import Any, Dict, Optional
import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------
# Load .env configuration
# ---------------------------------------------------------------------
load_dotenv()

LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_API_URL = os.getenv(
    "LLM_API_URL",
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
).strip()
LLM_MODEL_DEFAULT = os.getenv("LLM_MODEL", "gemini-2.5-flash")
MOCK_MODE = os.getenv("LLM_MOCK_MODE", "false").lower() in ("1", "true", "yes")
DEFAULT_TIMEOUT = int(os.getenv("LLM_TIMEOUT_SEC", "60"))


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _strip_code_fences(s: str) -> str:
    """Remove Markdown / triple-backtick code fences and surrounding whitespace."""
    if not isinstance(s, str):
        s = str(s)
    s = re.sub(r"```(?:\w+)?\n?", "", s)
    s = re.sub(r"\n?```", "", s)
    return s.strip()


def _extract_text_from_response(data: Dict[str, Any]) -> str:
    """Extract text from Gemini or OpenAI responses."""
    try:
        # Gemini candidate-based structure
        if "candidates" in data and len(data["candidates"]) > 0:
            candidate = data["candidates"][0]
            parts = candidate.get("content", {}).get("parts", [])
            if parts:
                first = parts[0]
                if isinstance(first, dict):
                    return first.get("text", "").strip()
                return str(first).strip()
        # OpenAI chat completions
        if "choices" in data and data["choices"]:
            choice = data["choices"][0]
            msg = choice.get("message") or {}
            if isinstance(msg, dict):
                return (msg.get("content") or msg.get("text") or "").strip()
            return choice.get("text", "").strip()
    except Exception:
        pass
    try:
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        return str(data)


# ---------------------------------------------------------------------
# Core client
# ---------------------------------------------------------------------
def call_llm(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 512,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    system_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send a prompt to the configured LLM endpoint and return a normalized response.

    Returns:
      {
        "ok": bool,
        "text": <cleaned text or "" on failure>,
        "model": <model used>,
        "raw": <raw JSON>,
        "error_code": <HTTP code> (optional)
      }
    """
    model = model or LLM_MODEL_DEFAULT

    # -----------------------------------------------------------------
    # 1️⃣ MOCK mode (offline or missing API key)
    # -----------------------------------------------------------------
    if MOCK_MODE or not LLM_API_KEY:
        mock_text = f"[MOCK RESPONSE] Model {model} received {len(prompt)} characters."
        return {"ok": True, "text": mock_text, "model": model, "raw": {"mock": True}}

    is_gemini = "generativelanguage.googleapis.com" in (LLM_API_URL or "")

    # -----------------------------------------------------------------
    # 2️⃣ Gemini Payload Format (✅ Official Spec)
    # -----------------------------------------------------------------
    if is_gemini:
        endpoint = LLM_API_URL  # No ?key= anymore
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": LLM_API_KEY,  # Required header auth
        }
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

    # -----------------------------------------------------------------
    # 3️⃣ OpenAI-compatible fallback
    # -----------------------------------------------------------------
    else:
        endpoint = LLM_API_URL
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LLM_API_KEY}",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt or "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

    # -----------------------------------------------------------------
    # 4️⃣ Execute Request with Retries
    # -----------------------------------------------------------------
    attempt = 0
    while attempt <= max_retries:
        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            text = _extract_text_from_response(data)
            text = _strip_code_fences(text)
            return {"ok": True, "text": text, "model": model, "raw": data}

        except requests.HTTPError as http_err:
            status = getattr(http_err.response, "status_code", None)
            # Retry on transient errors
            if status in (429, 500, 502, 503, 504) and attempt < max_retries:
                time.sleep(backoff_factor ** attempt)
                attempt += 1
                continue
            err_text = f"[HTTP {status}] {str(http_err)}"
            return {"ok": False, "text": err_text, "model": model, "raw": {}, "error_code": status}

        except requests.RequestException as req_err:
            if attempt < max_retries:
                time.sleep(backoff_factor ** attempt)
                attempt += 1
                continue
            return {"ok": False, "text": f"[REQUEST ERROR] {str(req_err)}", "model": model, "raw": {}}

        except Exception as e:
            return {"ok": False, "text": f"[ERROR] {str(e)}", "model": model, "raw": {}}

    return {"ok": False, "text": "[ERROR] retries exhausted", "model": model, "raw": {}}


# ---------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------
if __name__ == "__main__":
    sample_prompt = "Summarize this anonymized report: A customer lost their credit card and requested replacement."
    response = call_llm(prompt=sample_prompt)
    print(json.dumps(response, indent=2, ensure_ascii=False))
