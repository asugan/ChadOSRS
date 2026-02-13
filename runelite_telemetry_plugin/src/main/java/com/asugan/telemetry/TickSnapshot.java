package com.asugan.telemetry;

final class TickSnapshot
{
    private final int tick;
    private final int x;
    private final int y;
    private final int plane;
    private final int animation;
    private final int poseAnimation;
    private final int healthRatio;
    private final int healthScale;
    private final String nearbyScorpionsJson;

    TickSnapshot(
        int tick,
        int x,
        int y,
        int plane,
        int animation,
        int poseAnimation,
        int healthRatio,
        int healthScale,
        String nearbyScorpionsJson
    )
    {
        this.tick = tick;
        this.x = x;
        this.y = y;
        this.plane = plane;
        this.animation = animation;
        this.poseAnimation = poseAnimation;
        this.healthRatio = healthRatio;
        this.healthScale = healthScale;
        this.nearbyScorpionsJson = nearbyScorpionsJson;
    }

    String toJson()
    {
        return "{" +
            "\"tick\":" + tick + "," +
            "\"player_pos\":[" + x + "," + y + "]," +
            "\"plane\":" + plane + "," +
            "\"animation\":" + animation + "," +
            "\"pose_animation\":" + poseAnimation + "," +
            "\"health_ratio\":" + healthRatio + "," +
            "\"health_scale\":" + healthScale + "," +
            "\"nearby_scorpions\":" + nearbyScorpionsJson +
            "}";
    }
}
