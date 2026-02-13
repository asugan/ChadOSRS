from __future__ import annotations

from dataclasses import dataclass, field

from ..types import ActionResult, BotAction, Coord
from ..world_model import Npc, NpcType, WorldModel


@dataclass
class GridWorldState:
    width: int
    height: int
    bot_pos: Coord
    target_pos: Coord
    obstacles: set[Coord] = field(default_factory=set)
    task_complete: bool = False
    npcs: dict[str, Npc] = field(default_factory=dict)


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

    def add_scorpion(self, npc_id: str, pos: Coord, hp: int = 10) -> None:
        self.state.npcs[npc_id] = Npc(
            id=npc_id,
            npc_type=NpcType.SCORPION,
            pos=pos,
            hp=hp,
            max_hp=hp,
            alive=True,
        )

    def _distance(self, pos1: Coord, pos2: Coord) -> int:
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

    def _get_nearest_scorpion(self) -> Npc | None:
        nearest = None
        min_dist = float("inf")
        for npc in self.state.npcs.values():
            if npc.alive:
                dist = self._distance(self.state.bot_pos, npc.pos)
                if dist < min_dist:
                    min_dist = dist
                    nearest = npc
        return nearest

    def snapshot(self) -> WorldModel:
        return WorldModel(
            tick=0,
            width=self.state.width,
            height=self.state.height,
            bot_pos=self.state.bot_pos,
            target_pos=self.state.target_pos,
            obstacles=set(self.state.obstacles),
            task_complete=self.state.task_complete,
            npcs=dict(self.state.npcs),
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

        if action.kind in ("attack", "auto_attack"):
            return self._apply_attack()

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

    def _apply_attack(self) -> ActionResult:
        scorpion = self._get_nearest_scorpion()
        if scorpion is None:
            return ActionResult(success=False, message="no_scorpion_found")

        dist = self._distance(self.state.bot_pos, scorpion.pos)
        if dist > 1:
            return ActionResult(success=False, message="not_in_combat_range")

        scorpion.hp -= 1
        if scorpion.hp <= 0:
            scorpion.alive = False
            return ActionResult(success=True, message="scorpion_killed")

        return ActionResult(success=True, message="scorpion_damaged")
