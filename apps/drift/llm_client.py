"""
LLM Client for Groq API integration with mock fallback.
"""
import os
from typing import Optional

try:
    from groq import Groq
    GROQ_SDK_AVAILABLE = True
except ImportError:
    GROQ_SDK_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_SDK_AVAILABLE = True
except ImportError:
    OPENAI_SDK_AVAILABLE = False


class GroqClient:
    """Client for interacting with Groq LLM API."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.3-70b-versatile"):
        """
        Initialize Groq client.
        
        Args:
            api_key: Groq API key
            model: Model to use (default: llama-3.3-70b-versatile)
        """
        self.api_key = api_key
        self.model = model
        self.mock_mode = False
        self.provider = None
        
        if not api_key:
            self.mock_mode = True
            self.client = None
            print("Running in MOCK mode (no API key provided)")
        elif GROQ_SDK_AVAILABLE:
            self.client = Groq(api_key=self.api_key)
            self.provider = "groq-sdk"
            print("Running in API mode with Groq SDK")
            print(f"   Model: {self.model}")
            print(f"   API Key: {self.api_key[:12]}...{self.api_key[-4:]}")
        elif OPENAI_SDK_AVAILABLE:
            self.client = OpenAI(api_key=self.api_key, base_url="https://api.groq.com/openai/v1")
            self.provider = "openai-sdk"
            print("Running in API mode with OpenAI SDK (Groq endpoint)")
            print(f"   Model: {self.model}")
            print(f"   API Key: {self.api_key[:12]}...{self.api_key[-4:]}")
        else:
            self.mock_mode = True
            self.client = None
            print("Running in MOCK mode (neither groq nor openai package is installed)")
    
    def generate_response(self, prompt: str) -> str:
        """
        Generate LLM response for given prompt.
        
        Args:
            prompt: Input prompt text
            
        Returns:
            LLM generated response
        """
        if self.mock_mode:
            return self._mock_response(prompt)
        
        try:
            return self._call_groq_api(prompt)
        except Exception as e:
            print(f"Error calling Groq API: {e}")
            print("Falling back to mock response...")
            return self._mock_response(prompt)
    
    def _call_groq_api(self, prompt: str) -> str:
        """
        Call actual Groq API.
        
        Args:
            prompt: Input prompt text
            
        Returns:
            API response text
        """
        print(f"\nCalling Groq API...")
        print(f"   Model: {self.model}")
        print(f"   Prompt length: {len(prompt)} chars")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant. Respond naturally to the user's message."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=1024
            )
            
            generated_text = response.choices[0].message.content
            print(f"Generated text length: {len(generated_text)} chars")
            return generated_text
            
        except Exception as e:
            print(f"API call failed: {str(e)}")
            raise
    
    def _mock_response(self, prompt: str) -> str:
        """
        Generate mock LLM response for testing.
        
        Args:
            prompt: Input prompt text
            
        Returns:
            Mock response text
        """
        # Simple mock that echoes back with some context
        word_count = len(prompt.split())
        
        response = f"""[MOCK LLM RESPONSE]

I received your message with {word_count} words. 

Here's my response based on the anonymized input:

Thank you for your message. I understand you've shared some information with me. 
I can see references to various entities and details in your text. 

If this were a real LLM interaction, I would provide a thoughtful response 
based on the content you've shared, while being mindful that some information 
has been anonymized for privacy protection.

Is there anything specific you'd like me to help you with regarding this information?

[This is a mock response. Configure GROQ_API_KEY in .env for real LLM integration]
"""
        return response
