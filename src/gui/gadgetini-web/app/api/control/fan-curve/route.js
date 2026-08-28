// GET  /api/control/fan-curve  → returns current fan_curve.sources from config.yaml
// PUT  /api/control/fan-curve  → writes new fan_curve.sources into config.yaml (atomic rename)
//
// Schema: array of sources, each with its own linear curve (min_temp, max_temp, min_duty, max_duty).
// duty unit is 0.1% (0~1000). control_board picks up the change via mtime polling within the next cycle (~1s).
// Sources are config-file-defined (key, label, redis_key are immutable via API);
// only min_temp/max_temp/min_duty/max_duty are user-editable.
import { NextResponse } from "next/server";
import { promises as fs } from "node:fs";
import path from "node:path";
import yaml from "js-yaml";

const CONFIG_PATH =
  process.env.CONTROL_BOARD_CONFIG ||
  "/home/gadgetini/gadgetini/src/exporter/pcb_config.yaml";

// Curve anchors: min_temp = 27C, the ASHRAE recommended upper bound for a data
// centre's controlled envelope (18~27C) — while the room holds its setpoint the
// fans sit at the 8% idle floor. max_temp = the Critical threshold from
// src/gui/grafana/common/threshold.md (coolant outlet >65C, chassis >50C), where
// the fans reach 100%. Idle is anchored to ambient, not to the Normal ceiling:
// anchoring at Normal would leave the whole Normal band with no ramp at all.
const DEFAULT_SOURCES = [
  { key: "coolant", label: "Coolant Outlet Temp", redis_key: "coolant_temp_outlet1", min_temp: 27, max_temp: 65, min_duty: 80, max_duty: 1000 },
  { key: "chassis", label: "Chassis Temperature", redis_key: "air_temp", min_temp: 27, max_temp: 50, min_duty: 80, max_duty: 1000 },
];

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
    const sources = Array.isArray(fc.sources) && fc.sources.length > 0
      ? fc.sources
      : DEFAULT_SOURCES;
    return NextResponse.json({ sources });
  } catch (err) {
    return NextResponse.json(
      { error: err?.message || "Failed to read config.yaml" },
      { status: 500 }
    );
  }
}

function validateSource(source) {
  if (!source || typeof source !== "object") return "each source must be an object";
  const { key, min_temp, max_temp, min_duty, max_duty } = source;
  if (typeof key !== "string") return "source.key must be a string";
  for (const [k, v] of Object.entries({ min_temp, max_temp, min_duty, max_duty })) {
    if (typeof v !== "number" || !Number.isFinite(v)) return `source.${k} must be a finite number`;
  }
  if (min_temp < 0 || min_temp > 100) return "source.min_temp must be in [0, 100]";
  if (max_temp < 0 || max_temp > 100) return "source.max_temp must be in [0, 100]";
  if (min_temp >= max_temp) return "source.min_temp must be < max_temp";
  if (min_duty < 0 || min_duty > 1000) return "source.min_duty must be in [0, 1000]";
  if (max_duty < 0 || max_duty > 1000) return "source.max_duty must be in [0, 1000]";
  if (min_duty >= max_duty) return "source.min_duty must be < max_duty";
  return null;
}

function validate(body) {
  if (!body || typeof body !== "object") return "body must be an object";
  const { sources } = body;
  if (!Array.isArray(sources) || sources.length === 0) return "sources must be a non-empty array";
  for (const src of sources) {
    const err = validateSource(src);
    if (err) return err;
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
    const currentSources = (doc.fan_curve?.sources || []).reduce((m, s) => {
      m[s.key] = s;
      return m;
    }, {});

    const updatedSources = body.sources.map((src) => {
      const existing = currentSources[src.key];
      if (!existing) {
        throw new Error(`unknown source key: ${src.key}`);
      }
      return {
        ...existing,
        min_temp: src.min_temp,
        max_temp: src.max_temp,
        min_duty: src.min_duty,
        max_duty: src.max_duty,
      };
    });

    if (!doc.fan_curve) {
      doc.fan_curve = {};
    }
    doc.fan_curve.sources = updatedSources;

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
