"""LiteLLM-backed client for model-agnostic OpenAI-spec style access."""

from __future__ import annotations

import asyncio
import base64
import logging
import os
from typing import Optional

from .llm_base import parse_json_response

logger = logging.getLogger(__name__)

try:
    from litellm import completion

    LITELLM_AVAILABLE = True
except ImportError:
    completion = None  # type: ignore[assignment]
    LITELLM_AVAILABLE = False
    logger.warning("litellm package not installed. LiteLLM features will be limited.")


class LiteLLMClient:
    """LLM client using LiteLLM completion interface."""

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: int = 120,
    ):
        self.model = model
        self.api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY", "")
        self.base_url = base_url or os.getenv("LLM_API_BASE", "")
        self.timeout_seconds = timeout_seconds

        if not LITELLM_AVAILABLE:
            self._enabled = False
            return

        self._enabled = bool(self.api_key)
        if not self._enabled:
            logger.warning("No LLM_API_KEY/OPENAI_API_KEY set for LiteLLM")

    async def query(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> str:
        if not self._enabled:
            logger.error("LiteLLM client not initialized")
            return ""

        def _call() -> str:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "api_key": self.api_key,
                "timeout": self.timeout_seconds,
            }
            if self.base_url:
                kwargs["api_base"] = self.base_url

            resp = completion(**kwargs)
            return resp.choices[0].message.content or ""

        try:
            return await asyncio.to_thread(_call)
        except Exception as exc:
            logger.error("LiteLLM error: %s", exc)
            return ""

    async def query_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> dict:
        text = await self.query(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=0.0,
        )
        return parse_json_response(text)

    async def query_with_image(
        self,
        prompt: str,
        image_data: bytes,
        image_media_type: str = "image/png",
        max_tokens: int = 4096,
    ) -> str:
        if not self._enabled:
            logger.error("LiteLLM client not initialized")
            return ""

        def _call() -> str:
            image_base64 = base64.b64encode(image_data).decode("utf-8")
            image_url = f"data:{image_media_type};base64,{image_base64}"

            kwargs = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ],
                "max_tokens": max_tokens,
                "api_key": self.api_key,
                "timeout": self.timeout_seconds,
            }
            if self.base_url:
                kwargs["api_base"] = self.base_url

            resp = completion(**kwargs)
            return resp.choices[0].message.content or ""

        try:
            return await asyncio.to_thread(_call)
        except Exception as exc:
            logger.error("LiteLLM image error: %s", exc)
            return ""

    async def batch_query(
        self,
        prompts: list[str],
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> list[str]:
        responses = []
        for prompt in prompts:
            responses.append(
                await self.query(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                )
            )
        return responses

    def is_available(self) -> bool:
        return self._enabled
