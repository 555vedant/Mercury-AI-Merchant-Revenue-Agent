"""Google Gemini implementation used by AgenticPay."""
import os
import sys
import threading
import time
from typing import Any, Optional

try:
    from dotenv import load_dotenv
    from google import genai
    from google.genai import errors, types
except ImportError as error:
    raise ImportError(
        "Gemini support requires the project dependencies. Install them with: "
        f'"{sys.executable}" -m pip install -r requirements.txt'
    ) from error

from agenticpay.models.base_llm import BaseLLM

load_dotenv()


class GeminiLLM(BaseLLM):
    """Gemini text model with conservative free-tier request pacing."""

    def __init__(self, model: str = "gemini-3.6-flash", api_key: Optional[str] = None, min_request_interval: float = 13.0):
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required. Add it to .env or set it in your environment.")
        self.model = model
        self.client = genai.Client(api_key=api_key)
        self.min_request_interval = min_request_interval
        self._last_request_at = 0.0
        self._request_lock = threading.Lock()

    def generate(self, prompt: str, temperature: float = 0.0, max_tokens: Optional[int] = None, **kwargs: Any) -> str:
        config_values = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
            **kwargs,
        }
        with self._request_lock:
            wait_seconds = self.min_request_interval - (time.monotonic() - self._last_request_at)
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(**config_values),
                )
            except errors.ClientError as error:
                if error.code == 429:
                    raise RuntimeError(
                        "Gemini quota is exhausted. Wait for the quota window to reset or enable billing; "
                        "the client is already pacing requests at one every 13 seconds."
                    ) from error
                raise
            finally:
                self._last_request_at = time.monotonic()
        if not response.text:
            raise RuntimeError("Gemini returned no text response.")
        return response.text

    def __repr__(self) -> str:
        return f"GeminiLLM(model={self.model!r})"
