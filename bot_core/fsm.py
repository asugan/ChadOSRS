from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .types import BotAction
from .world_model import WorldModel


@dataclass
class TickContext:
    world: WorldModel
    max_retries: int
    blackboard: dict[str, Any] = field(default_factory=dict)
    stop_reason: str | None = None


class State(Protocol):
    name: str

    def on_tick(self, ctx: TickContext) -> tuple[str | None, BotAction]:
        ...


class FiniteStateMachine:
    def __init__(self, states: dict[str, State], initial_state: str) -> None:
        if initial_state not in states:
            raise ValueError(f"Unknown initial state: {initial_state}")
        self.states = states
        self.current_state = initial_state

    def tick(self, ctx: TickContext) -> BotAction:
        state = self.states[self.current_state]
        transition, action = state.on_tick(ctx)
        if transition is not None:
            if transition not in self.states:
                raise ValueError(f"Unknown transition state: {transition}")
            self.current_state = transition
        return action
