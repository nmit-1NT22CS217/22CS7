"""
core/llm_client.py

Zero-Trust LLM Client for Secure AI Pipelines.

Design principles:
- LLM is treated as UNTRUSTED
- LLM never receives raw PII
- System prompts are fixed and non-overridable
- Role is passed only as context, never authority
- Safe fallback to mock mode
"""

import os
from typing import Optional

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("Groq library not installed. Run: pip install groq")


class GroqClient:
    """
    Client for interacting with Groq LLM API
    under a zero-trust security model.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "llama-3.3-70b-versatile"
    ):
        self.api_key = api_key
        self.model = model

        self.mock_mode = not (api_key and GROQ_AVAILABLE)

        if self.mock_mode:
            self.client = None
            if not GROQ_AVAILABLE:
                print("⚠ Groq library not available → MOCK mode")
            else:
                print("⚠ GROQ_API_KEY not set → MOCK mode")
        else:
            self.client = Groq(api_key=self.api_key)
            print("✅ Groq API initialized")
            print(f"   Model: {self.model}")

    # =========================================================
    # PUBLIC API
    # =========================================================
    def generate_response(self, sanitized_prompt: str, role: str) -> str:
        """
        Generate LLM response.

        IMPORTANT:
        - Input MUST be sanitized before calling this method
        - Role is informational only
        """

        if not sanitized_prompt or not sanitized_prompt.strip():
            return "⚠ Empty prompt after sanitization."

        if self.mock_mode:
            return self._mock_response(sanitized_prompt, role)

        try:
            return self._call_groq_api(sanitized_prompt, role)
        except Exception as e:
            print(f"❌ Groq API error: {e}")
            print("⚠ Falling back to mock response")
            return self._mock_response(sanitized_prompt, role)

    # =========================================================
    # INTERNAL API CALL
    # =========================================================
    def _call_groq_api(self, sanitized_prompt: str, role: str) -> str:
        """
        Call Groq API with a fixed system prompt.
        """

        print("\n🔒 Calling Groq API (zero-trust)")
        print(f"   Prompt length: {len(sanitized_prompt)} chars")
        print(f"   Role context: {role}")

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    # 🔒 FIXED SYSTEM PROMPT
                    "role": "system",
                    "content": (
                        "You are a helpful assistant operating in a secure environment. "
                        "Some sensitive information may be anonymized or replaced with placeholders. "
                        "Do NOT attempt to infer, reconstruct, or guess any hidden data. "
                        "Respond only based on the visible content."
                    )
                },
                {
                    "role": "user",
                    "content": sanitized_prompt
                }
            ],
            temperature=0.7,
            max_tokens=1024
        )

        generated_text = response.choices[0].message.content.strip()

        print(f"✅ Response generated ({len(generated_text)} chars)")
        return generated_text

    # =========================================================
    # MOCK MODE (SAFE FALLBACK)
    # =========================================================
    def _mock_response(self, sanitized_prompt: str, role: str) -> str:
        """
        Deterministic mock response for development/testing.
        """

        word_count = len(sanitized_prompt.split())

        return (
            "[MOCK LLM RESPONSE]\n\n"
            f"Role context: {role}\n"
            f"Input length: {word_count} words\n\n"
            "The message was processed in a secure, anonymized form.\n"
            "Sensitive information (if any) was protected before reaching the model.\n\n"
            "This is a mock response used for local development.\n"
            "Set GROQ_API_KEY in your environment to enable real LLM calls."
        )


# =========================================================
# SINGLETON FACTORY (USED BY anonymizer.py)
# =========================================================
def call_llm(prompt: str, role: str) -> str:
    """
    Stateless helper used by the AI orchestrator.
    """

    client = GroqClient(
        api_key=os.getenv("GROQ_API_KEY"),
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    )

    return client.generate_response(prompt, role)
