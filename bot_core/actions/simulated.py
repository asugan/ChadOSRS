from __future__ import annotations

from ..simulator.grid_world import GridWorldEnv
from ..types import ActionResult, BotAction


class SimulatedActionRunner:
    def __init__(self, env: GridWorldEnv) -> None:
        self.env = env

    def execute(self, action: BotAction) -> ActionResult:
        return self.env.step(action)
