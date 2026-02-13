from __future__ import annotations

from dataclasses import dataclass, field

from .types import Coord


@dataclass
class WorldModel:
    tick: int
    width: int
    height: int
    bot_pos: Coord
    target_pos: Coord
    obstacles: set[Coord] = field(default_factory=set)
    task_complete: bool = False
    meta: dict[str, object] = field(default_factory=dict)
