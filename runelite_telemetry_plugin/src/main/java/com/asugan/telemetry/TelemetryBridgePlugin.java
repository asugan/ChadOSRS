package com.asugan.telemetry;

import com.google.inject.Provides;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;
import java.awt.AWTException;
import java.awt.MouseInfo;
import java.awt.Point;
import java.awt.Rectangle;
import java.awt.Robot;
import java.awt.Shape;
import java.awt.event.InputEvent;
import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.InetSocketAddress;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.logging.Level;
import java.util.logging.Logger;
import javax.inject.Inject;
import net.runelite.api.Client;
import net.runelite.api.GameState;
import net.runelite.api.MenuAction;
import net.runelite.api.NPC;
import net.runelite.api.NPCComposition;
import net.runelite.api.Player;
import net.runelite.api.coords.WorldPoint;
import net.runelite.api.events.GameTick;
import net.runelite.client.callback.ClientThread;
import net.runelite.client.config.ConfigManager;
import net.runelite.client.events.ConfigChanged;
import net.runelite.client.eventbus.Subscribe;
import net.runelite.client.plugins.Plugin;
import net.runelite.client.plugins.PluginDescriptor;
import net.runelite.client.ui.overlay.OverlayManager;

@PluginDescriptor(
    name = "Telemetry Bridge",
    description = "Exports telemetry and optional local action bridge",
    tags = {"telemetry", "analysis", "debug"}
)
public class TelemetryBridgePlugin extends Plugin
{
    private static final Logger LOG = Logger.getLogger(TelemetryBridgePlugin.class.getName());
    private static final String CONFIG_GROUP = "telemetrybridge";
    private static final int SCORPION_RADIUS_TILES = 15;
    private static final int MAX_SCORPIONS_PER_TICK = 20;
    private static final Pattern KIND_PATTERN = Pattern.compile("\\\"kind\\\"\\s*:\\s*\\\"([^\\\"]+)\\\"");
    private static final Pattern TARGET_ID_PATTERN = Pattern.compile("\\\"target_id\\\"\\s*:\\s*(-?\\d+)");
    private static final String ACTION_PATH = "/action";
    private static final java.util.Random RANDOM = new java.util.Random();

    private final HttpClient httpClient = HttpClient.newBuilder()
        .connectTimeout(Duration.ofSeconds(2))
        .build();

    private final ExecutorService executorService = Executors.newSingleThreadExecutor();
    private Robot robot;

    @Inject
    private Client client;

    @Inject
    private ClientThread clientThread;

    @Inject
    private TelemetryBridgeConfig config;

    @Inject
    private OverlayManager overlayManager;

    @Inject
    private TelemetryCenterOverlay centerOverlay;

