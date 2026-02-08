"""Extraction worker polling repository-backed pending runs."""

from __future__ import annotations

import asyncio
import logging
import signal
from typing import Optional

from ..api.dependencies import get_extraction_service
from ..extraction.service import ExtractionService

logger = logging.getLogger(__name__)


class ExtractionWorker:
    """Background worker executing pending extraction runs."""

    def __init__(
        self,
        service: Optional[ExtractionService] = None,
        poll_interval: float = 2.0,
        batch_size: int = 5,
    ):
        self.service = service or get_extraction_service()
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.running = False
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        logger.info("Starting extraction worker")
        self.running = True

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_shutdown)

        while self.running:
            try:
                completed = await self.service.process_pending_runs(limit=self.batch_size)
                if completed:
                    logger.info("Processed %s extraction runs", len(completed))
                else:
                    await asyncio.sleep(self.poll_interval)
            except Exception as exc:
                logger.exception("Extraction worker loop failed: %s", exc)
                await asyncio.sleep(self.poll_interval)

        logger.info("Extraction worker stopped")

    def _handle_shutdown(self) -> None:
        self.running = False
        self._shutdown_event.set()

    async def stop(self) -> None:
        self.running = False
        self._shutdown_event.set()


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    worker = ExtractionWorker()
    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
