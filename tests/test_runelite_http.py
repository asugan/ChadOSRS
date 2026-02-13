from __future__ import annotations

import json
from urllib import request

from bot_core.adapters.runelite_http import (
    RuneLiteHttpAdapterConfig,
    RuneLiteNoopActionRunner,
    RuneLitePerception,
)
from bot_core.types import BotAction


def _post_json(url: str, payload: dict[str, object]) -> int:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url=url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=2.0) as response:
        return int(response.status)


def test_runelite_perception_observe_maps_payload() -> None:
    perception = RuneLitePerception(
        RuneLiteHttpAdapterConfig(
            host="127.0.0.1",
            port=0,
            observe_timeout_s=1.0,
            world_width=10000,
            world_height=10000,
            target_pos=(3200, 3200),
            obstacles={(1, 1)},
        )
    )

    try:
        url = f"http://127.0.0.1:{perception.listen_port}/tick"
        status = _post_json(
            url,
            {
                "tick": 123,
                "player_pos": [3200, 3200],
                "plane": 0,
                "animation": -1,
                "nearby_scorpions": [
                    {
                        "id": 3028,
                        "name": "Scorpion",
                        "pos": [3201, 3200],
                        "distance": 1,
                    }
                ],
            },
        )
        assert status == 204

        world = perception.observe()
        assert world.tick == 123
        assert world.bot_pos == (3200, 3200)
        assert world.target_pos == (3200, 3200)
        assert world.task_complete is True
        assert (1, 1) in world.obstacles
        assert world.meta["nearby_scorpion_count"] == 1
        assert world.meta["nearest_scorpion_distance"] == 1
        assert world.meta["risk_level"] == "high"
        assert world.meta["attack_recommendation"] == "attack_now"
        assert world.meta["can_attack_now"] is True
        best_target = world.meta.get("best_target")
        assert isinstance(best_target, dict)
        assert best_target.get("id") == 3028
    finally:
        perception.close()


def test_runelite_noop_runner_returns_success() -> None:
    runner = RuneLiteNoopActionRunner()
    result = runner.execute(BotAction(kind="move", target=(1, 0)))

    assert result.success is True
    assert result.message == "noop:move"
