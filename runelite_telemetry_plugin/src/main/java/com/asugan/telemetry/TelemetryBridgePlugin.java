package com.asugan.telemetry;

import com.google.inject.Provides;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Locale;
import java.util.logging.Level;
import java.util.logging.Logger;
import javax.inject.Inject;
import net.runelite.api.Client;
import net.runelite.api.GameState;
import net.runelite.api.NPC;
import net.runelite.api.Player;
import net.runelite.api.coords.WorldPoint;
import net.runelite.api.events.GameTick;
import net.runelite.client.config.ConfigManager;
import net.runelite.client.events.ConfigChanged;
import net.runelite.client.eventbus.Subscribe;
import net.runelite.client.plugins.Plugin;
import net.runelite.client.plugins.PluginDescriptor;
import net.runelite.client.ui.overlay.OverlayManager;

@PluginDescriptor(
    name = "Telemetry Bridge",
    description = "Exports read-only player telemetry to localhost",
    tags = {"telemetry", "analysis", "debug"}
)
public class TelemetryBridgePlugin extends Plugin
{
    private static final Logger LOG = Logger.getLogger(TelemetryBridgePlugin.class.getName());
    private static final String CONFIG_GROUP = "telemetrybridge";
    private static final int SCORPION_RADIUS_TILES = 15;
    private static final int MAX_SCORPIONS_PER_TICK = 20;

    private final HttpClient httpClient = HttpClient.newBuilder()
        .connectTimeout(Duration.ofSeconds(2))
        .build();

    @Inject
    private Client client;

    @Inject
    private TelemetryBridgeConfig config;

    @Inject
    private OverlayManager overlayManager;

    @Inject
    private TelemetryCenterOverlay centerOverlay;

    private URI endpointUri;
    private volatile int nearbyScorpionCount = 0;
    private volatile int nearestScorpionDistance = Integer.MAX_VALUE;
    private volatile String nearestScorpionName = "Scorpion";

    @Provides
    TelemetryBridgeConfig provideConfig(ConfigManager configManager)
    {
        return configManager.getConfig(TelemetryBridgeConfig.class);
    }

    @Override
    protected void startUp()
    {
        refreshEndpoint();
        overlayManager.add(centerOverlay);
        LOG.info("Telemetry Bridge started");
    }

    @Override
    protected void shutDown()
    {
        overlayManager.remove(centerOverlay);
        clearOverlayState();
        LOG.info("Telemetry Bridge stopped");
    }

    @Subscribe
    public void onConfigChanged(ConfigChanged event)
    {
        if (!CONFIG_GROUP.equals(event.getGroup()))
        {
            return;
        }

        if ("endpoint".equals(event.getKey()))
        {
            refreshEndpoint();
        }
    }

    @Subscribe
    public void onGameTick(GameTick tick)
    {
        if (!config.enabled())
        {
            clearOverlayState();
            return;
        }

        if (client.getGameState() != GameState.LOGGED_IN)
        {
            clearOverlayState();
            return;
        }

        Player local = client.getLocalPlayer();
        if (local == null)
        {
            clearOverlayState();
            return;
        }

        WorldPoint world = local.getWorldLocation();
        if (world == null)
        {
            clearOverlayState();
            return;
        }

        ScorpionScanResult scan = scanNearbyScorpions(world);
        nearbyScorpionCount = scan.count;
        nearestScorpionDistance = scan.nearestDistance;
        nearestScorpionName = scan.nearestName;

        if (endpointUri == null)
        {
            return;
        }

        TickSnapshot snapshot = new TickSnapshot(
            client.getTickCount(),
            world.getX(),
            world.getY(),
            world.getPlane(),
            local.getAnimation(),
            local.getPoseAnimation(),
            local.getHealthRatio(),
            local.getHealthScale(),
            scan.nearbyScorpionsJson
        );

        HttpRequest request = HttpRequest.newBuilder(endpointUri)
            .header("Content-Type", "application/json")
            .timeout(Duration.ofMillis(config.requestTimeoutMs()))
            .POST(HttpRequest.BodyPublishers.ofString(snapshot.toJson()))
            .build();

        httpClient.sendAsync(request, HttpResponse.BodyHandlers.discarding())
            .exceptionally(ex -> {
                LOG.log(Level.FINE, "Telemetry send failed: " + ex.getMessage());
                return null;
            });
    }

