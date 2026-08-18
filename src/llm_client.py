"""Thin wrapper around the Anthropic API used by the converter."""

import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

_DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

_client = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def complete(prompt: str, model: str = None, max_tokens: int = 500, temperature: float = 0.0) -> str:
    """Send a single-turn prompt and return the raw text response."""
    client = get_client()
    response = client.messages.create(
        model=model or _DEFAULT_MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
    return "".join(parts).strip()
