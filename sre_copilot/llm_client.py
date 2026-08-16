"""Provider-agnostic LLM access layer for sre-copilot.

Every agent in every cycle calls generate(...) from this module and never
talks to a provider SDK directly. Switching models later is a config change
(LLM_PROVIDER env var), not a rewrite.

Implemented : ollama (local, primary)
Stubbed     : gemini, glm (ready branches, not implemented yet)
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional, Type, TypeVar, Union

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

load_dotenv()

T = TypeVar("T", bound=BaseModel)

OLLAMA_TIMEOUT_S = 120


class LLMProviderError(RuntimeError):
    """Raised when the selected provider is misconfigured or unreachable."""


# ---------------------------------------------------------------- providers

def _call_ollama(prompt: str) -> str:
    base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "gemma3:4b")
    resp = requests.post(
        f"{base}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False, "format": "json"},
        timeout=OLLAMA_TIMEOUT_S,
    )
    resp.raise_for_status()
    return resp.json().get("response", "")


def _call_gemini(prompt: str) -> str:
    raise LLMProviderError(
        "LLM_PROVIDER=gemini selected but the Gemini branch is a stub. "
        "Add GEMINI_API_KEY to .env and implement _call_gemini()."
    )


def _call_glm(prompt: str) -> str:
    raise LLMProviderError(
        "LLM_PROVIDER=glm selected but the GLM branch is a stub. "
        "Add GLM_API_KEY to .env and implement _call_glm()."
    )


def _raw_generate(prompt: str) -> str:
    provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
    if provider == "ollama":
        return _call_ollama(prompt)
    if provider == "gemini":
        return _call_gemini(prompt)
    if provider == "glm":
        return _call_glm(prompt)
    raise LLMProviderError(f"Unknown LLM_PROVIDER: {provider!r}")


# ------------------------------------------------------------- json parsing

def _extract_json(text: str) -> Optional[dict]:
    """Direct parse first, then regex-based JSON-substring extraction."""
    text = (text or "").strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


# --------------------------------------------------------------- public API

def generate(prompt: str, schema: Optional[Type[T]] = None) -> Union[T, str]:
    """Generate a completion, optionally validated against a Pydantic schema.

    Retry / fallback contract (deliberate architecture decision):
      1. Ask for JSON matching `schema` (few-shot examples live in the prompt).
      2. Parse; on failure try regex JSON-substring extraction.
      3. If still invalid, retry ONCE with an explicit correction prompt.
      4. If still invalid, return the schema's safe defaults instead of
         crashing (satisfies 'recover from tool failure without crashing').
    """
    if schema is None:
        return _raw_generate(prompt)

    json_instruction = (
        "\n\nReturn ONLY valid JSON matching this schema, no prose:\n"
        + json.dumps(schema.model_json_schema(), indent=2)
    )

    last_raw = ""
    for attempt in (1, 2):
        if attempt == 1:
            full_prompt = prompt + json_instruction
        else:
            full_prompt = (
                "Your last output was invalid JSON.\n"
                f"Last output:\n{last_raw[:500]}\n\n"
                + prompt
                + json_instruction
                + "\nReturn ONLY valid JSON matching this schema."
            )
        try:
            last_raw = _raw_generate(full_prompt)
        except (LLMProviderError, requests.RequestException) as exc:
            print(f"[llm_client] provider error on attempt {attempt}: {exc}")
            break

        parsed = _extract_json(last_raw)
        if parsed is not None:
            try:
                return schema.model_validate(parsed)
            except ValidationError:
                continue

    print("[llm_client] using safe-default fallback after failed retries")
    return schema()