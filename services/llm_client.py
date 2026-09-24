import json
import os
import requests
from typing import Optional, List, Dict, Any

_client = None
_cached_key = None

SARVAM_COMPLETIONS_URL = "https://api.sarvam.ai/v1/chat/completions"
DEFAULT_SARVAM_MODEL = "sarvam-105b"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"


def _load_env_file() -> None:
    """Load key-value pairs from .env in the project root."""
    try:
        import env_loader
        env_loader.load_env()
    except Exception:
        pass


def _call_sarvam(
    api_key: str,
    system_prompt: str,
    messages: list,
    max_tokens: int = 1024,
    model: Optional[str] = None,
) -> str:
    chosen_model = model or os.environ.get("SARVAM_MODEL") or DEFAULT_SARVAM_MODEL
    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    headers = {
        "api-subscription-key": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": chosen_model,
        "messages": full_messages,
        "max_tokens": max_tokens,
        "temperature": 0.3,
        # Disable reasoning so the model puts its answer directly in "content"
        # rather than returning content=null with a separate reasoning_content field.
        "reasoning_effort": None,
    }

    try:
        res = requests.post(SARVAM_COMPLETIONS_URL, headers=headers, json=payload, timeout=90)
    except Exception as e:
        raise RuntimeError(f"Sarvam AI network request failed: {e}") from e

    if res.status_code != 200:
        err_detail = res.text
        try:
            err_json = res.json()
            if isinstance(err_json, dict):
                err_detail = err_json.get("error") or err_json.get("message") or res.text
        except Exception:
            pass
        raise RuntimeError(f"Sarvam AI API error (HTTP {res.status_code}): {err_detail}")

    try:
        data = res.json()
    except Exception as e:
        raise RuntimeError(f"Sarvam AI returned non-JSON response: {res.text[:500]}") from e

    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError(f"Sarvam AI returned empty choices: {json.dumps(data)[:500]}")

    msg = choices[0].get("message", {})

    # Primary: standard "content" field
    content = msg.get("content")

    # Fallback 1: some reasoning models put text in "reasoning_content"
    if not content:
        content = msg.get("reasoning_content")

    # Fallback 2: check for a top-level "text" field (rare)
    if not content:
        content = msg.get("text")

    # Fallback 3: check delta in streaming-style responses
    if not content:
        delta = choices[0].get("delta", {})
        content = delta.get("content") or delta.get("reasoning_content")

    if not content:
        raise RuntimeError(
            f"Sarvam AI returned an empty response. "
            f"Raw message object: {json.dumps(msg)[:500]}"
        )

    return content


def _call_anthropic(
    api_key: str,
    system_prompt: str,
    messages: list,
    max_tokens: int = 1024,
    model: Optional[str] = None,
) -> str:
    global _client, _cached_key
    from anthropic import Anthropic

    chosen_model = model or DEFAULT_ANTHROPIC_MODEL
    if _client is None or _cached_key != api_key:
        _client = Anthropic(api_key=api_key)
        _cached_key = api_key
    try:
        response = _client.messages.create(
            model=chosen_model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        )
        return "".join(block.text for block in response.content if block.type == "text")
    except Exception as e:
        raise RuntimeError(f"Anthropic LLM call failed: {e}") from e


def get_client():
    """Backward compatibility helper for Anthropic client."""
    global _client, _cached_key
    _load_env_file()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if api_key and not api_key.startswith("your_"):
        from anthropic import Anthropic
        if _client is None or _cached_key != api_key:
            _client = Anthropic(api_key=api_key)
            _cached_key = api_key
        return _client
    return None


def call_llm(system_prompt: str, messages: list, max_tokens: int = 1024, model: Optional[str] = None) -> str:
    """
    Unified entrypoint for LLM completions.
    Supports Sarvam AI (primary) and Anthropic Claude.
    Raises RuntimeError on API failure or missing keys so callers return HTTP 502.
    """
    _load_env_file()

    sarvam_key = (
        os.environ.get("SARVAM_API_KEY", "").strip()
        or os.environ.get("SARVAMAI_API_KEY", "").strip()
    )
    if sarvam_key and not sarvam_key.startswith("your_"):
        return _call_sarvam(sarvam_key, system_prompt, messages, max_tokens=max_tokens, model=model)

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if anthropic_key and not anthropic_key.startswith("your_"):
        return _call_anthropic(anthropic_key, system_prompt, messages, max_tokens=max_tokens, model=model)

    raise RuntimeError(
        "No AI API key found. Please set SARVAM_API_KEY in your .env file."
    )
