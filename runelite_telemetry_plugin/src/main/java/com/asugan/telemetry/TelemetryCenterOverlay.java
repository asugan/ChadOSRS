package com.asugan.telemetry;

import java.awt.Color;
import java.awt.Dimension;
import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.Graphics2D;
import java.awt.Rectangle;
import javax.inject.Inject;
import javax.inject.Singleton;
import net.runelite.client.ui.overlay.Overlay;
import net.runelite.client.ui.overlay.OverlayLayer;
import net.runelite.client.ui.overlay.OverlayPosition;
import net.runelite.client.ui.overlay.OverlayPriority;

@Singleton
public class TelemetryCenterOverlay extends Overlay
{
    private final TelemetryBridgePlugin plugin;
    private final TelemetryBridgeConfig config;

    @Inject
    public TelemetryCenterOverlay(TelemetryBridgePlugin plugin, TelemetryBridgeConfig config)
    {
        this.plugin = plugin;
        this.config = config;
        setPosition(OverlayPosition.DYNAMIC);
        setLayer(OverlayLayer.ABOVE_WIDGETS);
        setPriority(OverlayPriority.HIGHEST);
    }

    @Override
    public Dimension render(Graphics2D graphics)
    {
        if (!config.centerOverlayEnabled())
        {
            return null;
        }

        String text = plugin.getCenterOverlayText();
        if (text == null)
        {
            return null;
        }

        Rectangle bounds = graphics.getClipBounds();
        if (bounds == null)
        {
            return null;
        }

        Font original = graphics.getFont();
        Font overlayFont = original.deriveFont(Font.BOLD, 22f);
        graphics.setFont(overlayFont);

        FontMetrics metrics = graphics.getFontMetrics();
        int x = bounds.x + (bounds.width - metrics.stringWidth(text)) / 2;
        int y = bounds.y + bounds.height / 2;

        Color color = plugin.isAttackNow() ? new Color(220, 50, 50) : new Color(245, 180, 35);
        graphics.setColor(Color.BLACK);
        graphics.drawString(text, x + 2, y + 2);
        graphics.setColor(color);
        graphics.drawString(text, x, y);

        graphics.setFont(original);
        return null;
    }
}
