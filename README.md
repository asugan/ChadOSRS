# Bot Core Starter (Python)

Minimal bir bot cekirdegi iskeleti:

- Tick tabanli engine (`sense -> decide -> act`)
- FSM tabanli karar mekanizmasi
- Grid-world simulator
- JSONL loglama
- Basit fail-safe (consecutive failure guard)
- Sim/real-stub adaptor gecisi (config tabanli)
- RuneLite HTTP telemetry adaptor (read-only)
- `pytest` ile temel testler

## Hizli Baslangic

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python3 run_demo.py
python3 -m pytest
```

Demo sonunda log dosyasi `runs/latest.jsonl` altina yazilir.

## Adaptor Modlari

- Config dosyasi: `configs/dev.json`
- `adapter_mode: "sim"` -> Grid simulator adaptorleri
- `adapter_mode: "real_stub"` -> Gercek baglanti yerini temsil eden stub adaptorler
- `adapter_mode: "runelite_http"` -> RuneLite plugininden HTTP tick verisi alir

Ornek:

```bash
python3 run_demo.py --config configs/dev.json
python3 run_demo.py --config configs/real_stub.json
python3 run_demo.py --config configs/runelite_http.json
```

## RuneLite Telemetry ile Canli Calisma

1. RuneLite tarafinda `Telemetry Bridge` pluginini ac.
2. Plugin endpointi: `http://127.0.0.1:8765/tick`
3. Python tarafinda calistir:

```bash
python3 run_demo.py --config configs/runelite_http.json
```

Notlar:

- Bu mod read-only telemetri alir, oyun ici input uretmez.
- `configs/runelite_http.json` icinde `target_pos` ve timeout ayarlarini guncelleyebilirsin.
- Canli modda her game tick bir engine tick olarak islenir (`require_tick_advance: true`).
- `runs/runelite_live.jsonl` icinde `nearby_scorpion_count` ve `nearest_scorpion_distance` alanlari yer alir.
- Ayni logda `risk_level`, `attack_recommendation`, `best_target_*` alanlari da yazilir.

## Dizin Yapisi

- `bot_core/engine.py`: Tick dongusu
- `bot_core/fsm.py`: Finite State Machine
- `bot_core/states.py`: Idle/Navigate/Interact/Recover state'leri
- `bot_core/navigation.py`: A* pathfinding
- `bot_core/simulator/grid_world.py`: Simulasyon ortami
- `bot_core/perception/simulated.py`: Perception adaptor
- `bot_core/actions/simulated.py`: Action runner adaptor
- `bot_core/interfaces.py`: IPerception/IActionRunner protocol'leri
- `bot_core/adapters/real_stub.py`: Gercek entegrasyon icin stub bridge
- `bot_core/adapters/runelite_http.py`: RuneLite HTTP perception + noop action runner
- `bot_core/runtime.py`: Config yukleme ve adaptor secimi
- `bot_core/safety.py`: Fail-safe guard
- `tests/test_engine.py`: Temel davranis testleri
