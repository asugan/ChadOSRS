from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTextEdit,
    QSpinBox,
    QGroupBox,
    QFormLayout,
)

from bot_core.fsm import FiniteStateMachine, TickContext
from bot_core.interfaces import IActionRunner, IPerception
from bot_core.navigation import astar
from bot_core.actions.simulated import SimulatedActionRunner
from bot_core.runtime import load_app_config, build_adapters
from bot_core.simulator.grid_world import GridWorldEnv
from bot_core.states import build_default_states
from bot_core.types import BotAction, Coord
from bot_core.world_model import WorldModel


class MapWidget(QWidget):
    def __init__(
        self,
        width: int = 10,
        height: int = 10,
        cell_size: int = 40,
        max_visible_cells: int = 21,
    ):
        super().__init__()
        self.cell_size = cell_size
        self.max_visible_cells = max_visible_cells
        self.grid_width = width
        self.grid_height = height
        self.view_origin: Coord = (0, 0)
        self.resize_grid(width, height)
        self.world: Optional[WorldModel] = None

    def resize_grid(self, width: int, height: int):
        self.grid_width = width
        self.grid_height = height
        self.setFixedSize(width * self.cell_size, height * self.cell_size)

    def set_world(self, world: WorldModel):
        self.world = world

        if world.width > self.max_visible_cells or world.height > self.max_visible_cells:
            visible_width = min(self.max_visible_cells, world.width)
            visible_height = min(self.max_visible_cells, world.height)
            half_w = visible_width // 2
            half_h = visible_height // 2
            origin_x = max(0, min(world.width - visible_width, world.bot_pos[0] - half_w))
            origin_y = max(0, min(world.height - visible_height, world.bot_pos[1] - half_h))
            self.view_origin = (origin_x, origin_y)
            self.resize_grid(visible_width, visible_height)
        else:
            self.view_origin = (0, 0)
            self.resize_grid(world.width, world.height)

        self.update()

    def _to_view(self, pos: Coord) -> Coord | None:
        local_x = pos[0] - self.view_origin[0]
        local_y = pos[1] - self.view_origin[1]
        if 0 <= local_x < self.grid_width and 0 <= local_y < self.grid_height:
            return local_x, local_y
        return None

    def paintEvent(self, event):
        if self.world is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for x in range(self.grid_width):
            for y in range(self.grid_height):
                painter.setPen(QPen(QColor(100, 100, 100), 1))
                painter.drawRect(
                    x * self.cell_size,
                    (self.grid_height - 1 - y) * self.cell_size,
                    self.cell_size,
                    self.cell_size,
                )

        for obs in self.world.obstacles:
            mapped = self._to_view(obs)
            if mapped is None:
                continue
            ox, oy = mapped
            painter.setBrush(QBrush(QColor(80, 80, 80)))
            painter.drawRect(
                ox * self.cell_size,
                (self.grid_height - 1 - oy) * self.cell_size,
                self.cell_size,
                self.cell_size,
            )

        mapped_target = self._to_view(self.world.target_pos)
        if mapped_target is not None:
            tx, ty = mapped_target
            painter.setBrush(QBrush(QColor(0, 200, 0)))
            painter.drawRect(
                tx * self.cell_size,
                (self.grid_height - 1 - ty) * self.cell_size,
                self.cell_size,
                self.cell_size,
            )

        for npc in self.world.npcs.values():
            if npc.alive:
                mapped = self._to_view(npc.pos)
                if mapped is None:
                    continue
                nx, ny = mapped
                hp_ratio = npc.hp / npc.max_hp
                color = QColor(int(200 * (1 - hp_ratio)), int(200 * hp_ratio), 0)
                painter.setBrush(QBrush(color))
                painter.drawEllipse(
                    nx * self.cell_size + 5,
                    (self.grid_height - 1 - ny) * self.cell_size + 5,
                    self.cell_size - 10,
                    self.cell_size - 10,
                )

        mapped_bot = self._to_view(self.world.bot_pos)
        if mapped_bot is not None:
            bx, by = mapped_bot
            painter.setBrush(QBrush(QColor(0, 100, 255)))
            painter.drawEllipse(
                bx * self.cell_size + 3,
                (self.grid_height - 1 - by) * self.cell_size + 3,
                self.cell_size - 6,
                self.cell_size - 6,
            )


class BotGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OSRS Bot GUI - FSM Entegre")
        self.setGeometry(100, 100, 900, 600)

        self.env: Optional[GridWorldEnv] = None
        self.runner: Optional[SimulatedActionRunner] = None
        self.fsm: Optional[FiniteStateMachine] = None
        self.ctx: Optional[TickContext] = None
        self.live_mode = False
        self.live_perception: Optional[IPerception] = None
        self.live_runner: Optional[IActionRunner] = None
        self.live_world: Optional[WorldModel] = None
        self.live_config_path = Path(__file__).resolve().parents[1] / "configs" / "runelite_http.json"
        self.last_live_tick: Optional[int] = None
        self.last_live_attack_tick: Optional[int] = None
        self.running = False
        self.tick_count = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._step_tick)

        self._setup_ui()
        self._setup_default_world()
        self._enable_live_mode(auto=True)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        left_panel = QVBoxLayout()
        main_layout.addLayout(left_panel, 2)

        map_group = QGroupBox("Harita")
        map_layout = QVBoxLayout()
        self.map_widget = MapWidget(width=10, height=10)
        map_layout.addWidget(self.map_widget)
        map_group.setLayout(map_layout)
        left_panel.addWidget(map_group)

        control_group = QGroupBox("Kontrol")
        control_layout = QHBoxLayout()

        self.start_btn = QPushButton("Başlat")
        self.start_btn.clicked.connect(self._start_bot)
        control_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Durdur")
        self.stop_btn.clicked.connect(self._stop_bot)
        self.stop_btn.setEnabled(False)
        control_layout.addWidget(self.stop_btn)

        self.step_btn = QPushButton("Adım")
        self.step_btn.clicked.connect(self._step_bot)
        control_layout.addWidget(self.step_btn)

        control_group.setLayout(control_layout)
        left_panel.addWidget(control_group)

        status_layout = QHBoxLayout()
        self.status_label = QLabel("Durum: Hazır")
        status_layout.addWidget(self.status_label)
        self.mode_label = QLabel("Mod: Sim")
        status_layout.addWidget(self.mode_label)
        self.state_label = QLabel("State: idle")
        status_layout.addWidget(self.state_label)
        self.tick_label = QLabel("Tick: 0")
        status_layout.addWidget(self.tick_label)
        left_panel.addLayout(status_layout)

        right_panel = QVBoxLayout()
        main_layout.addLayout(right_panel, 1)

        settings_group = QGroupBox("Ayarlar")
        settings_layout = QFormLayout()

        self.width_spin = QSpinBox()
        self.width_spin.setRange(5, 30)
        self.width_spin.setValue(10)
        self.width_spin.valueChanged.connect(self._on_settings_changed)
        settings_layout.addRow("Genişlik:", self.width_spin)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(5, 30)
        self.height_spin.setValue(10)
        self.height_spin.valueChanged.connect(self._on_settings_changed)
        settings_layout.addRow("Yükseklik:", self.height_spin)

        self.max_ticks_spin = QSpinBox()
        self.max_ticks_spin.setRange(10, 1000)
        self.max_ticks_spin.setValue(120)
        settings_layout.addRow("Max Tick:", self.max_ticks_spin)

        self.scorpion_hp_spin = QSpinBox()
        self.scorpion_hp_spin.setRange(1, 100)
        self.scorpion_hp_spin.setValue(10)
        self.scorpion_hp_spin.valueChanged.connect(self._on_settings_changed)
        settings_layout.addRow("Scorpion HP:", self.scorpion_hp_spin)

        settings_group.setLayout(settings_layout)
        right_panel.addWidget(settings_group)

        self.live_toggle_btn = QPushButton("Canlı Veri Aç")
        self.live_toggle_btn.clicked.connect(self._toggle_live_mode)
        right_panel.addWidget(self.live_toggle_btn)

        self.reset_btn = QPushButton("Haritayı Sıfırla")
        self.reset_btn.clicked.connect(self._setup_default_world)
        right_panel.addWidget(self.reset_btn)

        self.attack_btn = QPushButton("Saldır!")
        self.attack_btn.clicked.connect(self._manual_attack)
        right_panel.addWidget(self.attack_btn)

        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        right_panel.addWidget(log_group)

    def _log(self, msg: str):
        self.log_text.append(msg)

    def _on_settings_changed(self):
        if self.live_mode:
            return
        self._setup_default_world()

    def _set_sim_controls_enabled(self, enabled: bool):
        self.width_spin.setEnabled(enabled)
        self.height_spin.setEnabled(enabled)
        self.scorpion_hp_spin.setEnabled(enabled)
        self.reset_btn.setEnabled(enabled)

    def _close_live_mode(self):
        if self.live_perception and hasattr(self.live_perception, "close"):
            try:
                getattr(self.live_perception, "close")()
            except Exception:
                pass
        self.live_perception = None
        self.live_runner = None
        self.live_world = None
        self.last_live_tick = None
        self.last_live_attack_tick = None

    def _enable_live_mode(self, auto: bool = False):
        if self.running:
            self._stop_bot()
        if self.live_mode:
            return

        try:
            self._close_live_mode()
            app_config = load_app_config(self.live_config_path)
            if app_config.adapter_mode != "runelite_http":
                raise RuntimeError(
                    f"adapter_mode runelite_http olmalı, mevcut: {app_config.adapter_mode}"
                )

            short_timeout_cfg = replace(
                app_config.runelite_http,
                observe_timeout_s=min(app_config.runelite_http.observe_timeout_s, 0.25),
            )
            app_config = replace(app_config, runelite_http=short_timeout_cfg)

            perception, runner = build_adapters(app_config)
            self.live_perception = perception
            self.live_runner = runner
            self.live_mode = True
            self.running = False
            self.timer.stop()
            self.tick_count = 0
            max_ticks = max(
                self.max_ticks_spin.minimum(),
                min(self.max_ticks_spin.maximum(), app_config.engine.max_ticks),
            )
            self.max_ticks_spin.setValue(max_ticks)
            self.mode_label.setText("Mod: Canlı")
            self.live_toggle_btn.setText("Canlı Veri Kapat")
            self.state_label.setText("State: live")
            self.tick_label.setText("Tick: 0")
            self.status_label.setText("Durum: Canlı Mod Hazır")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self._set_sim_controls_enabled(False)

            host = app_config.runelite_http.host
            port = app_config.runelite_http.port
            if hasattr(perception, "listen_port"):
                port = int(getattr(perception, "listen_port"))
            self._log(f"Canlı mod aktif. Endpoint: http://{host}:{port}/tick")
        except Exception as exc:
            self._close_live_mode()
            self.live_mode = False
            self.mode_label.setText("Mod: Sim")
            self.live_toggle_btn.setText("Canlı Veri Aç")
            self._set_sim_controls_enabled(True)
            if not auto:
                self._log(f"Canlı mod açılamadı: {exc}")

    def _disable_live_mode(self):
        if self.running:
            self._stop_bot()
        self.live_mode = False
        self._close_live_mode()
        self.mode_label.setText("Mod: Sim")
        self.live_toggle_btn.setText("Canlı Veri Aç")
        self._set_sim_controls_enabled(True)
        self._setup_default_world()
        self._log("Canlı mod kapatıldı, simülasyon moduna dönüldü")

    def _toggle_live_mode(self):
        if self.live_mode:
            self._disable_live_mode()
            return
        self._enable_live_mode(auto=False)

    def _step_live_tick(self):
        if not self.live_perception:
            self._log("Canlı tick error: perception yok")
            self._stop_bot()
            return

        if self.tick_count >= self.max_ticks_spin.value():
            self._log("Max tick reached!")
            self._stop_bot()
            return

        try:
            world = self.live_perception.observe()
        except Exception as exc:
            self._log(f"Canlı veri bekleniyor: {exc}")
            return

        self.live_world = world
        self.tick_count += 1

        recommendation = str(world.meta.get("attack_recommendation", "no_target"))
        nearest_distance = world.meta.get("nearest_scorpion_distance")

        self.state_label.setText("State: live")
        self.tick_label.setText(f"Tick: {world.tick}")
        self._update_map()

        if self.last_live_tick != world.tick:
            self.last_live_tick = world.tick
            self._log(
                "[live] "
                f"tick={world.tick} "
                f"player={world.bot_pos} "
                f"npc_count={world.meta.get('nearby_scorpion_count', 0)} "
                f"nearest={nearest_distance} "
                f"rec={recommendation}"
            )

        if (
            self.running
            and self.live_runner
            and recommendation == "attack_now"
            and self.last_live_attack_tick != world.tick
        ):
            self.last_live_attack_tick = world.tick
            result = self.live_runner.execute(BotAction(kind="attack"))
            self._log(f"[live-action] attack -> {result.message}")

    @staticmethod
    def _distance(pos1: Coord, pos2: Coord) -> int:
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

    def _reset_runtime_context(self):
        if not self.env:
            return

        self.runner = SimulatedActionRunner(self.env)
        self.fsm = FiniteStateMachine(states=build_default_states(), initial_state="idle")
        self.ctx = TickContext(
            world=self.env.snapshot(),
            max_retries=6,
            blackboard={},
        )
        self.tick_count = 0
        self.state_label.setText("State: idle")
        self.tick_label.setText("Tick: 0")

    def _path_to_attack_range(self, npc_pos: Coord) -> list[Coord] | None:
        if not self.env:
            return None

        candidates = [
            (npc_pos[0] + 1, npc_pos[1]),
            (npc_pos[0] - 1, npc_pos[1]),
            (npc_pos[0], npc_pos[1] + 1),
            (npc_pos[0], npc_pos[1] - 1),
        ]
        valid_goals = [pos for pos in candidates if self.env.is_walkable(pos)]

        best_path: list[Coord] | None = None
        for goal in valid_goals:
            path = astar(
                start=self.env.state.bot_pos,
                goal=goal,
                width=self.env.state.width,
                height=self.env.state.height,
                obstacles=self.env.state.obstacles,
            )
            if path is None:
                continue
            if best_path is None or len(path) < len(best_path):
                best_path = path

        return best_path

    def _setup_default_world(self):
        if self.live_mode:
            return

        if self.running:
            self._stop_bot()

        w = self.width_spin.value()
        h = self.height_spin.value()
        self.env = GridWorldEnv(
            width=w,
            height=h,
            bot_pos=(1, 1),
            target_pos=(w - 2, h - 2),
            obstacles={(w // 2, h // 2), (w // 2 + 1, h // 2)},
        )
        self.env.add_scorpion("scorpion_1", (w - 3, h // 2), hp=self.scorpion_hp_spin.value())

        self._reset_runtime_context()
        self.status_label.setText("Durum: Hazır")
        self._update_map()
        self._log(f"Harita oluşturuldu: {w}x{h}, FSM: idle")

    def _update_map(self):
        if self.live_mode and self.live_world:
            self.map_widget.set_world(self.live_world)
            return

        if self.env:
            self.map_widget.resize_grid(self.env.state.width, self.env.state.height)
            self.map_widget.set_world(self.env.snapshot())

    def _start_bot(self):
        if self.running:
            return

        if self.live_mode:
            if not self.live_perception:
                self._log("Canlı mod hazır değil")
                return
            self.last_live_attack_tick = None
            self.running = True
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.status_label.setText("Durum: Canlı Veri Dinleniyor")
            self._log("Canlı veri akışı başlatıldı")
            self.timer.start(100)
            return

        if not self.env:
            return

        run_finished = (
            self.ctx is not None
            and (
                self.ctx.stop_reason is not None
                or self.tick_count >= self.max_ticks_spin.value()
                or self.env.state.task_complete
            )
        )
        if run_finished:
            self._setup_default_world()
            self._log("Koşu tamamlandığı için dünya yeniden kuruldu")

        if (
            not self.runner
            or not self.fsm
            or not self.ctx
        ):
            self._reset_runtime_context()
            self._update_map()
            self._log("Koşu bağlamı sıfırlandı")

        self.running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("Durum: Çalışıyor")
        self._log("Bot başlatıldı (FSM)")

        self.timer.start(100)

    def _stop_bot(self):
        self.running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Durum: Durduruldu")
        self.timer.stop()
        self._log("Bot durduruldu")

    def _step_tick(self):
        if self.live_mode:
            self._step_live_tick()
            return

        if not self.env or not self.runner or not self.fsm or not self.ctx:
            return

        if self.tick_count >= self.max_ticks_spin.value():
            self._log("Max tick reached!")
            self._stop_bot()
            return

        if self.ctx.stop_reason:
            self._log(f"Stopped: {self.ctx.stop_reason}")
            self._stop_bot()
            return

        try:
            self.ctx.world = self.env.snapshot()
            previous_state = self.fsm.current_state
            action = self.fsm.tick(self.ctx)
            result = self.runner.execute(action)
            self.ctx.world = self.env.snapshot()

            self.tick_count += 1

            self.state_label.setText(f"State: {self.fsm.current_state}")
            self.tick_label.setText(f"Tick: {self.tick_count}")
            self._log(
                f"[{previous_state}->{self.fsm.current_state}] "
                f"{action.kind} -> {result.message}"
            )

            self._update_map()
        except Exception as exc:
            self._log(f"Tick error: {exc}")
            self._stop_bot()

    def _step_bot(self):
        if self.live_mode:
            self._step_live_tick()
            return

        if (
            not self.running
            and self.env
            and self.ctx
            and (
                self.ctx.stop_reason is not None
                or self.tick_count >= self.max_ticks_spin.value()
                or self.env.state.task_complete
            )
        ):
            self._setup_default_world()
            self._log("Adım öncesi dünya yeniden kuruldu")
        self._step_tick()

    def _manual_attack(self):
        if self.live_mode:
            if not self.live_runner:
                self._log("Canlı saldırı: runner yok")
                return

            result = self.live_runner.execute(BotAction(kind="attack"))
            recommendation = "no_target"
            can_attack_now = False
            best_target_id = None
            if self.live_world:
                recommendation = str(
                    self.live_world.meta.get("attack_recommendation", "no_target")
                )
                can_attack_now = bool(self.live_world.meta.get("can_attack_now", False))
                best_target = self.live_world.meta.get("best_target")
                if isinstance(best_target, dict):
                    best_target_id = best_target.get("id")

            self._log(
                f"Canlı saldırı isteği: {result.message} "
                f"(öneri={recommendation}, can_attack_now={can_attack_now}, "
                f"target={best_target_id})"
            )
            return

        if not self.env or not self.runner:
            return

        try:
            alive_npcs = [npc for npc in self.env.state.npcs.values() if npc.alive]
            if not alive_npcs:
                self._log("Saldırı: canlı hedef yok")
                self._update_map()
                return

            bot_pos = self.env.state.bot_pos
            target_npc = min(alive_npcs, key=lambda npc: self._distance(bot_pos, npc.pos))
            dist = self._distance(bot_pos, target_npc.pos)

            if dist > 1:
                path = self._path_to_attack_range(target_npc.pos)
                if path is None or len(path) < 2:
                    self._log("Saldırı: menzile yaklaşmak için yol bulunamadı")
                    self._update_map()
                    return

                move_result = self.runner.execute(BotAction(kind="move", target=path[1]))
                self._log(f"Saldırı için yaklaş: {move_result.message}")
                if not move_result.success:
                    self._update_map()
                    return

            result = self.runner.execute(BotAction(kind="attack"))
            self._update_map()
            self._log(f"Saldırı: {result.message}")

            for npc in self.env.state.npcs.values():
                if npc.alive:
                    self._log(f"  {npc.id} HP: {npc.hp}/{npc.max_hp}")
        except Exception as exc:
            self._log(f"Attack error: {exc}")

    def closeEvent(self, event):
        self._close_live_mode()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    window = BotGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
