// GET /api/control/pwm
// Reads PWM duty readback values from Redis (set by control_board polling).
// Pump CH1~4 → pwm_duty_pump_{1..4}, Fan CH5~12 → pwm_duty_fan_{1..8}.
// Missing keys (PCB not connected or wiring unmapped) return null in the array.
import { NextResponse } from "next/server";
import { getRedis } from "../../../../lib/redis";

const PUMP_COUNT = 4;
const FAN_COUNT = 8;

function toIntOrNull(v) {
  if (v === null || v === undefined) return null;
  const n = parseInt(v, 10);
  return Number.isFinite(n) ? n : null;
}

export async function GET() {
  try {
    const r = getRedis();
    const pumpKeys = Array.from({ length: PUMP_COUNT }, (_, i) => `pwm_duty_pump_${i + 1}`);
    const fanKeys = Array.from({ length: FAN_COUNT }, (_, i) => `pwm_duty_fan_${i + 1}`);
    const values = await r.mget(...pumpKeys, ...fanKeys);
    const pump = values.slice(0, PUMP_COUNT).map(toIntOrNull);
    const fan = values.slice(PUMP_COUNT).map(toIntOrNull);
    return NextResponse.json({ pump, fan });
  } catch (err) {
    return NextResponse.json(
      { error: err?.message || "Redis read failed" },
      { status: 500 }
    );
  }
}