    private void refreshEndpoint()
    {
        String endpoint = config.endpoint();
        try
        {
            endpointUri = URI.create(endpoint);
        }
        catch (IllegalArgumentException ex)
        {
            endpointUri = null;
            LOG.warning("Invalid telemetry endpoint: " + endpoint);
        }
    }

    String getCenterOverlayText()
    {
        if (nearbyScorpionCount <= 0)
        {
            return null;
        }

        if (isAttackNow())
        {
            return "ATTACK " + nearestScorpionName.toUpperCase(Locale.ROOT);
        }

        if (config.overlayOnlyAttackNow())
        {
            return null;
        }

        return "SCORPION NEARBY (" + nearestScorpionDistance + ")";
    }

    boolean isAttackNow()
    {
        return nearestScorpionDistance <= 1;
    }

    private void clearOverlayState()
    {
        nearbyScorpionCount = 0;
        nearestScorpionDistance = Integer.MAX_VALUE;
        nearestScorpionName = "Scorpion";
    }

    private ScorpionScanResult scanNearbyScorpions(WorldPoint localPos)
    {
        StringBuilder sb = new StringBuilder("[");
        int count = 0;
        int nearestDistance = Integer.MAX_VALUE;
        String nearestName = "Scorpion";

        for (NPC npc : client.getNpcs())
        {
            if (npc == null)
            {
                continue;
            }

            String name = npc.getName();
            if (name == null)
            {
                continue;
            }

            String lower = name.toLowerCase(Locale.ROOT);
            if (!lower.contains("scorpion"))
            {
                continue;
            }

            WorldPoint npcPos = npc.getWorldLocation();
            if (npcPos == null || npcPos.getPlane() != localPos.getPlane())
            {
                continue;
            }

            int dx = Math.abs(npcPos.getX() - localPos.getX());
            int dy = Math.abs(npcPos.getY() - localPos.getY());
            int distance = Math.max(dx, dy);
            if (distance > SCORPION_RADIUS_TILES)
            {
                continue;
            }

            if (distance < nearestDistance)
            {
                nearestDistance = distance;
                nearestName = name;
            }

            if (count > 0)
            {
                sb.append(',');
            }

            sb.append('{')
                .append("\"id\":").append(npc.getId()).append(',')
                .append("\"name\":\"").append(escapeJson(name)).append("\",")
                .append("\"pos\":[").append(npcPos.getX()).append(',').append(npcPos.getY()).append("],")
                .append("\"distance\":").append(distance)
                .append('}');

            count++;
            if (count >= MAX_SCORPIONS_PER_TICK)
            {
                break;
            }
        }

        sb.append(']');
        return new ScorpionScanResult(sb.toString(), count, nearestDistance, nearestName);
    }

    private static String escapeJson(String raw)
    {
        StringBuilder out = new StringBuilder(raw.length() + 8);
        for (int i = 0; i < raw.length(); i++)
        {
            char c = raw.charAt(i);
            if (c == '"' || c == '\\')
            {
                out.append('\\');
            }
            out.append(c);
        }
        return out.toString();
    }

    private static final class ScorpionScanResult
    {
        private final String nearbyScorpionsJson;
        private final int count;
        private final int nearestDistance;
        private final String nearestName;

        private ScorpionScanResult(
            String nearbyScorpionsJson,
            int count,
            int nearestDistance,
            String nearestName
        )
        {
            this.nearbyScorpionsJson = nearbyScorpionsJson;
            this.count = count;
            this.nearestDistance = nearestDistance;
            this.nearestName = nearestName;
        }
    }
}
