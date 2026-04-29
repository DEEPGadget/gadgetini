// GET /api/control/pwm
// Reads PWM duty readback values from Redis (set by control_board polling).
// Pump CH1~4 → pwm_duty_pump_{1..4}, Fan CH5~12 → pwm_duty_fan_{1..8}.
// Missing keys (PCB 미연결 / wiring 미매핑 / 모터 미회전 → sticky tach 미감지) → null.
//
// comm_status가 'ok'가 아니면 (PCB 통신 끊긴 상태) Redis에 남은 stale 값을 보지 말고
// 모두 null 반환 — UI에 잘못된 정보 표시 회피.
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
    const commStatus = await r.get("comm_status");
    if (commStatus !== "ok") {
      return NextResponse.json({
        pump: Array(PUMP_COUNT).fill(null),
        fan: Array(FAN_COUNT).fill(null),
        comm_status: commStatus || "unknown",
      });
    }
    // 0-based 인덱스 (control_board polling이 SET하는 키 형식과 일치)
    const pumpKeys = Array.from({ length: PUMP_COUNT }, (_, i) => `pwm_duty_pump_${i}`);
    const fanKeys = Array.from({ length: FAN_COUNT }, (_, i) => `pwm_duty_fan_${i}`);
    const values = await r.mget(...pumpKeys, ...fanKeys);
    const pump = values.slice(0, PUMP_COUNT).map(toIntOrNull);
    const fan = values.slice(PUMP_COUNT).map(toIntOrNull);
    return NextResponse.json({ pump, fan, comm_status: "ok" });
  } catch (err) {
    return NextResponse.json(
      { error: err?.message || "Redis read failed" },
      { status: 500 }
    );
  }
}
