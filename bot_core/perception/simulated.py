from __future__ import annotations

from ..simulator.grid_world import GridWorldEnv
from ..world_model import WorldModel


class SimulatedPerception:
    def __init__(self, env: GridWorldEnv) -> None:
        self.env = env

    def observe(self) -> WorldModel:
        return self.env.snapshot()
