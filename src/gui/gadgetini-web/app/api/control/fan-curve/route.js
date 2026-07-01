// GET  /api/control/fan-curve  → returns current fan_curve from config.yaml
// PUT  /api/control/fan-curve  → writes new fan_curve into config.yaml (atomic rename)
//
// Schema: linear interpolation between (min_temp, min_duty) and (max_temp, max_duty).
// duty unit is 0.1% (0~1000). control_board picks up the change via mtime polling within the next cycle (~1s).
import { NextResponse } from "next/server";
import { promises as fs } from "node:fs";
import path from "node:path";
import yaml from "js-yaml";

const CONFIG_PATH =
  process.env.CONTROL_BOARD_CONFIG ||
  "/home/gadgetini/gadgetini/src/exporter/pcb_config.yaml";

const DEFAULTS = { min_temp: 25, max_temp: 60, min_duty: 100, max_duty: 1000 };

async function loadConfig() {
  const raw = await fs.readFile(CONFIG_PATH, "utf8");
  const doc = yaml.load(raw) || {};
  return { raw, doc };
}

function num(v, fallback) {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

export async function GET() {
  try {
    const { doc } = await loadConfig();
    const fc = doc.fan_curve || {};
    return NextResponse.json({
      min_temp: num(fc.min_temp, DEFAULTS.min_temp),
      max_temp: num(fc.max_temp, DEFAULTS.max_temp),
      min_duty: num(fc.min_duty, DEFAULTS.min_duty),
      max_duty: num(fc.max_duty, DEFAULTS.max_duty),
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
  const { min_temp, max_temp, min_duty, max_duty } = body;
  for (const [k, v] of Object.entries({ min_temp, max_temp, min_duty, max_duty })) {
    if (typeof v !== "number" || !Number.isFinite(v)) return `${k} must be a finite number`;
  }
  if (min_temp < 0 || min_temp > 100) return "min_temp must be in [0, 100]";
  if (max_temp < 0 || max_temp > 100) return "max_temp must be in [0, 100]";
  if (min_temp >= max_temp) return "min_temp must be < max_temp";
  if (min_duty < 0 || min_duty > 1000) return "min_duty must be in [0, 1000]";
  if (max_duty < 0 || max_duty > 1000) return "max_duty must be in [0, 1000]";
  if (min_duty >= max_duty) return "min_duty must be < max_duty";
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
      min_temp: body.min_temp,
      max_temp: body.max_temp,
      min_duty: body.min_duty,
      max_duty: body.max_duty,
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
