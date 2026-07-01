// GET /api/control/mode — get current control_mode
// PUT /api/control/mode — set control_mode ('auto' or 'manual')
// On manual transition, capture current duty from Redis to avoid PWM jump
import { NextResponse } from "next/server";
import { promises as fs } from "node:fs";
import yaml from "js-yaml";
import { getRedis } from "../../../../lib/redis";

const CONFIG_PATH =
  process.env.CONTROL_BOARD_CONFIG ||
  "/home/gadgetini/gadgetini/src/exporter/pcb_config.yaml";

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

    // If switching to manual, capture current duty from Redis and update yaml
    if (mode === "manual") {
      const r = getRedis();
      const pumpKeys = [0, 1, 2, 3].map((i) => `pwm_duty_pump_${i}`);
      const fanKeys = [0, 1, 2, 3, 4, 5, 6, 7].map((i) => `pwm_duty_fan_${i}`);
      const vals = await r.mget(...pumpKeys, ...fanKeys);

      // Parse values; null becomes 0 (comm down or key missing)
      const pumpPwm = vals.slice(0, 4).map((v) => parseInt(v, 10) || 0);
      const fanPwm = vals.slice(4, 12).map((v) => parseInt(v, 10) || 0);

      // Update yaml manual_pwm section with current duty (atomic rename)
      const raw = await fs.readFile(CONFIG_PATH, "utf8");
      const doc = yaml.load(raw) || {};
      doc.manual_pwm = { pump: pumpPwm, fan: fanPwm };
      const tmpPath = CONFIG_PATH + ".tmp";
      await fs.writeFile(tmpPath, yaml.dump(doc), "utf8");
      await fs.rename(tmpPath, CONFIG_PATH);
    }

    await getRedis().set("control_mode", mode);
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
