from __future__ import annotations

from pathlib import Path

from bot_core.actions.simulated import SimulatedActionRunner
from bot_core.engine import BotEngine, EngineConfig
from bot_core.perception.simulated import SimulatedPerception
from bot_core.simulator.grid_world import GridWorldEnv


def make_engine(
    env: GridWorldEnv,
    tmp_path: Path,
    *,
    max_ticks: int = 50,
    max_retries: int = 3,
    max_consecutive_failures: int = 10,
) -> BotEngine:
    return BotEngine.default(
        perception=SimulatedPerception(env),
        runner=SimulatedActionRunner(env),
        config=EngineConfig(
            max_ticks=max_ticks,
            max_retries=max_retries,
            max_consecutive_failures=max_consecutive_failures,
            log_path=tmp_path / "latest.jsonl",
        ),
    )


def test_reaches_target_and_completes(tmp_path: Path) -> None:
    env = GridWorldEnv(width=5, height=5, bot_pos=(0, 0), target_pos=(2, 0))
    engine = make_engine(env, tmp_path)

    result = engine.run()

    assert result.success is True
    assert result.reason == "completed"
    assert env.state.task_complete is True
    assert env.state.bot_pos == (2, 0)


def test_timeout_when_ticks_are_too_low(tmp_path: Path) -> None:
    env = GridWorldEnv(width=8, height=8, bot_pos=(0, 0), target_pos=(7, 7))
    engine = make_engine(env, tmp_path, max_ticks=3, max_retries=20)

    result = engine.run()

    assert result.success is False
    assert result.reason == "timeout"


def test_recover_stops_after_max_retries(tmp_path: Path) -> None:
    wall = {(2, y) for y in range(6)}
    env = GridWorldEnv(
        width=6,
        height=6,
        bot_pos=(0, 0),
        target_pos=(5, 5),
        obstacles=wall,
    )
    engine = make_engine(env, tmp_path, max_ticks=60, max_retries=2)

    result = engine.run()

    assert result.success is False
    assert result.reason == "max_retries"
