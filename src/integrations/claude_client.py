"""
Claude Client.

Wrapper for the Anthropic Claude API.
"""

import json
import logging
import os
import re
from typing import Optional, Any

logger = logging.getLogger(__name__)

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("anthropic package not installed. LLM features will be limited.")


class ClaudeClient:
    """
    Client for the Anthropic Claude API.

    Provides:
    - Text generation
    - JSON extraction
    - Vision (for document images)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        max_retries: int = 3
    ):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model
        self.max_retries = max_retries

        if ANTHROPIC_AVAILABLE and self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        else:
            self.client = None
            if not ANTHROPIC_AVAILABLE:
                logger.warning("Anthropic client not available - install 'anthropic' package")
            elif not self.api_key:
                logger.warning("No ANTHROPIC_API_KEY set")

    async def query(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.0
    ) -> str:
        """
        Send a query to Claude and get a text response.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens in response
            temperature: Temperature for generation

        Returns:
            Generated text response
        """
        if not self.client:
            logger.error("Claude client not initialized")
            return ""

        try:
            messages = [{"role": "user", "content": prompt}]

            kwargs = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": messages,
            }

            if system_prompt:
                kwargs["system"] = system_prompt

            if temperature > 0:
                kwargs["temperature"] = temperature

            response = self.client.messages.create(**kwargs)
            return response.content[0].text

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return ""

    async def query_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096
    ) -> dict:
        """
        Send a query and parse the response as JSON.

        Args:
            prompt: The user prompt (should request JSON output)
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens in response

        Returns:
            Parsed JSON response as dict
        """
        text = await self.query(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=0.0
        )

        return self._parse_json(text)

    def _parse_json(self, text: str) -> dict:
        """Parse JSON from Claude's response."""
        if not text:
            return {}

        try:
            # Try direct parse
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON in response
        try:
            # Look for JSON block
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
            if json_match:
                return json.loads(json_match.group(1))

            # Look for any JSON object
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                return json.loads(json_match.group())

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from response: {e}")

        return {}

    async def query_with_image(
        self,
        prompt: str,
        image_data: bytes,
        image_media_type: str = "image/png",
        max_tokens: int = 4096
    ) -> str:
        """
        Send a query with an image (for document analysis).

        Args:
            prompt: The user prompt
            image_data: Image bytes
            image_media_type: MIME type of the image
            max_tokens: Maximum tokens in response

        Returns:
            Generated text response
        """
        if not self.client:
            logger.error("Claude client not initialized")
            return ""

        try:
            import base64
            image_base64 = base64.b64encode(image_data).decode("utf-8")

            messages = [{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image_media_type,
                            "data": image_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }]

            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=messages
            )
            return response.content[0].text

        except Exception as e:
            logger.error(f"Claude API error (with image): {e}")
            return ""

    async def batch_query(
        self,
        prompts: list[str],
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096
    ) -> list[str]:
        """
        Send multiple queries (for parallel processing).

        Note: Currently processes sequentially.
        Could be optimized with asyncio.gather for true parallelism.

        Args:
            prompts: List of prompts
            system_prompt: Optional shared system prompt
            max_tokens: Maximum tokens per response

        Returns:
            List of responses
        """
        responses = []
        for prompt in prompts:
            response = await self.query(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens
            )
            responses.append(response)
        return responses

    def is_available(self) -> bool:
        """Check if the client is properly configured."""
        return self.client is not None
