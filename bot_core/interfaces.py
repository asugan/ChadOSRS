from __future__ import annotations

from typing import Protocol

from .types import ActionResult, BotAction
from .world_model import WorldModel


class IPerception(Protocol):
    def observe(self) -> WorldModel:
        ...


class IActionRunner(Protocol):
    def execute(self, action: BotAction) -> ActionResult:
        ...
