"""Shared LLM protocol and helpers."""

from __future__ import annotations

import json
import logging
import re
from typing import Protocol, runtime_checkable, Optional

logger = logging.getLogger(__name__)


@runtime_checkable
class LLMClientProtocol(Protocol):
    """Minimal interface used by extraction/generation components."""

    async def query(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> str: ...

    async def query_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> dict: ...

    async def query_with_image(
        self,
        prompt: str,
        image_data: bytes,
        image_media_type: str = "image/png",
        max_tokens: int = 4096,
    ) -> str: ...

    async def batch_query(
        self,
        prompts: list[str],
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> list[str]: ...

    def is_available(self) -> bool: ...


def parse_json_response(text: str) -> dict:
    """Best-effort JSON extraction from model output."""
    if not text:
        return {}

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    try:
        json_match = re.search(r"```json\s*([\s\S]*?)\s*```", text)
        if json_match:
            return json.loads(json_match.group(1))

        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            return json.loads(json_match.group())
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse JSON from response: %s", exc)

    return {}
