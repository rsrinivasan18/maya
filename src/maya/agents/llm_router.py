"""
MAYA LLM Router - Session 11 (LiteLLM refactor)
=================================================
Tiered LLM fallback chain using LiteLLM as a unified interface.

Tier order (online):   Sarvam API → Claude API → OpenAI API → Ollama
Tier order (offline):  Ollama directly (no wasted network calls)

Each tier:
  - Only tried if the API key is present (settings.HAS_*_KEY)
  - If it raises ANY exception, silently falls to the next tier
  - Uses litellm.completion() — identical call and response shape for every provider

Returns (response_text, provider_label) so callers can log which tier was used.

LEARNING NOTES for Srinivasan:
--------------------------------
Why LiteLLM?
  Before Session 11, every provider needed its own code:
    - Sarvam:    urllib.request + json parsing
    - Claude:    anthropic client, separate system/chat message split
    - OpenAI:    openai client, result.choices[0].message.content
    - Ollama:    ollama.chat(), result.message.content (dict!)

  Each one had a different response shape and error type.
  Adding a 5th provider meant writing a 5th code path.

  LiteLLM wraps all 100+ providers under ONE call:
    response = litellm.completion(model="...", messages=messages)
    text = response.choices[0].message.content    ← identical every time

  Adding a new provider = ONE new line in _TIERS_ONLINE. That's it.

Why keep the same function signature (call_llm_tiered)?
  All graph nodes call call_llm_tiered(messages, is_online).
  Keeping the signature identical means ZERO changes outside this file.
  Tests still pass without modification — clean refactor.

Sarvam model string:
  "openai/sarvam-m" — LiteLLM's OpenAI-compatible custom endpoint pattern.
  Sarvam's REST API follows the OpenAI spec, so LiteLLM treats it as a
  custom OpenAI deployment. We pass api_base and extra_headers for auth.

Ollama model string:
  "ollama/llama3.2:3b" — LiteLLM connects to localhost:11434/v1 automatically.
  No ollama Python package import needed (LiteLLM uses HTTP directly).
"""

import os
import litellm

from src.maya.config.settings import settings

# Silence LiteLLM's verbose startup and per-call logging
litellm.suppress_debug_info = True
litellm.set_verbose = False


# ── Tier definitions ───────────────────────────────────────────────────────────
# Each entry: (provider_label, litellm_model_string, extra_kwargs)
# Online tiers tried in order; first success wins.

_SARVAM_KEY = os.getenv("SARVAM_API_KEY", "")

_TIERS_ONLINE: list[tuple[str, str, dict]] = [
    # Tier 1 — Sarvam: best Hindi/Hinglish quality, built for Indian languages
    (
        "sarvam",
        "openai/sarvam-m",
        {
            "api_base": "https://api.sarvam.ai/v1",
            "api_key": _SARVAM_KEY,
            "extra_headers": {"api-subscription-key": _SARVAM_KEY},
        },
    ),
    # Tier 2 — Claude: high quality, excellent at explanations and reasoning
    (
        "claude",
        "anthropic/claude-haiku-4-5-20251001",
        {},
    ),
    # Tier 3 — OpenAI: wide availability, cost-effective (gpt-4o-mini)
    (
        "openai",
        "openai/gpt-4o-mini",
        {},
    ),
]

# Tier 4 — Ollama: always the final fallback; free, local, offline-capable
_TIER_OLLAMA: tuple[str, str, dict] = ("ollama", "ollama/llama3.2:3b", {})


# ── Key availability check ─────────────────────────────────────────────────────

def _key_available(label: str) -> bool:
    """Return True if the API key for this tier is present in settings."""
    return {
        "sarvam": settings.HAS_SARVAM_KEY,
        "claude": settings.HAS_ANTHROPIC_KEY,
        "openai": settings.HAS_OPENAI_KEY,
        "ollama": True,  # Ollama needs no key
    }.get(label, False)


# ── Public API ─────────────────────────────────────────────────────────────────

def call_llm_tiered(
    messages: list[dict],
    is_online: bool,
    fallback_error_prefix: str = "MAYA",
    force_provider: str | None = None,
) -> tuple[str, str]:
    """
    Call the best available LLM, falling back down the tier chain on any error.

    Args:
        messages:              Full message list including system prompt.
                               Format: [{"role": "system"|"user"|"assistant", "content": str}, ...]
        is_online:             True if internet is reachable (from check_connectivity node).
        fallback_error_prefix: Label for the final error message (e.g. "MAYA Math Tutor").
        force_provider:        Optional override from the web UI model selector.
                               If set (and not "auto"), skip directly to that provider,
                               then fall back to Ollama on failure.
                               Values: "sarvam"|"claude"|"openai"|"ollama"|None|"auto"

    Returns:
        (response_text, provider_label)
        provider_label is one of: "sarvam" | "claude" | "openai" | "ollama" | "error"
    """
    # Build tier list
    if force_provider and force_provider != "auto":
        # Force a specific provider; Ollama is always the safety-net fallback
        all_tiers = _TIERS_ONLINE + [_TIER_OLLAMA]
        forced = [t for t in all_tiers if t[0] == force_provider]
        tiers = forced + [_TIER_OLLAMA]
    else:
        # Auto mode: online providers first (if online), then Ollama always last
        tiers = (_TIERS_ONLINE if is_online else []) + [_TIER_OLLAMA]

    for label, model, kwargs in tiers:
        if not _key_available(label):
            continue  # Skip tiers without keys (e.g. no ANTHROPIC_API_KEY set)
        try:
            response = litellm.completion(
                model=model,
                messages=messages,
                max_tokens=300,
                timeout=15,
                **kwargs,
            )
            text = response.choices[0].message.content or ""
            return text.strip(), label
        except Exception:
            continue  # Silent fallback — try next tier

    # All tiers exhausted (shouldn't happen if Ollama is running)
    return (
        f"Hmm, {fallback_error_prefix} is having trouble thinking right now! "
        "Make sure Ollama is running: ollama serve."
    ), "error"
