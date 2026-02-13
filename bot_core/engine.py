from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from .fsm import FiniteStateMachine, TickContext
from .interfaces import IActionRunner, IPerception
from .safety import SafetyConfig, SafetyGuard
from .states import build_default_states
from .types import BotAction


@dataclass
class EngineConfig:
    max_ticks: int = 200
    max_retries: int = 5
    log_path: Path = Path("runs/latest.jsonl")
    max_consecutive_failures: int = 6
    require_tick_advance: bool = False
    poll_interval_ms: int = 25
    double_observe: bool = True


@dataclass
class RunResult:
    success: bool
    reason: str
    ticks: int
    final_state: str
    log_path: Path


class BotEngine:
    def __init__(
        self,
        perception: IPerception,
        runner: IActionRunner,
        fsm: FiniteStateMachine,
        config: EngineConfig | None = None,
    ) -> None:
        self.perception = perception
        self.runner = runner
        self.fsm = fsm
        self.config = config or EngineConfig()
        self.safety = SafetyGuard(
            SafetyConfig(max_consecutive_failures=self.config.max_consecutive_failures)
        )

    @classmethod
    def default(
        cls,
        perception: IPerception,
        runner: IActionRunner,
        config: EngineConfig | None = None,
    ) -> "BotEngine":
        states = build_default_states()
        fsm = FiniteStateMachine(states=states, initial_state="idle")
        return cls(perception=perception, runner=runner, fsm=fsm, config=config)

    def run(self) -> RunResult:
        self.config.log_path.parent.mkdir(parents=True, exist_ok=True)

        initial_world = self.perception.observe()
        ctx = TickContext(
            world=initial_world,
            max_retries=self.config.max_retries,
            blackboard={},
        )

        source_tick: int | None = None
        if self.config.require_tick_advance:
            source_tick = int(initial_world.tick)

        processed_ticks = 0

        with self.config.log_path.open("w", encoding="utf-8") as logfile:
            while processed_ticks < self.config.max_ticks:
                world = self.perception.observe()
                observed_tick = int(world.tick)

                if self.config.require_tick_advance and source_tick is not None:
                    if observed_tick == source_tick:
                        time.sleep(self.config.poll_interval_ms / 1000)
                        continue

                if not self.config.require_tick_advance:
                    world.tick = processed_ticks

                ctx.world = world

                action: BotAction = self.fsm.tick(ctx)
                result = self.runner.execute(action)
                self.safety.evaluate(result, ctx)

                if self.config.double_observe:
                    post_world = self.perception.observe()
                    if not self.config.require_tick_advance:
                        post_world.tick = processed_ticks
                else:
                    post_world = world

                ctx.world = post_world

                if self.config.require_tick_advance:
                    source_tick = observed_tick

                best_target = post_world.meta.get("best_target")
                best_target_id = None
                best_target_distance = None
                best_target_name = None
                if isinstance(best_target, dict):
                    best_target_id = best_target.get("id")
                    best_target_distance = best_target.get("distance")
                    best_target_name = best_target.get("name")

                log_row = {
                    "tick": post_world.tick,
                    "state": self.fsm.current_state,
                    "action": action.kind,
                    "target": action.target,
                    "action_success": result.success,
                    "action_message": result.message,
                    "bot_pos": list(post_world.bot_pos),
                    "target_pos": list(post_world.target_pos),
                    "task_complete": post_world.task_complete,
                    "nearby_scorpion_count": post_world.meta.get("nearby_scorpion_count", 0),
                    "nearest_scorpion_distance": post_world.meta.get(
                        "nearest_scorpion_distance"
                    ),
                    "risk_level": post_world.meta.get("risk_level", "none"),
                    "attack_recommendation": post_world.meta.get(
                        "attack_recommendation", "no_target"
                    ),
                    "can_attack_now": post_world.meta.get("can_attack_now", False),
                    "best_target_id": best_target_id,
                    "best_target_name": best_target_name,
                    "best_target_distance": best_target_distance,
                    "stop_reason": ctx.stop_reason,
                }
                logfile.write(json.dumps(log_row) + "\n")

                processed_ticks += 1

                if post_world.task_complete:
                    return RunResult(
                        success=True,
                        reason="completed",
                        ticks=processed_ticks,
                        final_state=self.fsm.current_state,
                        log_path=self.config.log_path,
                    )

                if ctx.stop_reason is not None:
                    return RunResult(
                        success=False,
                        reason=ctx.stop_reason,
                        ticks=processed_ticks,
                        final_state=self.fsm.current_state,
                        log_path=self.config.log_path,
                    )

        return RunResult(
            success=False,
            reason="timeout",
            ticks=self.config.max_ticks,
            final_state=self.fsm.current_state,
            log_path=self.config.log_path,
        )
