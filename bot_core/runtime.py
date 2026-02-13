from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .actions.simulated import SimulatedActionRunner
from .adapters.real_stub import (
    RealActionRunnerStub,
    RealClientBridgeStub,
    RealPerceptionStub,
    RealStubWorldConfig,
)
from .adapters.runelite_http import (
    RuneLiteHttpAdapterConfig,
    RuneLiteNoopActionRunner,
    RuneLitePerception,
)
from .engine import EngineConfig
from .interfaces import IActionRunner, IPerception
from .perception.simulated import SimulatedPerception
from .simulator.grid_world import GridWorldEnv
from .types import Coord


def _to_coord(value: list[int]) -> Coord:
    if len(value) != 2:
        raise ValueError(f"Expected [x, y], got: {value}")
    return (int(value[0]), int(value[1]))


def _to_coord_set(values: list[list[int]]) -> set[Coord]:
    return {_to_coord(v) for v in values}


@dataclass(frozen=True)
class WorldConfig:
    width: int
    height: int
    bot_pos: Coord
    target_pos: Coord
    obstacles: set[Coord]


@dataclass(frozen=True)
class AppConfig:
    adapter_mode: Literal["sim", "real_stub", "runelite_http"]
    engine: EngineConfig
    sim_world: WorldConfig
    real_stub_world: WorldConfig
    runelite_http: RuneLiteHttpAdapterConfig


def load_app_config(path: Path) -> AppConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))

    engine_raw = raw.get("engine", {})
    engine = EngineConfig(
        max_ticks=int(engine_raw.get("max_ticks", 120)),
        max_retries=int(engine_raw.get("max_retries", 6)),
        log_path=Path(engine_raw.get("log_path", "runs/latest.jsonl")),
        max_consecutive_failures=int(engine_raw.get("max_consecutive_failures", 6)),
        require_tick_advance=bool(engine_raw.get("require_tick_advance", False)),
        poll_interval_ms=int(engine_raw.get("poll_interval_ms", 25)),
        double_observe=bool(engine_raw.get("double_observe", True)),
    )

    sim_raw = raw.get("sim_world", {})
    sim_world = WorldConfig(
        width=int(sim_raw.get("width", 8)),
        height=int(sim_raw.get("height", 6)),
        bot_pos=_to_coord(sim_raw.get("bot_pos", [0, 0])),
        target_pos=_to_coord(sim_raw.get("target_pos", [6, 4])),
        obstacles=_to_coord_set(sim_raw.get("obstacles", [])),
    )

    stub_raw = raw.get("real_stub_world", {})
    real_stub_world = WorldConfig(
        width=int(stub_raw.get("width", 8)),
        height=int(stub_raw.get("height", 6)),
        bot_pos=_to_coord(stub_raw.get("bot_pos", [0, 0])),
        target_pos=_to_coord(stub_raw.get("target_pos", [6, 4])),
        obstacles=_to_coord_set(stub_raw.get("obstacles", [])),
    )

    rl_raw = raw.get("runelite_http", {})
    runelite_http = RuneLiteHttpAdapterConfig(
        host=str(rl_raw.get("host", "127.0.0.1")),
        port=int(rl_raw.get("port", 8765)),
        observe_timeout_s=float(rl_raw.get("observe_timeout_s", 10.0)),
        world_width=int(rl_raw.get("world_width", 10000)),
        world_height=int(rl_raw.get("world_height", 10000)),
        target_pos=_to_coord(rl_raw.get("target_pos", [0, 0])),
        obstacles=_to_coord_set(rl_raw.get("obstacles", [])),
    )

    mode = raw.get("adapter_mode", "sim")
    if mode not in {"sim", "real_stub", "runelite_http"}:
        raise ValueError(f"Unknown adapter_mode: {mode}")

    return AppConfig(
        adapter_mode=mode,
        engine=engine,
        sim_world=sim_world,
        real_stub_world=real_stub_world,
        runelite_http=runelite_http,
    )


def build_adapters(config: AppConfig) -> tuple[IPerception, IActionRunner]:
    if config.adapter_mode == "sim":
        env = GridWorldEnv(
            width=config.sim_world.width,
            height=config.sim_world.height,
            bot_pos=config.sim_world.bot_pos,
            target_pos=config.sim_world.target_pos,
            obstacles=config.sim_world.obstacles,
        )
        return SimulatedPerception(env), SimulatedActionRunner(env)

    if config.adapter_mode == "real_stub":
        bridge = RealClientBridgeStub(
            RealStubWorldConfig(
                width=config.real_stub_world.width,
                height=config.real_stub_world.height,
                bot_pos=config.real_stub_world.bot_pos,
                target_pos=config.real_stub_world.target_pos,
                obstacles=config.real_stub_world.obstacles,
            )
        )
        return RealPerceptionStub(bridge), RealActionRunnerStub(bridge)

    return RuneLitePerception(config.runelite_http), RuneLiteNoopActionRunner()
