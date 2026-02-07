"""
Generation Worker.

Background worker for processing generation requests from the queue.
"""

import asyncio
import logging
import signal
from typing import Optional

from ..generation.service import GenerationService
from ..core.models import RunStatus

logger = logging.getLogger(__name__)


class GenerationWorker:
    """
    Background worker that processes generation requests.

    In a full implementation, this would consume from Kafka/SQS.
    """

    def __init__(
        self,
        service: Optional[GenerationService] = None,
        poll_interval: float = 1.0
    ):
        self.service = service or GenerationService()
        self.poll_interval = poll_interval
        self.running = False
        self._shutdown_event = asyncio.Event()

    async def start(self):
        """Start the worker."""
        logger.info("Starting generation worker")
        self.running = True

        # Set up signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_shutdown)

        while self.running:
            try:
                request = await self._poll_for_work()

                if request:
                    await self._process_request(request)
                else:
                    await asyncio.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(self.poll_interval)

        logger.info("Generation worker stopped")

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
        Poll for generation requests.

        In production, this would read from Kafka/SQS.
        """
        # TODO: Implement queue consumption
        return None

    async def _process_request(self, request: dict):
        """Process a single generation request."""
        logger.info(f"Processing generation request: {request}")

        try:
            run = await self.service.run_generation(
                deal_id=request["deal_id"],
                pipeline_id=request["pipeline_id"],
                triggered_by=request.get("triggered_by", "worker"),
                context_vars=request.get("context_vars")
            )

            logger.info(f"Generation completed: {run.id}, status={run.status.value}")

        except Exception as e:
            logger.error(f"Generation failed: {e}")


async def main():
    """Main entry point for the worker."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    worker = GenerationWorker()
    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
