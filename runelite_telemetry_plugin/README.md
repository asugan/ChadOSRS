# RuneLite Telemetry Bridge Plugin

This is a read-only RuneLite plugin skeleton that sends per-tick telemetry to a local HTTP endpoint.

## What it exports

- Tick number
- Player world position (`x`, `y`, `plane`)
- Animation and pose animation IDs
- Health ratio and scale
- Nearby scorpions (name, id, tile, distance)

Payload example:

```json
{
  "tick": 12345,
  "player_pos": [3200, 3201],
  "plane": 0,
  "animation": -1,
  "pose_animation": 808,
  "health_ratio": 26,
  "health_scale": 30,
  "nearby_scorpions": [
    {
      "id": 3028,
      "name": "Scorpion",
      "pos": [3201, 3200],
      "distance": 1
    }
  ]
}
```

## Build notes

This folder is a plugin module skeleton. You can either:

1. Copy `src/main/java/com/asugan/telemetry` into your existing RuneLite plugin template project, or
2. Build this module directly with Gradle in a RuneLite-compatible environment.

## Local development run (recommended)

Run a RuneLite instance with this plugin loaded as a built-in external plugin:

```bash
cd runelite_telemetry_plugin
./gradlew run --args="--developer-mode"
```

This project includes `DevRuneLiteLauncher` which calls
`ExternalPluginManager.loadBuiltin(TelemetryBridgePlugin.class)` before starting RuneLite.

## Bolt launcher note

Bolt/official RuneLite plugin loading is driven by Plugin Hub manifests.
Dropping a random local jar into plugin directories usually will not make it appear in the plugin list.
Use the local development run above for testing local plugin code.

## Bolt setup (working recipe)

This exact flow was used successfully on Flatpak Bolt:

1. Build and create runnable distribution:

```bash
cd ~/Projects/osrsbot/runelite_telemetry_plugin
./gradlew clean installDist
```

2. Copy distribution into Bolt sandbox data (Flatpak cannot read `~/Projects` by default):

```bash
mkdir -p ~/.var/app/com.adamcake.Bolt/data/bolt-launcher/custom-clients
rm -rf ~/.var/app/com.adamcake.Bolt/data/bolt-launcher/custom-clients/runelite-telemetry-plugin
cp -a ~/Projects/osrsbot/runelite_telemetry_plugin/build/install/runelite-telemetry-plugin \
  ~/.var/app/com.adamcake.Bolt/data/bolt-launcher/custom-clients/
```

3. In Bolt config, set **RuneLite launch command** to:

```text
$HOME/.var/app/com.adamcake.Bolt/data/bolt-launcher/custom-clients/runelite-telemetry-plugin/bin/runelite-telemetry-plugin --developer-mode
```

4. Save, fully restart Bolt/RuneLite, then search plugins for `Telemetry Bridge`.

### Important troubleshooting notes

- If client opens then closes quickly, verify `runeliteVersion` in `gradle.properties` matches your launcher/client line.
- If command says OK but nothing opens, it is usually a sandbox path issue; use the path under `~/.var/app/com.adamcake.Bolt/data/bolt-launcher/...`.
- Successful startup log line: `Telemetry Bridge started`.

## Configuration in RuneLite

- `Enabled`: turn telemetry on/off
- `Endpoint`: local endpoint, default `http://127.0.0.1:8765/tick`
- `Request Timeout (ms)`: per-request timeout
- `Center Overlay`: draw center-screen recommendation text
- `Overlay Only Attack Now`: only show overlay when scorpion is in attack range
- `Action Bridge Enabled`: starts a local action endpoint
- `Action Bridge Host`: bind host for action endpoint (default `127.0.0.1`)
- `Action Bridge Port`: bind port for action endpoint (default `8766`)
- `Action Auth Token`: optional token expected in `X-Action-Token`

## Optional action endpoint

When `Action Bridge Enabled` is on, plugin listens on:

- `http://<Action Bridge Host>:<Action Bridge Port>/action`

Supported command payload:

```json
{
  "kind": "attack"
}
```

Optional fields:

- `target_id`: prefer nearest scorpion with matching NPC id

Optional header:

- `X-Action-Token: <your-token>`

## Safety

- By default, action bridge is disabled.
- If enabled, it only accepts local HTTP commands and currently handles `attack`/`auto_attack` for nearby scorpions.
