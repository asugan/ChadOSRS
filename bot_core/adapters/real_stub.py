from __future__ import annotations

from dataclasses import dataclass

from ..simulator.grid_world import GridWorldEnv
from ..types import ActionResult, BotAction, Coord
from ..world_model import WorldModel


@dataclass
class RealStubWorldConfig:
    width: int
    height: int
    bot_pos: Coord
    target_pos: Coord
    obstacles: set[Coord]


class RealClientBridgeStub:
    """Stub for a real game bridge.

    Replace `poll_world` and `send_action` with your legal/approved integration.
    """

    def __init__(self, config: RealStubWorldConfig) -> None:
        self.env = GridWorldEnv(
            width=config.width,
            height=config.height,
            bot_pos=config.bot_pos,
            target_pos=config.target_pos,
            obstacles=config.obstacles,
        )

    def poll_world(self) -> WorldModel:
        return self.env.snapshot()

    def send_action(self, action: BotAction) -> ActionResult:
        return self.env.step(action)


class RealPerceptionStub:
    def __init__(self, bridge: RealClientBridgeStub) -> None:
        self.bridge = bridge

    def observe(self) -> WorldModel:
        return self.bridge.poll_world()


class RealActionRunnerStub:
    def __init__(self, bridge: RealClientBridgeStub) -> None:
        self.bridge = bridge

    def execute(self, action: BotAction) -> ActionResult:
        return self.bridge.send_action(action)
