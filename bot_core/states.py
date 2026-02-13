from __future__ import annotations

from .fsm import State, TickContext
from .navigation import astar
from .types import BotAction, Coord


def _adjacent_candidates(pos: Coord) -> list[Coord]:
    x, y = pos
    return [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]


class IdleState(State):
    name = "idle"

    def on_tick(self, ctx: TickContext) -> tuple[str | None, BotAction]:
        if ctx.world.task_complete:
            ctx.stop_reason = "completed"
            return None, BotAction("idle")

        if ctx.world.bot_pos == ctx.world.target_pos:
            return "interact", BotAction("idle")

        return "navigate", BotAction("idle")


class NavigateState(State):
    name = "navigate"

    def on_tick(self, ctx: TickContext) -> tuple[str | None, BotAction]:
        if ctx.world.bot_pos == ctx.world.target_pos:
            return "interact", BotAction("idle")

        path = astar(
            start=ctx.world.bot_pos,
            goal=ctx.world.target_pos,
            width=ctx.world.width,
            height=ctx.world.height,
            obstacles=ctx.world.obstacles,
        )

        if path is None or len(path) < 2:
            return "recover", BotAction("idle")

        ctx.blackboard["recover_attempts"] = 0
        return None, BotAction(kind="move", target=path[1])


class InteractState(State):
    name = "interact"

    def on_tick(self, ctx: TickContext) -> tuple[str | None, BotAction]:
        return "idle", BotAction("interact")


class RecoverState(State):
    name = "recover"

    def on_tick(self, ctx: TickContext) -> tuple[str | None, BotAction]:
        attempts = ctx.blackboard.get("recover_attempts", 0) + 1
        ctx.blackboard["recover_attempts"] = attempts

        if attempts > ctx.max_retries:
            ctx.stop_reason = "max_retries"
            return None, BotAction("idle")

        candidates = _adjacent_candidates(ctx.world.bot_pos)
        valid = [
            pos
            for pos in candidates
            if 0 <= pos[0] < ctx.world.width
            and 0 <= pos[1] < ctx.world.height
            and pos not in ctx.world.obstacles
        ]

        if not valid:
            ctx.stop_reason = "no_recover_move"
            return None, BotAction("idle")

        valid.sort()
        return "navigate", BotAction(kind="move", target=valid[0])


def build_default_states() -> dict[str, State]:
    return {
        IdleState.name: IdleState(),
        NavigateState.name: NavigateState(),
        InteractState.name: InteractState(),
        RecoverState.name: RecoverState(),
    }
