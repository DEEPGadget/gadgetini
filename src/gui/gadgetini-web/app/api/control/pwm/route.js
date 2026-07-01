// GET /api/control/pwm
// Returns pump CH1~4 / fan CH5~12 in **physical channel order** (fixed length 4 / 8).
// Also returns fan RPM (`fan_rpm_*`) and estimated pump flow (`coolant_flow_lpm`).
//
// PWM duty Redis keys are PHYSICAL-channel indexed (pump CH1~4 -> pwm_duty_pump_0~3,
// fan CH5~12 -> pwm_duty_fan_0~7), written by PCBDriver.poll register readback — read
// directly, no remap. fan_rpm is ALSO physical (fan_rpm_0~7 = CH5~12), so RPM lines up
// with the per-channel duty; tach is measured per-channel, independent of PWM wiring.
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

    // PWM duty is PHYSICAL-channel indexed (pump CH1~4 -> _0~3, fan CH5~12 -> _0~7);
    // read directly. fan_rpm is ALSO physical (fan_rpm_0~7 = CH5~12) — read directly too.
    const pumpDutyKeys = PUMP_CHANNELS.map((_, i) => `pwm_duty_pump_${i}`);
    const fanDutyKeys = FAN_CHANNELS.map((_, i) => `pwm_duty_fan_${i}`);
    const fanRpmKeys = FAN_CHANNELS.map((_, i) => `fan_rpm_${i}`);
    const allKeys = [
      ...pumpDutyKeys,
      ...fanDutyKeys,
      ...fanRpmKeys,
      "coolant_flow_lpm",
    ];
    const values = await r.mget(...allKeys);

    let off = 0;
    const pump = values.slice(off, off + pumpDutyKeys.length).map(toIntOrNull);
    off += pumpDutyKeys.length;
    const fan = values.slice(off, off + fanDutyKeys.length).map(toIntOrNull);
    off += fanDutyKeys.length;
    const fanRpm = values.slice(off, off + fanRpmKeys.length).map(toIntOrNull);
    off += fanRpmKeys.length;
    const coolantFlowLpm = toFloatOrNull(values[off]);

    return NextResponse.json({
      pump,
      fan,
      fanRpm,
      coolantFlowLpm,
      pumpChannels: PUMP_CHANNELS,
      fanChannels: FAN_CHANNELS,
      // Channels the fan curve / manual sliders actually control; the rest are fixed
      // (e.g. CH10 RPi fan @100%) and shown read-only with a "fixed" tag.
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

    // Apply PWM to PCB hardware asynchronously (don't block API response)
    // data_crawler will also pick up the updated config on next poll cycle
    setImmediate(() => {
      try {
        const { exec } = require("child_process");
        const scriptPath = "/tmp/apply_pwm_" + Date.now() + ".py";
        const script = `import sys
sys.path.insert(0, '/home/gadgetini/gadgetini/src/exporter')
import yaml, redis, pcb_driver
try:
    with open('${CONFIG_PATH}') as f:
        cfg = yaml.safe_load(f)
    r = redis.Redis(host='127.0.0.1', port=6379, db=0)
    driver = pcb_driver.PCBDriver(cfg, r)
    driver.apply_initial_state()
except Exception as e:
    print(f"PCB apply failed: {e}", file=sys.stderr)
`;
        fs.writeFileSync(scriptPath, script, "utf8");
        exec(`python3 ${scriptPath}`, { timeout: 10000 }, (err, stdout, stderr) => {
          if (err) console.warn("PCB apply warning:", err.message);
          else console.log("PCB PWM applied");
          fs.unlink(scriptPath, () => {});
        });
      } catch (err) {
        console.warn("PCB apply error:", err.message);
      }
    });

    // Set Redis keys for manual PWM (without changing control_mode)
    const r = getRedis();
    const pipe = r.pipeline();

    // Store manual PWM in Redis (physical channel indices, matching poll readback)
    // Instant feedback for the controllable channels (poll re-publishes readback for
    // all channels next cycle). Keys are PHYSICAL-indexed: pump CH-1, fan CH-5.
    const { wiredPump, wiredFan } = await loadWiring();
    wiredPump.forEach((ch) => {
      pipe.set(`pwm_duty_pump_${ch - 1}`, pumpPwm[ch - 1]);
    });
    wiredFan.forEach((ch) => {
      pipe.set(`pwm_duty_fan_${ch - 5}`, fanPwm[ch - 5]);
    });

    // Do NOT change control_mode here — let user explicitly switch via mode button
    await pipe.exec();

    // Get current mode to return in response
    const currentMode = await r.get("control_mode") || "auto";

    return NextResponse.json({
      success: true,
      pump: pumpPwm,
      fan: fanPwm,
      mode: currentMode,
    });
  } catch (err) {
    return NextResponse.json(
      { error: err?.message || "Failed to set manual PWM" },
      { status: 500 }
    );
  }
}
