"""Factory for selecting LLM client by provider."""

from __future__ import annotations

from typing import Optional

from ..core.settings import Settings, get_settings
from .claude_client import ClaudeClient
from .llm_base import LLMClientProtocol
from .openai_client import OpenAIClient


def get_llm_client(settings: Optional[Settings] = None) -> LLMClientProtocol:
    """Instantiate LLM client based on configured provider."""
    cfg = settings or get_settings()
    provider = (cfg.llm_provider or "anthropic").lower()

    if provider in {"openai", "gpt"}:
        return OpenAIClient(api_key=cfg.openai_api_key, model=cfg.agent_model)

    return ClaudeClient(api_key=cfg.anthropic_api_key, model=cfg.agent_model)
