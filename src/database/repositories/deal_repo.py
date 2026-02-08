"""Deal repository."""

from __future__ import annotations

import copy
from typing import Optional

from ...core.models import Deal


class DealRepository:
    """Simple repository for deal records."""

    def __init__(self):
        self._deals: dict[str, Deal] = {}

    async def upsert(self, deal: Deal) -> Deal:
        self._deals[deal.id] = copy.deepcopy(deal)
        return deal

    async def get(self, deal_id: str) -> Optional[Deal]:
        deal = self._deals.get(deal_id)
        return copy.deepcopy(deal) if deal else None

    async def list(self, limit: int = 100, offset: int = 0) -> list[Deal]:
        deals = list(self._deals.values())
        deals.sort(key=lambda d: d.created_at, reverse=True)
        return [copy.deepcopy(deal) for deal in deals[offset : offset + limit]]
