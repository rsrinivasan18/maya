"""
MAYA Configuration Settings
============================
Loads environment variables from .env and exposes them as a typed Settings object.

Usage:
    from src.maya.config.settings import settings
    print(settings.OFFLINE_MODE)

IMPORTANT: Never hardcode API keys. Always read from environment.
           Real keys go in .env (git-ignored). Placeholders go in .env.example.
"""

import os
from dotenv import load_dotenv

# Load .env file if it exists (safe to call even if file is missing)
load_dotenv()


class Settings:
    """Central configuration for all MAYA components."""

    # ── LangSmith Observability ───────────────────────────────────────────────
    LANGCHAIN_TRACING_V2: bool = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    LANGCHAIN_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "maya-assistant")
    # Note: LANGCHAIN_API_KEY is read automatically by LangChain from environment

    # ── Online LLM APIs (Week 3) ──────────────────────────────────────────────
    # Keys are read from env only - never stored as strings in code
    HAS_ANTHROPIC_KEY: bool = bool(os.getenv("ANTHROPIC_API_KEY", ""))
    HAS_SARVAM_KEY: bool = bool(os.getenv("SARVAM_API_KEY", ""))

    # ── Ollama Local LLM ──────────────────────────────────────────────────────
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "sarvam2b:4bit")

    # ── MAYA Behaviour ────────────────────────────────────────────────────────
    OFFLINE_MODE: bool = os.getenv("MAYA_OFFLINE_MODE", "false").lower() == "true"
    LANGUAGE: str = os.getenv("MAYA_LANGUAGE", "hinglish")
    LOG_LEVEL: str = os.getenv("MAYA_LOG_LEVEL", "INFO")

    def summary(self) -> str:
        """Human-readable config summary (safe to print - no secret values)."""
        return (
            f"MAYA Config | "
            f"offline={self.OFFLINE_MODE} | "
            f"language={self.LANGUAGE} | "
            f"tracing={self.LANGCHAIN_TRACING_V2} | "
            f"anthropic_key={'yes' if self.HAS_ANTHROPIC_KEY else 'no'} | "
            f"sarvam_key={'yes' if self.HAS_SARVAM_KEY else 'no'}"
        )


# Singleton - import this everywhere
settings = Settings()
