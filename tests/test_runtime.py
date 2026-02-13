from __future__ import annotations

from pathlib import Path

from bot_core.adapters.real_stub import RealActionRunnerStub, RealPerceptionStub
from bot_core.adapters.runelite_http import RuneLiteNoopActionRunner, RuneLitePerception
from bot_core.actions.simulated import SimulatedActionRunner
from bot_core.perception.simulated import SimulatedPerception
from bot_core.runtime import build_adapters, load_app_config


def test_load_config_and_build_sim_adapters(tmp_path: Path) -> None:
    config_path = tmp_path / "sim.json"
    config_path.write_text(
        """
{
  "adapter_mode": "sim",
  "engine": {"max_ticks": 10, "max_retries": 2, "log_path": "runs/test.jsonl"},
  "sim_world": {
    "width": 4,
    "height": 4,
    "bot_pos": [0, 0],
    "target_pos": [1, 1],
    "obstacles": []
  },
  "real_stub_world": {
    "width": 4,
    "height": 4,
    "bot_pos": [0, 0],
    "target_pos": [1, 1],
    "obstacles": []
  }
}
""".strip(),
        encoding="utf-8",
    )

    app_config = load_app_config(config_path)
    perception, runner = build_adapters(app_config)

    assert isinstance(perception, SimulatedPerception)
    assert isinstance(runner, SimulatedActionRunner)
    assert app_config.engine.max_ticks == 10


def test_load_config_and_build_real_stub_adapters(tmp_path: Path) -> None:
    config_path = tmp_path / "real_stub.json"
    config_path.write_text(
        """
{
  "adapter_mode": "real_stub",
  "engine": {"max_ticks": 10, "max_retries": 2, "log_path": "runs/test.jsonl"},
  "sim_world": {
    "width": 4,
    "height": 4,
    "bot_pos": [0, 0],
    "target_pos": [1, 1],
    "obstacles": []
  },
  "real_stub_world": {
    "width": 5,
    "height": 5,
    "bot_pos": [0, 0],
    "target_pos": [2, 2],
    "obstacles": [[1, 1]]
  }
}
""".strip(),
        encoding="utf-8",
    )

    app_config = load_app_config(config_path)
    perception, runner = build_adapters(app_config)

    assert isinstance(perception, RealPerceptionStub)
    assert isinstance(runner, RealActionRunnerStub)
    assert app_config.real_stub_world.width == 5


def test_load_config_and_build_runelite_http_adapters(tmp_path: Path) -> None:
    config_path = tmp_path / "runelite_http.json"
    config_path.write_text(
        """
{
  "adapter_mode": "runelite_http",
  "engine": {
    "max_ticks": 10,
    "max_retries": 2,
    "log_path": "runs/test.jsonl",
    "require_tick_advance": true,
    "poll_interval_ms": 10,
    "double_observe": false
  },
  "sim_world": {
    "width": 4,
    "height": 4,
    "bot_pos": [0, 0],
    "target_pos": [1, 1],
    "obstacles": []
  },
  "real_stub_world": {
    "width": 4,
    "height": 4,
    "bot_pos": [0, 0],
    "target_pos": [1, 1],
    "obstacles": []
  },
  "runelite_http": {
    "host": "127.0.0.1",
    "port": 0,
    "observe_timeout_s": 1.0,
    "world_width": 10000,
    "world_height": 10000,
    "target_pos": [3200, 3200],
    "obstacles": []
  }
}
""".strip(),
        encoding="utf-8",
    )

    app_config = load_app_config(config_path)
    perception, runner = build_adapters(app_config)

    try:
        assert isinstance(perception, RuneLitePerception)
        assert isinstance(runner, RuneLiteNoopActionRunner)
        assert app_config.engine.require_tick_advance is True
        assert app_config.engine.double_observe is False
    finally:
        if hasattr(perception, "close"):
            getattr(perception, "close")()
