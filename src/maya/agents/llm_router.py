"""
MAYA LLM Router - Session 8 Step 3
=====================================
Tiered LLM fallback chain for online/offline routing.

Tier order (online):   Sarvam API → Claude API → OpenAI API → Ollama
Tier order (offline):  Ollama directly (no wasted network calls)

Each tier:
  - Only tried if the API key is present (settings.HAS_*_KEY)
  - If it raises ANY exception, silently falls to the next tier
  - Uses lazy imports — if a package is not installed, that tier is skipped

Returns (response_text, provider_label) so callers can log which tier was used.

LEARNING NOTES for Srinivasan:
--------------------------------
Why tiered fallback?
  Sarvam is best for Hindi/Hinglish — built specifically for Indian languages.
  Claude and OpenAI are high quality but cost per token.
  Ollama is free, local, offline-capable. Together they ensure Srinika
  ALWAYS gets an answer — even if every API is down.

Why lazy imports (import inside try blocks)?
  - anthropic and openai are optional packages
  - If they're not installed, the ImportError is caught and we skip that tier
  - No hard crash — graceful degradation

Why urllib.request for Sarvam (not requests)?
  - urllib is Python built-in — zero new dependencies for the Sarvam tier
  - We're just sending a JSON POST — urllib handles it fine

Why return (text, provider)?
  - The caller logs it in steps: "[help_response/claude]"
  - Visible in --debug trace so you can see which tier MAYA actually used
  - Useful for learning, debugging, and cost tracking
"""

import json
import os
import urllib.request

from src.maya.config.settings import settings


def call_llm_tiered(
    messages: list[dict],
    is_online: bool,
    fallback_error_prefix: str = "MAYA",
) -> tuple[str, str]:
    """
    Call the best available LLM, falling back down the tier chain on any error.

    Args:
        messages: Full message list including system prompt.
                  Format: [{"role": "system"|"user"|"assistant", "content": str}, ...]
        is_online: True if internet is reachable (from check_connectivity node in state).
        fallback_error_prefix: Label for the final error message (e.g. "MAYA Math Tutor").

    Returns:
        (response_text, provider_label)
        provider_label is one of: "sarvam" | "claude" | "openai" | "ollama" | "error"
    """
    if is_online:
        # ── Tier 1: Sarvam API ─────────────────────────────────────────────────
        # Best Hindi/Hinglish quality — built for Indian languages
        if settings.HAS_SARVAM_KEY:
            try:
                sarvam_key = os.getenv("SARVAM_API_KEY", "")
                payload = json.dumps(
                    {"model": "sarvam-m", "messages": messages}
                ).encode("utf-8")
                req = urllib.request.Request(
                    "https://api.sarvam.ai/v1/chat/completions",
                    data=payload,
                    headers={
                        "api-subscription-key": sarvam_key,
                        "Content-Type": "application/json",
                    },
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip(), "sarvam"
            except Exception:
                pass  # Fall through to Claude

        # ── Tier 2: Claude API ─────────────────────────────────────────────────
        # High quality, fast, excellent at explanations and reasoning
        if settings.HAS_ANTHROPIC_KEY:
            try:
                import anthropic as _anthropic

                # Claude separates the system prompt from the chat messages list
                system_content = " ".join(
                    m["content"] for m in messages if m["role"] == "system"
                )
                chat_msgs = [m for m in messages if m["role"] != "system"]

                client = _anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
                result = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=300,
                    system=system_content,
                    messages=chat_msgs,
                )
                return result.content[0].text.strip(), "claude"
            except Exception:
                pass  # Fall through to OpenAI

        # ── Tier 3: OpenAI API ─────────────────────────────────────────────────
        # Wide availability, cost-effective (gpt-4o-mini)
        if settings.HAS_OPENAI_KEY:
            try:
                import openai as _openai

                client = _openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
                result = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    max_tokens=300,
                )
                return result.choices[0].message.content.strip(), "openai"
            except Exception:
                pass  # Fall through to Ollama

    # ── Tier 4: Ollama — always the final fallback ─────────────────────────────
    # Free, local, offline-capable. Works as long as `ollama serve` is running.
    try:
        import ollama as _ollama

        result = _ollama.chat(model="llama3.2:3b", messages=messages)
        return result.message.content.strip(), "ollama"
    except Exception as e:
        return (
            f"Hmm, {fallback_error_prefix} is having trouble thinking right now! "
            "Make sure Ollama is running: ollama serve. "
            f"({e})"
        ), "error"
