// GET  /api/control/fan-curve  → returns current fan_curve from config.yaml
// PUT  /api/control/fan-curve  → writes new fan_curve into config.yaml (atomic rename)
//
// control_board는 mtime 변경을 polling으로 감지하여 다음 cycle (~1s) 안에 PCB에 반영한다.
// 주석/포맷은 js-yaml dump 시 손실됨 (UX 우선, 후속 PR에서 lossless yaml 검토).
import { NextResponse } from "next/server";
import { promises as fs } from "node:fs";
import path from "node:path";
import yaml from "js-yaml";

const CONFIG_PATH =
  process.env.CONTROL_BOARD_CONFIG ||
  "/home/gadgetini/gadgetini/src/control_board/config.yaml";

async function loadConfig() {
  const raw = await fs.readFile(CONFIG_PATH, "utf8");
  const doc = yaml.load(raw) || {};
  return { raw, doc };
}

export async function GET() {
  try {
    const { doc } = await loadConfig();
    const fc = doc.fan_curve || {};
    return NextResponse.json({
      hysteresis_c: typeof fc.hysteresis_c === "number" ? fc.hysteresis_c : 1.0,
      stages: Array.isArray(fc.stages) ? fc.stages : [],
    });
  } catch (err) {
    return NextResponse.json(
      { error: err?.message || "Failed to read config.yaml" },
      { status: 500 }
    );
  }
}

function validate(body) {
  if (!body || typeof body !== "object") return "body must be an object";
  const { hysteresis_c, stages } = body;
  if (typeof hysteresis_c !== "number" || hysteresis_c < 0 || hysteresis_c > 10) {
    return "hysteresis_c must be a number in [0, 10]";
  }
  if (!Array.isArray(stages) || stages.length < 1 || stages.length > 16) {
    return "stages must be an array of length 1~16";
  }
  for (const [i, s] of stages.entries()) {
    if (!s || typeof s !== "object") return `stages[${i}] must be an object`;
    const u = s.until_outlet;
    const d = s.duty;
    if (u !== null && typeof u !== "number") {
      return `stages[${i}].until_outlet must be number or null`;
    }
    if (typeof d !== "number" || d < 0 || d > 1000) {
      return `stages[${i}].duty must be a number in [0, 1000]`;
    }
  }
  return null;
}

export async function PUT(req) {
  let body;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON" }, { status: 400 });
  }

  const err = validate(body);
  if (err) return NextResponse.json({ error: err }, { status: 400 });

  try {
    const { doc } = await loadConfig();
    doc.fan_curve = {
      hysteresis_c: body.hysteresis_c,
      stages: body.stages.map((s) => ({
        until_outlet: s.until_outlet,
        duty: s.duty,
      })),
    };

    const out = yaml.dump(doc, { lineWidth: 120, noRefs: true });
    // Atomic write: tmp file in same dir, then rename — partial reads from
    // control_board mtime watcher are avoided.
    const dir = path.dirname(CONFIG_PATH);
    const tmp = path.join(dir, `.config.yaml.${process.pid}.tmp`);
    await fs.writeFile(tmp, out, "utf8");
    await fs.rename(tmp, CONFIG_PATH);

    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json(
      { error: e?.message || "Failed to write config.yaml" },
      { status: 500 }
    );
  }
}
