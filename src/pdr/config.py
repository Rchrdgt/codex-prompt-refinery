"""Configuration and provider clients.

Loads .env, exposes settings, and returns OpenAI-compatible clients for
embeddings and LLM calls (OpenAI or Cerebras).

Cerebras uses OpenAI-compatible base_url and API key.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

# Load .env once at import
load_dotenv()


@dataclass(frozen=True)
class Settings:
    """App settings sourced from environment variables."""

    db_path: str = os.path.expanduser(os.environ.get("PDR_DB", "~/.pdr.sqlite"))

    embeddings_provider: str = os.environ.get("EMBEDDINGS_PROVIDER", "openai").lower()
    embedding_model: str = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_dimensions: int | None = (
        int(os.environ["EMBEDDING_DIMENSIONS"]) if os.environ.get("EMBEDDING_DIMENSIONS") else None
    )

    llm_provider: str = os.environ.get("LLM_PROVIDER", "openai").lower()
    llm_model: str | None = os.environ.get("LLM_MODEL")

    # OpenAI
    openai_api_key: str | None = os.environ.get("OPENAI_API_KEY")
    openai_base_url: str | None = os.environ.get("OPENAI_BASE_URL") or None

    # Cerebras (OpenAI-compatible)
    cerebras_api_key: str | None = os.environ.get("CEREBRAS_API_KEY")
    cerebras_base_url: str = os.environ.get("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1")


def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


def embeddings_client(settings: Settings) -> OpenAI:
    """Return OpenAI client for embeddings.

    Important: do not pass a None base_url to the OpenAI client, since that
    overrides the library default and results in invalid absolute URLs.
    Only include base_url when a non-empty value is provided.
    """
    if settings.embeddings_provider != "openai":
        # Day-1: only OpenAI-compatible embeddings are supported.
        # If another provider is requested, still construct an OpenAI client
        # and rely on OPENAI_BASE_URL to target a compatible endpoint.
        pass
    if settings.openai_base_url:
        return OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    return OpenAI(api_key=settings.openai_api_key)


def llm_client(settings: Settings) -> OpenAI:
    """Return OpenAI client for LLM calls.

    Uses OpenAI defaults or Cerebras OpenAI-compatible base_url.
    Avoid passing base_url=None to preserve library defaults.
    """
    if settings.llm_provider == "cerebras":
        return OpenAI(api_key=settings.cerebras_api_key, base_url=settings.cerebras_base_url)
    if settings.openai_base_url:
        return OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    return OpenAI(api_key=settings.openai_api_key)


def default_llm_model(settings: Settings) -> str:
    """Return provider-appropriate default LLM model."""
    if settings.llm_model:
        return settings.llm_model
    if settings.llm_provider == "cerebras":
        return "qwen-3-coder-480b"
    return "gpt-5-mini"
