from __future__ import annotations

from dataclasses import dataclass, field

from ..types import ActionResult, BotAction, Coord
from ..world_model import WorldModel


@dataclass
class GridWorldState:
    width: int
    height: int
    bot_pos: Coord
    target_pos: Coord
    obstacles: set[Coord] = field(default_factory=set)
    task_complete: bool = False


class GridWorldEnv:
    def __init__(
        self,
        width: int,
        height: int,
        bot_pos: Coord,
        target_pos: Coord,
        obstacles: set[Coord] | None = None,
    ) -> None:
        self.state = GridWorldState(
            width=width,
            height=height,
            bot_pos=bot_pos,
            target_pos=target_pos,
            obstacles=obstacles or set(),
        )

    def in_bounds(self, pos: Coord) -> bool:
        return 0 <= pos[0] < self.state.width and 0 <= pos[1] < self.state.height

    def is_walkable(self, pos: Coord) -> bool:
        return self.in_bounds(pos) and pos not in self.state.obstacles

    def snapshot(self) -> WorldModel:
        return WorldModel(
            tick=0,
            width=self.state.width,
            height=self.state.height,
            bot_pos=self.state.bot_pos,
            target_pos=self.state.target_pos,
            obstacles=set(self.state.obstacles),
            task_complete=self.state.task_complete,
        )

    def step(self, action: BotAction) -> ActionResult:
        if self.state.task_complete:
            return ActionResult(success=True, message="already_complete")

        if action.kind == "idle":
            return ActionResult(success=True, message="idle")

        if action.kind == "move":
            if action.target is None:
                return ActionResult(success=False, message="missing_move_target")
            return self._apply_move(action.target)

        if action.kind == "interact":
            if self.state.bot_pos == self.state.target_pos:
                self.state.task_complete = True
                return ActionResult(success=True, message="interaction_success")
            return ActionResult(success=False, message="not_in_range")

        return ActionResult(success=False, message=f"unknown_action:{action.kind}")

    def _apply_move(self, target: Coord) -> ActionResult:
        x, y = self.state.bot_pos
        tx, ty = target
        manhattan = abs(x - tx) + abs(y - ty)
        if manhattan != 1:
            return ActionResult(success=False, message="move_must_be_adjacent")
        if not self.is_walkable(target):
            return ActionResult(success=False, message="blocked")

        self.state.bot_pos = target
        return ActionResult(success=True, message="move_success")
