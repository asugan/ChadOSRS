package com.asugan.telemetry;

import net.runelite.client.RuneLite;
import net.runelite.client.externalplugins.ExternalPluginManager;

public final class DevRuneLiteLauncher
{
    private DevRuneLiteLauncher()
    {
    }

    public static void main(String[] args) throws Exception
    {
        ExternalPluginManager.loadBuiltin(TelemetryBridgePlugin.class);
        RuneLite.main(args);
    }
}
