"""
llm_client.py
-------------
Unified interface for calling Large Language Models (LLMs).
Now fully supports:
  ✅ Gemini 1.5 Flash / Pro (Google API)
  ✅ OpenAI-compatible APIs
  ✅ Mock mode for offline testing
"""

from __future__ import annotations
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import requests
from typing import Any, Dict
from dotenv import load_dotenv

# -------------------------------------------------------------------------
# Load environment variables
# -------------------------------------------------------------------------
load_dotenv()

LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_API_URL = os.getenv("LLM_API_URL", "").strip()
LLM_MODEL_DEFAULT = os.getenv("LLM_MODEL", "gemini-1.5-flash")
MOCK_MODE = os.getenv("LLM_MOCK_MODE", "false").lower() in ("1", "true", "yes")

# -------------------------------------------------------------------------
# Core Function
# -------------------------------------------------------------------------
def call_llm(
    prompt: str,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 512,
    system_prompt: str | None = None
) -> Dict[str, Any]:
    """
    Sends a prompt to the configured LLM (Gemini or OpenAI-compatible).

    Args:
        prompt: Text prompt for the LLM.
        model: Optional model override.
        temperature: Randomness of generation.
        max_tokens: Maximum output length.
        system_prompt: Optional instruction (ignored by Gemini).

    Returns:
        dict: {
          "ok": bool,
          "text": str,
          "model": str,
          "raw": dict
        }
    """
    model = model or LLM_MODEL_DEFAULT

    # ---------------------------------------------------------------------
    # 1️⃣ Mock Mode (offline or missing API key)
    # ---------------------------------------------------------------------
    if MOCK_MODE or not LLM_API_KEY:
        mock_text = f"[MOCK RESPONSE] Model {model} received {len(prompt)} characters."
        return {"ok": True, "text": mock_text, "model": model, "raw": {"mock": True}}

    try:
        headers = {"Content-Type": "application/json"}

        # -----------------------------------------------------------------
        # 2️⃣ Gemini API (Google Generative Language)
        # -----------------------------------------------------------------
        if "generativelanguage.googleapis.com" in LLM_API_URL:
            endpoint = f"{LLM_API_URL}?key={LLM_API_KEY}"
            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}
            }

            resp = requests.post(endpoint, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            text = ""
            if "candidates" in data and len(data["candidates"]) > 0:
                parts = data["candidates"][0].get("content", {}).get("parts", [])
                if parts and "text" in parts[0]:
                    text = parts[0]["text"]

            return {"ok": True, "text": text.strip(), "model": model, "raw": data}

        # -----------------------------------------------------------------
        # 3️⃣ OpenAI-style API (fallback)
        # -----------------------------------------------------------------
        else:
            headers["Authorization"] = f"Bearer {LLM_API_KEY}"
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt or "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": temperature
            }

            resp = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            text = ""
            if "choices" in data and len(data["choices"]) > 0:
                choice = data["choices"][0]
                text = (
                    choice.get("message", {}).get("content")
                    or choice.get("text")
                    or ""
                )

            return {"ok": True, "text": text.strip(), "model": model, "raw": data}

    except Exception as e:
        return {"ok": False, "text": f"[ERROR] {str(e)}", "model": model, "raw": {}}


# -------------------------------------------------------------------------
# Self-test (standalone mode)
# -------------------------------------------------------------------------
if __name__ == "__main__":
    prompt = "Summarize: A user reported a lost credit card and requested replacement."
    response = call_llm(prompt=prompt)
    print(json.dumps(response, indent=2, ensure_ascii=False))
