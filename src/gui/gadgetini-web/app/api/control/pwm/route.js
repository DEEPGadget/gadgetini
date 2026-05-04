// GET /api/control/pwm
// 펌프 CH1~4 / 팬 CH5~12 를 **물리 채널 순서**로 반환 (고정 길이 4 / 8).
// 팬 RPM (`fan_rpm_*`)과 펌프 유량 추정 (`coolant_flow_lpm`)도 함께 반환.
//
// Redis 키 `pwm_duty_{pump,fan}_{i}`, `fan_rpm_{i}` 는 wiring.pwm.{pump_ch,fan_ch}의
// 논리 슬롯 인덱스(0-based)라 그대로 보면 "CH9의 duty가 fan[0]에 들어와 CH5로 표기"되는
// 문제가 생긴다. 여기서 wiring을 읽어 물리 채널 위치로 재배치 — fan[ch-5] = 그 CH의 값.
//
// comm_status가 'ok'가 아니면 (PCB 통신 끊긴 상태) Redis에 남은 stale 값을 보지 말고
// 모두 null 반환 — UI에 잘못된 정보 표시 회피.
import { NextResponse } from "next/server";
import { promises as fs } from "node:fs";
import yaml from "js-yaml";
import { getRedis } from "../../../../lib/redis";

const CONFIG_PATH =
  process.env.CONTROL_BOARD_CONFIG ||
  "/home/gadgetini/gadgetini/src/control_board/config.yaml";

// 물리 채널 슬롯 (PCB 하드웨어 고정: TIM1=pump CH1~4, TIM2=fan CH5~8, TIM8=fan CH9~12)
const PUMP_CHANNELS = [1, 2, 3, 4];
const FAN_CHANNELS = [5, 6, 7, 8, 9, 10, 11, 12];

function toIntOrNull(v) {
  if (v === null || v === undefined) return null;
  const n = parseInt(v, 10);
  return Number.isFinite(n) ? n : null;
}

function toFloatOrNull(v) {
  if (v === null || v === undefined) return null;
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : null;
}

function sanitizeChannels(arr, lo, hi) {
  if (!Array.isArray(arr)) return [];
  return arr
    .map((v) => parseInt(v, 10))
    .filter((n) => Number.isInteger(n) && n >= lo && n <= hi);
}

async function loadWiring() {
  try {
    const raw = await fs.readFile(CONFIG_PATH, "utf8");
    const doc = yaml.load(raw) || {};
    const pwm = ((doc.wiring || {}).pwm) || {};
    return {
      wiredPump: sanitizeChannels(pwm.pump_ch, 1, 4),
      wiredFan: sanitizeChannels(pwm.fan_ch, 5, 12),
    };
  } catch {
    return { wiredPump: [], wiredFan: [] };
  }
}

export async function GET() {
  try {
    const { wiredPump, wiredFan } = await loadWiring();
    const r = getRedis();
    const commStatus = await r.get("comm_status");

    if (commStatus !== "ok") {
      return NextResponse.json({
        pump: Array(PUMP_CHANNELS.length).fill(null),
        fan: Array(FAN_CHANNELS.length).fill(null),
        fanRpm: Array(FAN_CHANNELS.length).fill(null),
        coolantFlowLpm: null,
        pumpChannels: PUMP_CHANNELS,
        fanChannels: FAN_CHANNELS,
        wiredPumpChannels: wiredPump,
        wiredFanChannels: wiredFan,
        comm_status: commStatus || "unknown",
      });
    }

    // 한 번의 mget으로 duty + RPM + flow 동시 fetch
    // (Redis는 wiring 순서의 논리 인덱스로 SET됨 — polling.py 참조)
    const pumpDutyKeys = wiredPump.map((_, i) => `pwm_duty_pump_${i}`);
    const fanDutyKeys = wiredFan.map((_, i) => `pwm_duty_fan_${i}`);
    const fanRpmKeys = wiredFan.map((_, i) => `fan_rpm_${i}`);
    const allKeys = [
      ...pumpDutyKeys,
      ...fanDutyKeys,
      ...fanRpmKeys,
      "coolant_flow_lpm",
    ];
    const values = allKeys.length > 0 ? await r.mget(...allKeys) : [];

    let off = 0;
    const pumpDutyLogical = values.slice(off, off + pumpDutyKeys.length).map(toIntOrNull);
    off += pumpDutyKeys.length;
    const fanDutyLogical = values.slice(off, off + fanDutyKeys.length).map(toIntOrNull);
    off += fanDutyKeys.length;
    const fanRpmLogical = values.slice(off, off + fanRpmKeys.length).map(toIntOrNull);
    off += fanRpmKeys.length;
    const coolantFlowLpm = toFloatOrNull(values[off]);

    // 물리 채널 위치로 재배치 — wiring에 매핑된 채널만 값, 나머지 슬롯은 null.
    const pump = PUMP_CHANNELS.map((ch) => {
      const i = wiredPump.indexOf(ch);
      return i >= 0 ? pumpDutyLogical[i] : null;
    });
    const fan = FAN_CHANNELS.map((ch) => {
      const i = wiredFan.indexOf(ch);
      return i >= 0 ? fanDutyLogical[i] : null;
    });
    const fanRpm = FAN_CHANNELS.map((ch) => {
      const i = wiredFan.indexOf(ch);
      return i >= 0 ? fanRpmLogical[i] : null;
    });

    return NextResponse.json({
      pump,
      fan,
      fanRpm,
      coolantFlowLpm,
      pumpChannels: PUMP_CHANNELS,
      fanChannels: FAN_CHANNELS,
      wiredPumpChannels: wiredPump,
      wiredFanChannels: wiredFan,
      comm_status: "ok",
    });
  } catch (err) {
    return NextResponse.json(
      { error: err?.message || "Redis read failed" },
      { status: 500 }
    );
  }
}
