"""
Extraction Worker.

Background worker for processing extraction requests from the queue.
"""

import asyncio
import logging
import signal
from typing import Optional

from ..extraction.service import ExtractionService
from ..core.models import RunStatus

logger = logging.getLogger(__name__)


class ExtractionWorker:
    """
    Background worker that processes extraction requests.

    In a full implementation, this would consume from Kafka/SQS.
    For now, it provides the structure for async processing.
    """

    def __init__(
        self,
        service: Optional[ExtractionService] = None,
        poll_interval: float = 1.0
    ):
        self.service = service or ExtractionService()
        self.poll_interval = poll_interval
        self.running = False
        self._shutdown_event = asyncio.Event()

    async def start(self):
        """Start the worker."""
        logger.info("Starting extraction worker")
        self.running = True

        # Set up signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_shutdown)

        while self.running:
            try:
                # Poll for work
                request = await self._poll_for_work()

                if request:
                    await self._process_request(request)
                else:
                    await asyncio.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(self.poll_interval)

        logger.info("Extraction worker stopped")

    def _handle_shutdown(self):
        """Handle shutdown signal."""
        logger.info("Shutdown signal received")
        self.running = False
        self._shutdown_event.set()

    async def stop(self):
        """Stop the worker gracefully."""
        self.running = False
        self._shutdown_event.set()

    async def _poll_for_work(self) -> Optional[dict]:
        """
        Poll for extraction requests.

        In production, this would read from Kafka/SQS.
        """
        # TODO: Implement queue consumption
        # For now, return None (no work)
        return None

    async def _process_request(self, request: dict):
        """Process a single extraction request."""
        logger.info(f"Processing extraction request: {request}")

        try:
            run = await self.service.run_extraction(
                deal_id=request["deal_id"],
                pipeline_id=request["pipeline_id"],
                document_ids=request["document_ids"],
                triggered_by=request.get("triggered_by", "worker")
            )

            logger.info(f"Extraction completed: {run.id}, status={run.status.value}")

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            # TODO: Update request status in queue/database


async def main():
    """Main entry point for the worker."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    worker = ExtractionWorker()
    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