    private URI endpointUri;
    private HttpServer actionServer;
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
        try
        {
            robot = new Robot();
        }
        catch (AWTException e)
        {
            LOG.warning("Failed to initialize Robot for mouse control: " + e.getMessage());
        }
        refreshEndpoint();
        restartActionServer();
        overlayManager.add(centerOverlay);
        LOG.info("Telemetry Bridge started");
    }

    @Override
    protected void shutDown()
    {
        stopActionServer();
        overlayManager.remove(centerOverlay);
        clearOverlayState();
        executorService.shutdownNow();
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
            return;
        }

        if (
            "actionBridgeEnabled".equals(event.getKey())
                || "actionBridgeHost".equals(event.getKey())
                || "actionBridgePort".equals(event.getKey())
                || "actionAuthToken".equals(event.getKey())
        )
        {
            restartActionServer();
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

    private void restartActionServer()
    {
        stopActionServer();

        if (!config.actionBridgeEnabled())
        {
            LOG.info("Action bridge disabled");
            return;
        }

        try
        {
            InetSocketAddress address = new InetSocketAddress(
                config.actionBridgeHost(),
                config.actionBridgePort()
            );
            HttpServer server = HttpServer.create(address, 0);
            server.createContext(ACTION_PATH, new ActionHttpHandler());
            server.start();
            actionServer = server;
            LOG.info("Action bridge listening on http://"
                + config.actionBridgeHost()
                + ":"
                + config.actionBridgePort()
                + ACTION_PATH);
        }
        catch (IOException ex)
        {
            LOG.warning("Action bridge start failed: " + ex.getMessage());
            actionServer = null;
        }
    }

    private void stopActionServer()
    {
        if (actionServer != null)
        {
            actionServer.stop(0);
            actionServer = null;
        }
    }

    private final class ActionHttpHandler implements HttpHandler
    {
        @Override
        public void handle(HttpExchange exchange) throws IOException
        {
            try
            {
                if (!"POST".equalsIgnoreCase(exchange.getRequestMethod()))
                {
                    writeResponse(exchange, 405, "method_not_allowed");
                    return;
                }

                String expectedToken = config.actionAuthToken().trim();
                if (!expectedToken.isEmpty())
                {
                    String providedToken = exchange.getRequestHeaders().getFirst("X-Action-Token");
                    if (providedToken == null || !expectedToken.equals(providedToken))
                    {
                        writeResponse(exchange, 401, "invalid_action_token");
                        return;
                    }
                }

                String body = readRequestBody(exchange);
                String kind = extractField(KIND_PATTERN, body);
                if (kind == null)
                {
                    writeResponse(exchange, 400, "missing_kind");
                    return;
                }

                Integer targetId = null;
                String targetIdStr = extractField(TARGET_ID_PATTERN, body);
                if (targetIdStr != null)
                {
                    try
                    {
                        targetId = Integer.parseInt(targetIdStr);
                    }
                    catch (NumberFormatException ex)
                    {
                        writeResponse(exchange, 400, "invalid_target_id");
                        return;
                    }
                }

                if (!"attack".equals(kind) && !"auto_attack".equals(kind))
                {
                    writeResponse(exchange, 400, "unsupported_kind");
                    return;
                }

                final Integer finalTargetId = targetId;
                clientThread.invoke(() -> handleAttackAction(finalTargetId));
                writeResponse(exchange, 202, "accepted");
            }
            catch (Exception ex)
            {
                LOG.log(Level.FINE, "Action bridge error: " + ex.getMessage());
                writeResponse(exchange, 500, "action_error");
            }
        }
    }

    private void handleAttackAction(Integer targetId)
    {
        if (client.getGameState() != GameState.LOGGED_IN)
        {
            return;
        }

        Player local = client.getLocalPlayer();
        if (local == null)
        {
            return;
        }

        WorldPoint localPos = local.getWorldLocation();
        if (localPos == null)
        {
            return;
        }

        NPC targetNpc = findNearestScorpion(localPos, targetId);
        if (targetNpc == null)
        {
            return;
        }

        if (robot == null)
        {
            performMenuAttack(targetNpc);
            return;
        }

        Shape hull = targetNpc.getConvexHull();
        if (hull == null)
        {
            performMenuAttack(targetNpc);
            return;
        }

        Rectangle bounds = hull.getBounds();
        if (bounds == null)
        {
            performMenuAttack(targetNpc);
            return;
        }

        int x = bounds.x + 2 + RANDOM.nextInt(Math.max(1, bounds.width - 4));
        int y = bounds.y + 2 + RANDOM.nextInt(Math.max(1, bounds.height - 4));

        try
        {
            Point canvasLoc = client.getCanvas().getLocationOnScreen();
            int screenX = canvasLoc.x + x;
            int screenY = canvasLoc.y + y;
            executorService.submit(() -> moveMouseAndClick(screenX, screenY));
        }
        catch (Exception ex)
        {
            LOG.warning("Failed to calculate screen coordinates: " + ex.getMessage());
            performMenuAttack(targetNpc);
        }
    }

    private void moveMouseAndClick(int targetX, int targetY)
    {
        if (robot == null)
        {
            return;
        }

        try
        {
            java.awt.PointerInfo pointerInfo = MouseInfo.getPointerInfo();
            if (pointerInfo == null)
            {
                return;
            }

            Point current = pointerInfo.getLocation();
            int distance = (int) Math.round(current.distance(targetX, targetY));
            int steps = Math.max(12, Math.min(45, (distance / 12) + 10 + RANDOM.nextInt(8)));

            int curveSpread = Math.max(12, Math.min(60, distance / 5));
            double controlX = (current.x + targetX) / 2.0 + (RANDOM.nextInt(curveSpread * 2 + 1) - curveSpread);
            double controlY = (current.y + targetY) / 2.0 + (RANDOM.nextInt(curveSpread * 2 + 1) - curveSpread);

            for (int i = 1; i <= steps; i++)
            {
                double t = i / (double) steps;
                double eased = 1.0 - Math.pow(1.0 - t, 2.2);
                double inv = 1.0 - eased;

                double curveX = (inv * inv * current.x) + (2.0 * inv * eased * controlX) + (eased * eased * targetX);
                double curveY = (inv * inv * current.y) + (2.0 * inv * eased * controlY) + (eased * eased * targetY);

                int jitterRadius = (int) Math.max(0, Math.round(3.0 * (1.0 - t)));
                int jitterX = jitterRadius == 0 ? 0 : RANDOM.nextInt(jitterRadius * 2 + 1) - jitterRadius;
                int jitterY = jitterRadius == 0 ? 0 : RANDOM.nextInt(jitterRadius * 2 + 1) - jitterRadius;

                robot.mouseMove((int) Math.round(curveX) + jitterX, (int) Math.round(curveY) + jitterY);
                Thread.sleep(6 + RANDOM.nextInt(11));
            }

            int settleX = targetX + (RANDOM.nextInt(5) - 2);
            int settleY = targetY + (RANDOM.nextInt(5) - 2);
            robot.mouseMove(settleX, settleY);
            Thread.sleep(40 + RANDOM.nextInt(80));
            robot.mousePress(InputEvent.BUTTON1_DOWN_MASK);
            Thread.sleep(20 + RANDOM.nextInt(35));
            robot.mouseRelease(InputEvent.BUTTON1_DOWN_MASK);
        }
        catch (InterruptedException e)
        {
            Thread.currentThread().interrupt();
        }
        catch (Exception e)
        {
            LOG.warning("Mouse automation error: " + e.getMessage());
        }
    }

    private void performMenuAttack(NPC targetNpc)
    {
        MenuAction attackAction = resolveAttackAction(targetNpc);
        if (attackAction == null)
        {
            return;
        }

        String targetName = targetNpc.getName();
        if (targetName == null)
        {
            targetName = "Scorpion";
        }

        client.menuAction(
            0,
            0,
            attackAction,
            targetNpc.getIndex(),
            0,
            "Attack",
            targetName
        );
    }

    private NPC findNearestScorpion(WorldPoint localPos, Integer targetId)
    {
        java.util.List<NPC> candidates = new java.util.ArrayList<>();
        int nearestDistance = Integer.MAX_VALUE;

        // First pass: find candidates and determine nearest distance
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

            if (!name.toLowerCase(Locale.ROOT).contains("scorpion"))
            {
                continue;
            }

            // If a specific ID is requested, check for match immediately
            if (targetId != null)
            {
                if (npc.getId() == targetId)
                {
                    return npc;
                }
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
            }
            candidates.add(npc);
        }

        if (candidates.isEmpty())
        {
            return null;
        }

        // If targetId was specified but we didn't return in loop, it wasn't found
        if (targetId != null)
        {
            return null;
        }

        // Second pass: Filter candidates that are "close enough" to the nearest one
        // Use a small fuzz factor (e.g. 1-2 tiles) to mimic human imprecision
        int fuzz = 1;
        if (nearestDistance > 5)
        {
            fuzz = 2; // More fuzz for distant targets
        }

        java.util.List<NPC> viableTargets = new java.util.ArrayList<>();
        for (NPC npc : candidates)
        {
            WorldPoint npcPos = npc.getWorldLocation();
            int dx = Math.abs(npcPos.getX() - localPos.getX());
            int dy = Math.abs(npcPos.getY() - localPos.getY());
            int dist = Math.max(dx, dy);

            if (dist <= nearestDistance + fuzz)
            {
                viableTargets.add(npc);
            }
        }

        if (viableTargets.isEmpty())
        {
            return null;
        }

        // Randomly pick one of the viable targets
        return viableTargets.get(RANDOM.nextInt(viableTargets.size()));
    }

    private MenuAction resolveAttackAction(NPC npc)
    {
        NPCComposition composition = npc.getTransformedComposition();
        if (composition == null)
        {
            composition = npc.getComposition();
        }
        if (composition == null)
        {
            return MenuAction.NPC_FIRST_OPTION;
        }

        String[] actions = composition.getActions();
        if (actions == null)
        {
            return MenuAction.NPC_FIRST_OPTION;
        }

        for (int i = 0; i < actions.length; i++)
        {
            String action = actions[i];
            if ("Attack".equalsIgnoreCase(action))
            {
                return npcActionFromIndex(i);
            }
        }

        return MenuAction.NPC_FIRST_OPTION;
    }

    private MenuAction npcActionFromIndex(int index)
    {
        switch (index)
        {
            case 0:
                return MenuAction.NPC_FIRST_OPTION;
            case 1:
                return MenuAction.NPC_SECOND_OPTION;
            case 2:
                return MenuAction.NPC_THIRD_OPTION;
            case 3:
                return MenuAction.NPC_FOURTH_OPTION;
            default:
                return MenuAction.NPC_FIFTH_OPTION;
        }
    }

    private String readRequestBody(HttpExchange exchange) throws IOException
    {
        InputStream in = exchange.getRequestBody();
        byte[] body = in.readAllBytes();
        return new String(body, StandardCharsets.UTF_8);
    }

    private String extractField(Pattern pattern, String body)
    {
        Matcher matcher = pattern.matcher(body);
        if (matcher.find())
        {
            return matcher.group(1);
        }
        return null;
    }

    private void writeResponse(HttpExchange exchange, int status, String body) throws IOException
    {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "text/plain; charset=utf-8");
        exchange.sendResponseHeaders(status, bytes.length);
        exchange.getResponseBody().write(bytes);
        exchange.close();
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
