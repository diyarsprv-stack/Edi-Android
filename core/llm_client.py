from __future__ import annotations

import json
import os
from pathlib import Path

try:
    from google import genai
    HAS_GEMINI = True
except Exception:
    HAS_GEMINI = False

BASE_DIR    = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
_DEFAULT_MODEL = "gemini-2.0-flash"


def _load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_llm_settings() -> tuple[str, str]:
    return "gemini", _DEFAULT_MODEL


def get_llm_provider() -> str:
    return "gemini"


def ensure_ollama_running(timeout: int = 15) -> bool:
    return True


def warmup_model(system_prompt: str | None = None) -> bool:
    return True


def check_model_available(log=None) -> bool:
    return True


def call_llm(messages: list, tools: list | None = None, timeout: int = 120) -> dict:
    return {"content": "", "tool_calls": []}


def call_llm_text(
    prompt: str,
    system: str | None = None,
    model: str | None = None,
    timeout: int = 120,
) -> str:
    if not HAS_GEMINI:
        return "Error: Gemini client not available."
    try:
        cfg = _load_config()
        api_key = cfg.get("gemini_api_key", "")
        if not api_key:
            return "Error: No Gemini API key configured."
        client = genai.Client(api_key=api_key)
        parts = []
        if system:
            parts.append(system + "\n\n")
        parts.append(prompt)
        resp = client.models.generate_content(
            model=model or _DEFAULT_MODEL,
            contents="".join(parts),
        )
        return resp.text.strip()
    except Exception as e:
        return f"Error: {e}"


def call_llm_stream(messages: list, tools: list | None = None, timeout: int = 120):
    yield {"type": "done", "content": "", "tool_calls": []}
