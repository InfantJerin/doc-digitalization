"""OpenAI client compatible with the platform LLM interface."""

from __future__ import annotations

import asyncio
import base64
import logging
import os
from typing import Optional

from .llm_base import parse_json_response

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None  # type: ignore[assignment]
    logger.warning("openai package not installed. OpenAI features will be limited.")


class OpenAIClient:
    """Client wrapper for OpenAI chat completions API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4.1-mini",
        max_retries: int = 3,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model
        self.max_retries = max_retries

        if OPENAI_AVAILABLE and self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None
            if not OPENAI_AVAILABLE:
                logger.warning("OpenAI client not available - install 'openai' package")
            elif not self.api_key:
                logger.warning("No OPENAI_API_KEY set")

    async def query(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> str:
        if not self.client:
            logger.error("OpenAI client not initialized")
            return ""

        try:
            def _call() -> str:
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                message = resp.choices[0].message
                return message.content or ""

            return await asyncio.to_thread(_call)
        except Exception as exc:
            logger.error("OpenAI API error: %s", exc)
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
        if not self.client:
            logger.error("OpenAI client not initialized")
            return ""

        try:
            def _call() -> str:
                b64 = base64.b64encode(image_data).decode("utf-8")
                data_url = f"data:{image_media_type};base64,{b64}"
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": data_url}},
                            ],
                        }
                    ],
                    max_tokens=max_tokens,
                )
                message = resp.choices[0].message
                return message.content or ""

            return await asyncio.to_thread(_call)
        except Exception as exc:
            logger.error("OpenAI API error (with image): %s", exc)
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
        return self.client is not None
