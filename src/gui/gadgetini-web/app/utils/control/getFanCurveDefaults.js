// Reads the standard (factory) fan-curve settings from the read-only
// pcb_defaults.yaml. Nothing in the web app ever writes to that file — it is the
// reference the "Restore standard settings" button loads from.
//
// If the file is missing or unparsable the built-in constant below is used, so a
// broken/absent defaults file can never take the settings UI down.
import { promises as fs } from "node:fs";
import yaml from "js-yaml";

const DEFAULTS_PATH =
  process.env.CONTROL_BOARD_DEFAULTS ||
  "/home/gadgetini/gadgetini/src/exporter/pcb_defaults.yaml";

// Last-resort fallback; keep in sync with pcb_defaults.yaml.
const BUILTIN_SOURCES = [
  { key: "coolant", label: "Coolant Outlet Temp", redis_key: "coolant_temp_outlet1", min_temp: 27, max_temp: 65, min_duty: 80, max_duty: 1000 },
  { key: "chassis", label: "Chassis Temperature", redis_key: "air_temp", min_temp: 27, max_temp: 50, min_duty: 80, max_duty: 1000 },
];

function isUsableSource(s) {
  return (
    s &&
    typeof s === "object" &&
    typeof s.key === "string" &&
    ["min_temp", "max_temp", "min_duty", "max_duty"].every(
      (f) => typeof s[f] === "number" && Number.isFinite(s[f])
    )
  );
}

// Returns { sources, source: "file" | "builtin" }.
export async function getFanCurveDefaults() {
  try {
    const raw = await fs.readFile(DEFAULTS_PATH, "utf8");
    const doc = yaml.load(raw) || {};
    const sources = doc.fan_curve?.sources;
    if (Array.isArray(sources) && sources.length > 0 && sources.every(isUsableSource)) {
      return { sources, source: "file" };
    }
  } catch {
    // fall through to the built-in
  }
  return { sources: BUILTIN_SOURCES, source: "builtin" };
}
