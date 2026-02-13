from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .types import Coord


class NpcType(Enum):
    SCORPION = "scorpion"


@dataclass
class Npc:
    id: str
    npc_type: NpcType
    pos: Coord
    hp: int = 10
    max_hp: int = 10
    alive: bool = True


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
    npcs: dict[str, Npc] = field(default_factory=dict)
