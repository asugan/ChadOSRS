from __future__ import annotations

from dataclasses import dataclass

from .fsm import TickContext
from .types import ActionResult


@dataclass
class SafetyConfig:
    max_consecutive_failures: int = 6


class SafetyGuard:
    def __init__(self, config: SafetyConfig | None = None) -> None:
        self.config = config or SafetyConfig()
        self.consecutive_failures = 0

    def evaluate(self, result: ActionResult, ctx: TickContext) -> None:
        if result.success:
            self.consecutive_failures = 0
            return

        self.consecutive_failures += 1
        if self.consecutive_failures >= self.config.max_consecutive_failures:
            ctx.stop_reason = "too_many_failures"
