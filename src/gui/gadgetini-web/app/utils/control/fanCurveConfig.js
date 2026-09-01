// Shared read/write helpers for the fan_curve section of pcb_config.yaml.
// Used by PUT /api/control/fan-curve (operator edits) and by
// POST /api/control/fan-curve/defaults (restore standard settings).
import { promises as fs } from "node:fs";
import path from "node:path";
import yaml from "js-yaml";

export const CONFIG_PATH =
  process.env.CONTROL_BOARD_CONFIG ||
  "/home/gadgetini/gadgetini/src/exporter/pcb_config.yaml";

export async function loadConfig() {
  const raw = await fs.readFile(CONFIG_PATH, "utf8");
  return yaml.load(raw) || {};
}

export function validateSource(source) {
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

export function validateSources(sources) {
  if (!Array.isArray(sources) || sources.length === 0) return "sources must be a non-empty array";
  for (const src of sources) {
    const err = validateSource(src);
    if (err) return err;
  }
  return null;
}

// Merges the four tunable fields of each incoming source into the config's
// existing sources (key/label/redis_key stay config-owned) and writes the file.
// Returns the sources as they were written.
export async function applyCurveSources(incoming) {
  const doc = await loadConfig();
  const currentSources = (doc.fan_curve?.sources || []).reduce((m, s) => {
    m[s.key] = s;
    return m;
  }, {});

  const updatedSources = incoming.map((src) => {
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

  return updatedSources;
}
