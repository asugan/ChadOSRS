from __future__ import annotations

from dataclasses import dataclass

Coord = tuple[int, int]


@dataclass(frozen=True)
class BotAction:
    kind: str
    target: Coord | None = None


ATTACK_KINDS = {"attack", "auto_attack"}


@dataclass(frozen=True)
class ActionResult:
    success: bool
    message: str = ""
