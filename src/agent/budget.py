"""Budget controls for agent extraction runs."""

from __future__ import annotations

from dataclasses import dataclass

from ..core.exceptions import AgentBudgetExceededError
from ..core.settings import Settings


@dataclass(slots=True)
class PipelineBudget:
    max_turns: int
    max_budget_usd: float


class BudgetTracker:
    """Tracks turn/cost usage and enforces limits."""

    def __init__(self, pipeline_id: str, budget: PipelineBudget):
        self.pipeline_id = pipeline_id
        self.budget = budget
        self.turns_used = 0
        self.cost_used_usd = 0.0

    def record_turn(self, count: int = 1) -> None:
        self.turns_used += count
        if self.turns_used > self.budget.max_turns:
            raise AgentBudgetExceededError(
                self.pipeline_id,
                f"turn limit exceeded ({self.turns_used}>{self.budget.max_turns})",
            )

    def record_cost(self, cost_usd: float) -> None:
        self.cost_used_usd += max(0.0, cost_usd)
        if self.cost_used_usd > self.budget.max_budget_usd:
            raise AgentBudgetExceededError(
                self.pipeline_id,
                (
                    "cost limit exceeded "
                    f"(${self.cost_used_usd:.2f}>${self.budget.max_budget_usd:.2f})"
                ),
            )


def budget_for_pipeline(settings: Settings, pipeline_id: str) -> PipelineBudget:
    """Resolve configured budget limits by pipeline id."""
    if pipeline_id == "covenant-compliance":
        return PipelineBudget(
            max_turns=settings.covenant_max_turns,
            max_budget_usd=settings.covenant_max_budget_usd,
        )
    if pipeline_id == "credit-agreement":
        return PipelineBudget(
            max_turns=settings.credit_agreement_max_turns,
            max_budget_usd=settings.credit_agreement_max_budget_usd,
        )
    return PipelineBudget(
        max_turns=settings.default_max_turns,
        max_budget_usd=settings.default_max_budget_usd,
    )
