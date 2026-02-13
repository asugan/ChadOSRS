from __future__ import annotations

import json
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Condition, Lock, Thread

from ..types import ActionResult, BotAction, Coord
from ..world_model import WorldModel


def _coerce_int(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise RuntimeError(f"Invalid integer field {field_name}: {value}")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(value)
    raise RuntimeError(f"Invalid integer field {field_name}: {value}")


def _risk_level(nearest_distance: int | None) -> str:
    if nearest_distance is None:
        return "none"
    if nearest_distance <= 1:
        return "high"
    if nearest_distance <= 3:
        return "medium"
    return "low"


@dataclass(frozen=True)
class RuneLiteHttpAdapterConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    observe_timeout_s: float = 10.0
    world_width: int = 10000
    world_height: int = 10000
    target_pos: Coord = (0, 0)
    obstacles: set[Coord] | None = None


class _SnapshotStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._condition = Condition(self._lock)
        self._latest: dict[str, object] | None = None

    def put(self, payload: dict[str, object]) -> None:
        with self._condition:
            self._latest = payload
            self._condition.notify_all()

    def wait_for_latest(self, timeout_s: float) -> dict[str, object] | None:
        with self._condition:
            if self._latest is not None:
                return dict(self._latest)
            self._condition.wait(timeout=timeout_s)
            if self._latest is None:
                return None
            return dict(self._latest)


class _TelemetryHandler(BaseHTTPRequestHandler):
    store: _SnapshotStore

    def do_POST(self) -> None:  # noqa: N802
        content_len = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_len)

        try:
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError("payload must be object")
        except (json.JSONDecodeError, ValueError):
            self.send_response(400)
            self.end_headers()
            return

        self.store.put(payload)
        self.send_response(204)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        del format, args


class RuneLiteTelemetryServer:
    def __init__(self, host: str, port: int) -> None:
        self.store = _SnapshotStore()

        handler_cls = type("RuneLiteTelemetryHandler", (_TelemetryHandler,), {})
        handler_cls.store = self.store

        self._server = ThreadingHTTPServer((host, port), handler_cls)
        self._server.daemon_threads = True
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def port(self) -> int:
        return int(self._server.server_port)

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()


class RuneLitePerception:
    def __init__(self, config: RuneLiteHttpAdapterConfig) -> None:
        self.config = config
        self.server = RuneLiteTelemetryServer(host=config.host, port=config.port)

    @property
    def listen_port(self) -> int:
        return self.server.port

    def observe(self) -> WorldModel:
        payload = self.server.store.wait_for_latest(self.config.observe_timeout_s)
        if payload is None:
            raise RuntimeError(
                "Timed out waiting for RuneLite telemetry. Check plugin endpoint and mode."
            )

        tick = _coerce_int(payload.get("tick", 0), "tick")
        pos_raw = payload.get("player_pos", [0, 0])
        if not isinstance(pos_raw, list) or len(pos_raw) != 2:
            raise RuntimeError(f"Invalid player_pos payload: {pos_raw}")

        bot_pos: Coord = (
            _coerce_int(pos_raw[0], "player_pos[0]"),
            _coerce_int(pos_raw[1], "player_pos[1]"),
        )
        obstacles = set(self.config.obstacles or set())
        task_complete = bot_pos == self.config.target_pos
        nearby_scorpions_raw = payload.get("nearby_scorpions", [])

        nearby_scorpions: list[dict[str, object]] = []
        if isinstance(nearby_scorpions_raw, list):
            for item in nearby_scorpions_raw:
                if isinstance(item, dict):
                    distance = item.get("distance")
                    if not isinstance(distance, int):
                        continue

                    npc_id = item.get("id", -1)
                    if not isinstance(npc_id, int):
                        npc_id = -1

                    name = item.get("name", "Unknown")
                    if not isinstance(name, str):
                        name = "Unknown"

                    pos = item.get("pos", [0, 0])
                    if (
                        not isinstance(pos, list)
                        or len(pos) != 2
                        or not isinstance(pos[0], int)
                        or not isinstance(pos[1], int)
                    ):
                        pos = [0, 0]

                    nearby_scorpions.append(
                        {
                            "id": npc_id,
                            "name": name,
                            "pos": pos,
                            "distance": distance,
                        }
                    )

        nearest_scorpion_distance: int | None = None
        distances: list[int] = []
        for npc in nearby_scorpions:
            distance = npc.get("distance")
            if isinstance(distance, int):
                distances.append(distance)
        if distances:
            nearest_scorpion_distance = min(distances)

        nearby_scorpions.sort(
            key=lambda npc: (int(npc.get("distance", 10**6)), int(npc.get("id", -1)))
        )
        best_target: dict[str, object] | None = nearby_scorpions[0] if nearby_scorpions else None

        risk_level = _risk_level(nearest_scorpion_distance)
        if best_target is None:
            attack_recommendation = "no_target"
        elif nearest_scorpion_distance is not None and nearest_scorpion_distance <= 1:
            attack_recommendation = "attack_now"
        elif nearest_scorpion_distance is not None and nearest_scorpion_distance <= 3:
            attack_recommendation = "prepare_attack"
        else:
            attack_recommendation = "approach_target"

        return WorldModel(
            tick=tick,
            width=self.config.world_width,
            height=self.config.world_height,
            bot_pos=bot_pos,
            target_pos=self.config.target_pos,
            obstacles=obstacles,
            task_complete=task_complete,
            meta={
                "nearby_scorpions": nearby_scorpions,
                "nearby_scorpion_count": len(nearby_scorpions),
                "nearest_scorpion_distance": nearest_scorpion_distance,
                "best_target": best_target,
                "risk_level": risk_level,
                "attack_recommendation": attack_recommendation,
                "can_attack_now": nearest_scorpion_distance is not None
                and nearest_scorpion_distance <= 1,
            },
        )

    def close(self) -> None:
        self.server.stop()


class RuneLiteNoopActionRunner:
    def execute(self, action: BotAction) -> ActionResult:
        return ActionResult(success=True, message=f"noop:{action.kind}")
