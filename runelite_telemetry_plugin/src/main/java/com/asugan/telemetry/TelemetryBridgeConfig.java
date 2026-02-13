package com.asugan.telemetry;

import net.runelite.client.config.Config;
import net.runelite.client.config.ConfigGroup;
import net.runelite.client.config.ConfigItem;

@ConfigGroup("telemetrybridge")
public interface TelemetryBridgeConfig extends Config
{
    @ConfigItem(
        keyName = "enabled",
        name = "Enabled",
        description = "Enable read-only telemetry export"
    )
    default boolean enabled()
    {
        return true;
    }

    @ConfigItem(
        keyName = "endpoint",
        name = "Endpoint",
        description = "Local endpoint URL, example: http://127.0.0.1:8765/tick"
    )
    default String endpoint()
    {
        return "http://127.0.0.1:8765/tick";
    }

    @ConfigItem(
        keyName = "requestTimeoutMs",
        name = "Request Timeout (ms)",
        description = "HTTP timeout per tick in milliseconds"
    )
    default int requestTimeoutMs()
    {
        return 350;
    }

    @ConfigItem(
        keyName = "centerOverlayEnabled",
        name = "Center Overlay",
        description = "Show center text for nearby scorpion recommendations"
    )
    default boolean centerOverlayEnabled()
    {
        return true;
    }

    @ConfigItem(
        keyName = "overlayOnlyAttackNow",
        name = "Overlay Only Attack Now",
        description = "Show center text only when scorpion is attack range"
    )
    default boolean overlayOnlyAttackNow()
    {
        return true;
    }

    @ConfigItem(
        keyName = "actionBridgeEnabled",
        name = "Action Bridge Enabled",
        description = "Enable local HTTP action endpoint (manual use)"
    )
    default boolean actionBridgeEnabled()
    {
        return false;
    }

    @ConfigItem(
        keyName = "actionBridgeHost",
        name = "Action Bridge Host",
        description = "Host to bind action endpoint"
    )
    default String actionBridgeHost()
    {
        return "127.0.0.1";
    }

    @ConfigItem(
        keyName = "actionBridgePort",
        name = "Action Bridge Port",
        description = "Port to bind action endpoint"
    )
    default int actionBridgePort()
    {
        return 8766;
    }

    @ConfigItem(
        keyName = "actionAuthToken",
        name = "Action Auth Token",
        description = "Optional token expected in X-Action-Token header"
    )
    default String actionAuthToken()
    {
        return "";
    }
}
