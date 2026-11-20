// GET /api/services/health              → status of every core service (+ a one-line
//                                         summary for the ones that are not healthy)
// GET /api/services/health?detail=<key> → raw journal tail for that one service
//
// Read-only by design. The cooling path (data_crawler) must not be controllable from an
// unauthenticated UI, so this route never starts, stops or restarts anything; it only
// runs `systemctl show` and `journalctl -u`, neither of which needs privilege.
//
// Unit names are never taken from the request: `detail` is matched against the
// hardcoded SERVICES allowlist and only the resolved unit name is passed to journalctl,
// always through execFile (no shell).
import { NextResponse } from "next/server";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { getRedis } from "../../../../lib/redis";
import {
  JOURNAL_LINES,
  SHOW_PROPERTIES,
  SERVICES,
  allUnits,
  classifyState,
  detailLines,
  findService,
  parseJournal,
  parseShowOutput,
  pickSummary,
  stateText,
} from "../../../utils/services/serviceHealth";

const execFileAsync = promisify(execFile);
const SYSTEMCTL = "/usr/bin/systemctl";
const JOURNALCTL = "/usr/bin/journalctl";
const EXEC_OPTS = { timeout: 5000, maxBuffer: 4 * 1024 * 1024 };

const SHOW_ARGS = [`--property=${SHOW_PROPERTIES.join(",")}`];

async function showUnits(units) {
  // One batched call. Blocks come back in the order requested, so they are matched
  // positionally (see parseShowOutput) — an alias resolves to its canonical Id and would
  // otherwise collide with the other spelling of the same unit.
  try {
    const { stdout } = await execFileAsync(
      SYSTEMCTL,
      ["show", ...units, ...SHOW_ARGS],
      EXEC_OPTS,
    );
    const blocks = parseShowOutput(stdout);
    if (blocks.length === units.length) return blocks;
  } catch {
    // fall through to per-unit calls
  }
  // Fallback: one call per unit, so a single bad unit cannot blank the whole panel.
  return Promise.all(
    units.map(async (unit) => {
      try {
        const { stdout } = await execFileAsync(
          SYSTEMCTL,
          ["show", unit, ...SHOW_ARGS],
          EXEC_OPTS,
        );
        return parseShowOutput(stdout)[0] || {};
      } catch {
        return {};
      }
    }),
  );
}

/** First candidate unit that is actually installed; otherwise the first candidate. */
function resolveService(service, units, blocks) {
  let fallback = null;
  for (const unit of service.units) {
    const props = blocks[units.indexOf(unit)] || {};
    if (props.LoadState === "loaded") return { unit: props.Id || unit, props };
    if (!fallback) fallback = { unit: props.Id || unit, props };
  }
  return fallback || { unit: service.units[0], props: {} };
}

async function readJournal(unit) {
  // No `-p` priority filter: every Python service logs to stderr so journald tags all of
  // its records PRIORITY=3, while the display's print()s land at PRIORITY=6. Any
  // priority filter would therefore drop one of the two.
  const { stdout } = await execFileAsync(
    JOURNALCTL,
    ["-u", unit, "-n", String(JOURNAL_LINES), "-o", "json", "--no-pager"],
    EXEC_OPTS,
  );
  return parseJournal(stdout);
}

async function getDetail(key) {
  const service = findService(key);
  if (!service) {
    return NextResponse.json({ ok: false, error: "Unknown service." }, { status: 400 });
  }
  const units = service.units;
  const blocks = await showUnits(units);
  const { unit } = resolveService(service, units, blocks);
  try {
    const records = await readJournal(unit);
    return NextResponse.json({ ok: true, key, unit, lines: detailLines(records) });
  } catch (err) {
    return NextResponse.json(
      { ok: true, key, unit, lines: [], error: err?.message || "Failed to read the journal." },
      { status: 200 },
    );
  }
}

// ── Logical health: systemd "active" is not the same as "doing its job" ──────────
// data_crawler stays active while the PCB is unreachable, and sensor_exporter stays
// active while serving nothing. These checks read the liveness keys the collector
// writes with a TTL (collector_ttl, comm_*; see src/exporter/redis_keys.py) and probe
// the exporter port, and downgrade a row to "degraded"/"error" with the real reason.
const EXPORTER_URL = "http://127.0.0.1:9003/metrics";

async function collectorHealth() {
  const r = getRedis();
  const [heartbeat, commStatus, fails, lastError] = await r.mget(
    "collector_ttl",
    "comm_status",
    "comm_consecutive_failures",
    "comm_last_error",
  );
  if (!heartbeat) {
    return { status: "error", state: "no heartbeat", summary: ["collector loop not reporting (collector_ttl absent)"] };
  }
  if (commStatus && commStatus !== "ok") {
    const summary = [`PCB ${commStatus} (${fails ?? "?"} consecutive failures)`];
    if (lastError) summary.push(lastError);
    return { status: "degraded", state: "PCB " + commStatus, summary };
  }
  return null;
}

async function exporterHealth() {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 2500);
  try {
    const res = await fetch(EXPORTER_URL, { signal: ctrl.signal, cache: "no-store" });
    if (!res.ok) {
      return { status: "degraded", state: `HTTP ${res.status}`, summary: [`exporter answered HTTP ${res.status} on :9003`] };
    }
    return null;
  } catch (err) {
    return { status: "degraded", state: "no response", summary: [`exporter not responding on :9003 (${err?.name === "AbortError" ? "timeout" : err?.message || err})`] };
  } finally {
    clearTimeout(timer);
  }
}

const LOGICAL_CHECKS = {
  data_crawler: collectorHealth,
  sensor_exporter: exporterHealth,
};

async function applyLogicalHealth(services) {
  await Promise.all(
    services.map(async (svc) => {
      const check = LOGICAL_CHECKS[svc.key];
      if (!check || svc.status !== "ok") return;
      try {
        const verdict = await check();
        if (verdict) Object.assign(svc, verdict);
      } catch (err) {
        // Redis down etc.: say so rather than pretend the service is fine.
        svc.status = "unknown";
        svc.state = "check failed";
        svc.summary = [`health check failed: ${err?.message || err}`];
      }
    }),
  );
}

async function getOverview() {
  const units = allUnits();
  const blocks = await showUnits(units);

  const resolved = SERVICES.map((service) => {
    const { unit, props } = resolveService(service, units, blocks);
    return { service, unit, props, status: classifyState(props) };
  });

  // The journal is only read for services that need explaining — a healthy box runs no
  // journalctl at all, which keeps the 15 s poll cheap.
  const summaries = await Promise.all(
    resolved.map(async ({ unit, props, status }) => {
      if (status === "ok") return [];
      try {
        return pickSummary(await readJournal(unit), props);
      } catch {
        return pickSummary([], props);
      }
    }),
  );

  const services = resolved.map(({ service, unit, props, status }, i) => ({
    key: service.key,
    unit,
    status,
    state: stateText(props),
    summary: summaries[i],
  }));

  await applyLogicalHealth(services);

  const total = services.length;
  const okCount = services.filter((s) => s.status === "ok").length;
  return NextResponse.json({
    ok: true,
    total,
    ok_count: okCount,
    unhealthy: total - okCount,
    services,
  });
}

export async function GET(request) {
  const detail = new URL(request.url).searchParams.get("detail");
  try {
    return detail ? await getDetail(detail) : await getOverview();
  } catch (err) {
    return NextResponse.json(
      { ok: false, error: err?.message || "Failed to read service status." },
      { status: 500 },
    );
  }
}
