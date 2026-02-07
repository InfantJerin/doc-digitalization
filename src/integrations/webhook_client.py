"""
Webhook Client.

Handles webhook delivery to configured endpoints after approval.
"""

import logging
import json
from datetime import datetime
from typing import Optional
import uuid
import httpx

from ..core.models import WebhookDelivery, ExtractionRun, GenerationRun
from ..core.exceptions import WebhookError

logger = logging.getLogger(__name__)


class WebhookClient:
    """
    Client for delivering webhooks to configured endpoints.

    Features:
    - Retry logic with exponential backoff
    - Delivery tracking for audit
    - Signature generation for verification
    """

    def __init__(
        self,
        max_retries: int = 3,
        timeout: float = 30.0,
        retry_delay: float = 1.0
    ):
        self.max_retries = max_retries
        self.timeout = timeout
        self.retry_delay = retry_delay
        self.http_client = httpx.AsyncClient(timeout=timeout)

    async def deliver(
        self,
        webhook_url: str,
        payload: dict,
        headers: Optional[dict] = None,
        signing_secret: Optional[str] = None
    ) -> WebhookDelivery:
        """
        Deliver a webhook to the specified URL.

        Args:
            webhook_url: The endpoint URL
            payload: The JSON payload
            headers: Optional additional headers
            signing_secret: Optional secret for signing the payload

        Returns:
            WebhookDelivery record with result
        """
        delivery = WebhookDelivery(
            id=str(uuid.uuid4()),
            webhook_url=webhook_url,
            payload=payload,
            attempted_at=datetime.utcnow()
        )

        request_headers = {
            "Content-Type": "application/json",
            "X-Webhook-ID": delivery.id,
            "X-Webhook-Timestamp": delivery.attempted_at.isoformat()
        }

        if headers:
            request_headers.update(headers)

        if signing_secret:
            signature = self._generate_signature(payload, signing_secret)
            request_headers["X-Webhook-Signature"] = signature

        # Retry loop
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            delivery.attempt_number = attempt

            try:
                response = await self.http_client.post(
                    webhook_url,
                    json=payload,
                    headers=request_headers
                )

                delivery.status_code = response.status_code
                delivery.response_body = response.text[:1000]  # Limit stored response

                if response.is_success:
                    delivery.success = True
                    logger.info(
                        f"Webhook delivered successfully: {webhook_url} "
                        f"(attempt {attempt})"
                    )
                    break
                else:
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.warning(
                        f"Webhook delivery failed: {webhook_url} - {last_error} "
                        f"(attempt {attempt}/{self.max_retries})"
                    )

            except httpx.RequestError as e:
                last_error = str(e)
                logger.warning(
                    f"Webhook request error: {webhook_url} - {e} "
                    f"(attempt {attempt}/{self.max_retries})"
                )

            # Wait before retry (exponential backoff)
            if attempt < self.max_retries:
                import asyncio
                await asyncio.sleep(self.retry_delay * (2 ** (attempt - 1)))

        if not delivery.success:
            delivery.error_message = last_error

        return delivery

    async def deliver_extraction_result(
        self,
        run: ExtractionRun,
        webhook_url: str,
        signing_secret: Optional[str] = None
    ) -> WebhookDelivery:
        """
        Deliver extraction results to a webhook.

        Formats the extraction run into a standard payload format.
        """
        payload = {
            "event": "extraction.completed",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "run_id": run.id,
                "deal_id": run.deal_id,
                "pipeline_id": run.pipeline_id,
                "version": run.version,
                "status": run.status.value,
                "triggered_by": run.triggered_by,
                "document_ids": run.document_ids,
                "extracted_fields": {
                    f.field_path: {
                        "value": f.value,
                        "confidence": f.confidence,
                        "attested": f.attested,
                        "overridden": f.overridden,
                        "override_value": f.override_value if f.overridden else None
                    }
                    for f in run.extracted_fields
                },
                "completed_at": run.completed_at.isoformat() if run.completed_at else None
            }
        }

        delivery = await self.deliver(
            webhook_url=webhook_url,
            payload=payload,
            signing_secret=signing_secret
        )
        delivery.run_id = run.id

        return delivery

    async def deliver_generation_result(
        self,
        run: GenerationRun,
        webhook_url: str,
        signing_secret: Optional[str] = None
    ) -> WebhookDelivery:
        """
        Deliver generation results to a webhook.

        Formats the generation run into a standard payload format.
        """
        payload = {
            "event": "generation.completed",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "run_id": run.id,
                "deal_id": run.deal_id,
                "pipeline_id": run.pipeline_id,
                "version": run.version,
                "status": run.status.value,
                "triggered_by": run.triggered_by,
                "output_path": run.output_path,
                "output_format": run.output_format,
                "sections": [
                    {
                        "id": s.section_id,
                        "name": s.section_name,
                        "has_conflicts": s.data_points.has_conflicts if s.data_points else False
                    }
                    for s in run.sections
                ],
                "completed_at": run.completed_at.isoformat() if run.completed_at else None
            }
        }

        delivery = await self.deliver(
            webhook_url=webhook_url,
            payload=payload,
            signing_secret=signing_secret
        )
        delivery.run_id = run.id

        return delivery

    def _generate_signature(self, payload: dict, secret: str) -> str:
        """Generate HMAC signature for webhook verification."""
        import hmac
        import hashlib

        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        signature = hmac.new(
            secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()

        return f"sha256={signature}"

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()
