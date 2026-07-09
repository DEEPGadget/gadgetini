// GET /api/control/mode — get current control_mode
// PUT /api/control/mode — set control_mode ('auto' or 'manual')
// On manual transition, capture current duty from Redis to manual_pwm_target_* keys
import { NextResponse } from "next/server";
import { getRedis } from "../../../../lib/redis";

export async function GET() {
  try {
    const mode = await getRedis().get("control_mode");
    return NextResponse.json({
      mode: (mode === "manual" ? "manual" : "auto"),
    });
  } catch (err) {
    return NextResponse.json(
      { error: err?.message || "Failed to get control mode" },
      { status: 500 }
    );
  }
}

export async function PUT(request) {
  try {
    const body = await request.json();
    const { mode } = body;

    if (mode !== "auto" && mode !== "manual") {
      return NextResponse.json(
        { error: "mode must be 'auto' or 'manual'" },
        { status: 400 }
      );
    }

    const r = getRedis();
    const pipe = r.pipeline();

    // If switching to manual, capture current duty from Redis and store as targets
    if (mode === "manual") {
      const pumpKeys = [0, 1, 2, 3].map((i) => `pwm_duty_pump_${i}`);
      const fanKeys = [0, 1, 2, 3, 4, 5, 6, 7].map((i) => `pwm_duty_fan_${i}`);
      const vals = await r.mget(...pumpKeys, ...fanKeys);

      // Parse values; null becomes 500/80 (safe defaults on comm down)
      const pumpPwm = vals.slice(0, 4).map((v) => parseInt(v, 10) || 500);
      const fanPwm = vals.slice(4, 12).map((v) => parseInt(v, 10) || 80);

      // Store as manual targets (will be applied by data_crawler._apply_manual_pwm)
      pumpPwm.forEach((duty, i) => {
        pipe.set(`manual_pwm_target_pump_${i}`, duty);
      });
      fanPwm.forEach((duty, i) => {
        pipe.set(`manual_pwm_target_fan_${i}`, duty);
      });
    }

    pipe.set("control_mode", mode);
    await pipe.exec();

    return NextResponse.json({
      success: true,
      mode: mode,
    });
  } catch (err) {
    return NextResponse.json(
      { error: err?.message || "Failed to set control mode" },
      { status: 500 }
    );
  }
}
