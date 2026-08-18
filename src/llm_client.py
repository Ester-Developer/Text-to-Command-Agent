"""Thin wrapper around the Google Gemini API (free tier) used by the converter."""

import logging
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

logging.getLogger("google_genai.models").setLevel(logging.ERROR)

_DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

_client = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Copy .env.example to .env and add your free key "
                "from https://aistudio.google.com/apikey"
            )
        _client = genai.Client(api_key=api_key)
    return _client


def complete(prompt: str, model: str = None, max_tokens: int = 500, temperature: float = 0.0) -> str:
    """Send a single-turn prompt and return the raw text response."""
    client = get_client()
    response = client.models.generate_content(
        model=model or _DEFAULT_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
        ),
    )
    return (response.text or "").strip()
