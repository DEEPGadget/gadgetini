// GET /api/control/pwm
// Returns pump CH1~4 / fan CH5~12 in **physical channel order** (fixed length 4 / 8).
// Also returns fan RPM (`fan_rpm_*`) and estimated pump flow (`coolant_flow_lpm`).
//
// The Redis keys `pwm_duty_{pump,fan}_{i}` and `fan_rpm_{i}` are indexed by the
// logical slot (0-based) of wiring.pwm.{pump_ch,fan_ch}, so reading them as-is would
// cause "CH9's duty showing up at fan[0] and being labeled CH5". Here we read wiring
// and remap to physical channel positions — fan[ch-5] = that CH's value.
//
// If comm_status is not 'ok' (PCB communication is down), do not show stale Redis
// values — return all null to avoid displaying incorrect info in the UI.
//
// PUT /api/control/pwm
// Sets manual PWM values: { pump: [ch1, ch2, ch3, ch4], fan: [ch5~ch12] }
// Stores in config.yaml under manual_pwm and Redis, switches control_mode to 'manual'.
import { NextResponse } from "next/server";
import { promises as fs } from "node:fs";
import yaml from "js-yaml";
import { getRedis } from "../../../../lib/redis";

const CONFIG_PATH =
  process.env.CONTROL_BOARD_CONFIG ||
  "/home/gadgetini/gadgetini/src/exporter/pcb_config.yaml";

// Physical channel slots (fixed by PCB hardware: TIM1=pump CH1~4, TIM2=fan CH5~8, TIM8=fan CH9~12)
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

    // Fetch duty + RPM + flow together in a single mget
    // (Redis is SET using the logical index of wiring order — see polling.py)
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

    // Remap to physical channel positions — only channels mapped in wiring get values, the rest are null.
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

export async function PUT(request) {
  try {
    const body = await request.json();
    const { pump, fan } = body;

    if (!Array.isArray(pump) || !Array.isArray(fan)) {
      return NextResponse.json(
        { error: "pump and fan must be arrays" },
        { status: 400 }
      );
    }

    if (pump.length !== 4 || fan.length !== 8) {
      return NextResponse.json(
        { error: "pump must have 4 values, fan must have 8 values" },
        { status: 400 }
      );
    }

    // Validate ranges: 0-1000 (0-100%)
    const validatePwm = (val) => {
      const n = parseInt(val, 10);
      return Number.isInteger(n) && n >= 0 && n <= 1000 ? n : null;
    };

    const pumpPwm = pump.map(validatePwm);
    const fanPwm = fan.map(validatePwm);

    if (pumpPwm.includes(null) || fanPwm.includes(null)) {
      return NextResponse.json(
        { error: "PWM values must be integers 0-1000" },
        { status: 400 }
      );
    }

    // Load config, update manual_pwm, write back
    const raw = await fs.readFile(CONFIG_PATH, "utf8");
    const doc = yaml.load(raw) || {};
    doc.manual_pwm = {
      pump: pumpPwm,
      fan: fanPwm,
    };

    const updated = yaml.dump(doc);
    const tmpPath = CONFIG_PATH + ".tmp";
    await fs.writeFile(tmpPath, updated, "utf8");
    await fs.rename(tmpPath, CONFIG_PATH);

    // Set Redis keys for manual PWM + control_mode
    const r = getRedis();
    const pipe = r.pipeline();

    // Store manual PWM in Redis (logical indices, matching wiring)
    // pumpPwm/fanPwm are physical-channel-ordered (CH1~4 / CH5~12); the Redis
    // keys are logical wiring slots, so map each wired channel to its value.
    const { wiredPump, wiredFan } = await loadWiring();
    wiredPump.forEach((ch, i) => {
      pipe.set(`pwm_duty_pump_${i}`, pumpPwm[ch - 1]);
    });
    wiredFan.forEach((ch, i) => {
      pipe.set(`pwm_duty_fan_${i}`, fanPwm[ch - 5]);
    });

    // Switch mode to manual
    pipe.set("control_mode", "manual");
    await pipe.exec();

    return NextResponse.json({
      success: true,
      pump: pumpPwm,
      fan: fanPwm,
      mode: "manual",
    });
  } catch (err) {
    return NextResponse.json(
      { error: err?.message || "Failed to set manual PWM" },
      { status: 500 }
    );
  }
}
