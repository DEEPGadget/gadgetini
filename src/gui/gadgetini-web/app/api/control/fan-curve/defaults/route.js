// GET  /api/control/fan-curve/defaults  → the standard (factory) fan_curve sources
// POST /api/control/fan-curve/defaults  → writes those standard values into pcb_config.yaml
//
// The standard values live in the read-only src/exporter/pcb_defaults.yaml. This
// route only ever READS that file; there is deliberately no handler that writes
// it, so "standard" cannot be redefined from the web UI.
//
// POST is the Reset button's one-shot path: the operator confirms, and the curve
// is restored and saved in a single request — no separate Save click needed.
// control_board picks up the change via mtime polling within the next cycle (~1s).
import { NextResponse } from "next/server";
import { getFanCurveDefaults } from "../../../../utils/control/getFanCurveDefaults";
import { applyCurveSources, validateSources } from "../../../../utils/control/fanCurveConfig";

export async function GET() {
  const { sources, source } = await getFanCurveDefaults();
  return NextResponse.json({ sources, defaults_source: source });
}

export async function POST() {
  try {
    const { sources } = await getFanCurveDefaults();

    // The defaults file is operator-editable on disk; validate before it reaches config.
    const err = validateSources(sources);
    if (err) {
      return NextResponse.json(
        { error: `invalid standard settings: ${err}` },
        { status: 500 }
      );
    }

    const applied = await applyCurveSources(sources);
    return NextResponse.json({ ok: true, sources: applied });
  } catch (e) {
    return NextResponse.json(
      { error: e?.message || "Failed to restore standard settings" },
      { status: 500 }
    );
  }
}
