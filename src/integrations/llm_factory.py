"""Factory for selecting LLM client by provider."""

from __future__ import annotations

from typing import Optional

from ..core.settings import Settings, get_settings
from .claude_client import ClaudeClient
from .llm_base import LLMClientProtocol
from .litellm_client import LiteLLMClient
from .openai_client import OpenAIClient


def get_llm_client(settings: Optional[Settings] = None) -> LLMClientProtocol:
    """Instantiate LLM client based on configured provider."""
    cfg = settings or get_settings()
    provider = (cfg.llm_provider or "anthropic").lower()
    api_key = cfg.llm_api_key or cfg.openai_api_key

    if provider in {"openai", "gpt", "openai_compatible", "openai-compatible"}:
        return OpenAIClient(
            api_key=api_key,
            base_url=cfg.llm_api_base or None,
            model=cfg.agent_model,
        )

    if provider in {"litellm", "lite-llm"}:
        return LiteLLMClient(
            model=cfg.agent_model,
            api_key=api_key,
            base_url=cfg.llm_api_base or None,
            timeout_seconds=cfg.llm_timeout_seconds,
        )

    return ClaudeClient(api_key=cfg.anthropic_api_key, model=cfg.agent_model)
