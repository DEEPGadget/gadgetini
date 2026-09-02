// GET  /api/control/fan-curve  → returns current fan_curve.sources from config.yaml
// PUT  /api/control/fan-curve  → writes new fan_curve.sources into config.yaml (atomic rename)
//
// Schema: array of sources, each with its own linear curve (min_temp, max_temp, min_duty, max_duty).
// duty unit is 0.1% (0~1000). control_board picks up the change via mtime polling within the next cycle (~1s).
// Sources are config-file-defined (key, label, redis_key are immutable via API);
// only min_temp/max_temp/min_duty/max_duty are user-editable.
//
// The standard/factory values live in the read-only src/exporter/pcb_defaults.yaml —
// see ./defaults/route.js for the Reset path.
import { NextResponse } from "next/server";
import { getFanCurveDefaults } from "../../../utils/control/getFanCurveDefaults";
import { applyCurveSources, loadConfig, validateSources } from "../../../utils/control/fanCurveConfig";

export async function GET() {
  try {
    const doc = await loadConfig();
    const fc = doc.fan_curve || {};
    if (Array.isArray(fc.sources) && fc.sources.length > 0) {
      return NextResponse.json({ sources: fc.sources });
    }
    // config.yaml has no curve configured yet — fall back to the standard settings.
    const { sources } = await getFanCurveDefaults();
    return NextResponse.json({ sources });
  } catch (err) {
    return NextResponse.json(
      { error: err?.message || "Failed to read config.yaml" },
      { status: 500 }
    );
  }
}

export async function PUT(req) {
  let body;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON" }, { status: 400 });
  }

  if (!body || typeof body !== "object") {
    return NextResponse.json({ error: "body must be an object" }, { status: 400 });
  }
  const err = validateSources(body.sources);
  if (err) return NextResponse.json({ error: err }, { status: 400 });

  try {
    await applyCurveSources(body.sources);
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json(
      { error: e?.message || "Failed to write config.yaml" },
      { status: 500 }
    );
  }
}
