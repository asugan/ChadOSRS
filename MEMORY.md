# Project Memory

Bu dosya, su ana kadar yaptigimiz tum isleri hizli hatirlatma icin tutulur.

## 1) Python bot-core altyapisi

- Tick tabanli engine var: `sense -> decide -> act`
- FSM state'leri: `idle`, `navigate`, `interact`, `recover`
- A* pathfinding var
- JSONL loglama var (`runs/*.jsonl`)
- Safety guard var (consecutive failure limiti)
- Adapter bazli mimari var (`IPerception`, `IActionRunner`)
- Engine'e canli veri icin ayarlar eklendi:
  - `require_tick_advance`
  - `poll_interval_ms`
  - `double_observe`

Ana dosyalar:

- `bot_core/engine.py`
- `bot_core/fsm.py`
- `bot_core/states.py`
- `bot_core/navigation.py`
- `bot_core/interfaces.py`

## 2) Adapter katmani

Aktif mode'lar:

- `sim` (grid simulator)
- `real_stub` (entegrasyon template)
- `runelite_http` (RuneLite Telemetry Bridge ile read-only veri)

Config dosyalari:

- `configs/dev.json`
- `configs/real_stub.json`
- `configs/runelite_http.json`

Runelite HTTP adapterinda su an:

- local HTTP server dinleniyor (`127.0.0.1:8765`)
- payload parse ediliyor
- scorpion verileri `WorldModel.meta` icine yaziliyor
- `best_target`, `risk_level`, `attack_recommendation`, `can_attack_now` uretiliyor

Ana dosya:

- `bot_core/adapters/runelite_http.py`

## 3) RuneLite Java plugin (Telemetry Bridge)

Modul: `runelite_telemetry_plugin`

Yapilanlar:

- RuneLite plugin skeleton yazildi
- `GameTick` bazli HTTP POST telemetry eklendi
- Player telemetrisi:
  - `tick`, `player_pos`, `plane`, `animation`, `pose_animation`, `health_ratio`, `health_scale`
- Nearby scorpion telemetrisi eklendi:
  - `id`, `name`, `pos`, `distance`
- Center-screen overlay eklendi:
  - attack mesafesinde: `ATTACK SCORPION`
  - ayara gore sadece attack range'de veya yakinlik mesaji da gosterebilir

Ana dosyalar:

- `runelite_telemetry_plugin/src/main/java/com/asugan/telemetry/TelemetryBridgePlugin.java`
- `runelite_telemetry_plugin/src/main/java/com/asugan/telemetry/TickSnapshot.java`
- `runelite_telemetry_plugin/src/main/java/com/asugan/telemetry/TelemetryBridgeConfig.java`
- `runelite_telemetry_plugin/src/main/java/com/asugan/telemetry/TelemetryCenterOverlay.java`

## 4) Bolt/Flatpak entegrasyonu (kritik notlar)

Kritik bulgu:

- Bolt Flatpak sandbox, `~/Projects` yolunu dogrudan kullanamiyor.

Bu yuzden custom client distro sandbox altina kopyalaniyor:

- `~/.var/app/com.adamcake.Bolt/data/bolt-launcher/custom-clients/runelite-telemetry-plugin`

Calsan launch command:

- `$HOME/.var/app/com.adamcake.Bolt/data/bolt-launcher/custom-clients/runelite-telemetry-plugin/bin/runelite-telemetry-plugin --developer-mode`

Ek not:

- `runeliteVersion` uyumsuzlugunda client acilip kapanabiliyor; su an `1.12.17` ile uyumlu build alindi.

## 5) Canli akis (Python <-> RuneLite)

Calistirma komutu:

- `python3 run_demo.py --config configs/runelite_http.json`

Canli log:

- `runs/runelite_live.jsonl`

Log alanlari su an:

- temel: `tick`, `state`, `action`, `action_message`, `bot_pos`, `target_pos`
- scorpion: `nearby_scorpion_count`, `nearest_scorpion_distance`
- karar: `risk_level`, `attack_recommendation`, `can_attack_now`
- hedef: `best_target_id`, `best_target_name`, `best_target_distance`

Durum:

- Scorpion algisi canli logda dogrulandi
- `nearest_scorpion_distance=1` oldugunda `attack_recommendation=attack_now` uretiliyor

## 6) Test / kalite durumu

- Python testleri yesil: `8 passed`
- Test dosyalari:
  - `tests/test_engine.py`
  - `tests/test_runtime.py`
  - `tests/test_runelite_http.py`

## 7) Bilincli sinir

Bu setup su anda:

- read-only telemetry
- karar/oneri uretimi
- overlay ile manuel yardim

Oyun ici otomatik input/aksiyon uretimi implement edilmedi.

## 8) Sonraki mantikli adimlar

1. Overlay'e hedef outline/tile marker eklemek
2. Terminalde canli alert satiri (`attack_now` oldugunda)
3. Scorpion disinda genel NPC threat modeli (combat level, interacting vb.)
