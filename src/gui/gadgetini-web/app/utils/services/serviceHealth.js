// Shared service list + systemd/journald parsing for /api/services/health.
//
// Why parse message text instead of journald metadata: every Python service logs to
// stderr, so journald tags *every* record PRIORITY=3 regardless of real severity
// (data_crawler.py:22-25 installs a bare StreamHandler). The only reliable severity
// marker is the levelname inside MESSAGE. For the same reason `journalctl -p` is never
// used — it would keep all Python records and drop the display's stdout print()s.

// Unit candidates are tried in order; the first one that is `loaded` wins.
// redis is `redis-server.service` on Raspbian (with a redis.service alias) but a real
// `redis.service` on Rocky/RHEL, so both spellings are listed.
export const SERVICES = [
  { key: "data_crawler", units: ["data_crawler.service"] },
  { key: "sensor_exporter", units: ["sensor_exporter.service"] },
  { key: "display_pannel", units: ["display_pannel.service"] },
  { key: "usb_gadget", units: ["usb-gadget-up.service"] },
  { key: "redis", units: ["redis-server.service", "redis.service"] },
  { key: "prometheus", units: ["prometheus.service"] },
  { key: "grafana", units: ["grafana-server.service"] },
  { key: "nginx", units: ["nginx.service"] },
];

export const SHOW_PROPERTIES = [
  "Id",
  "LoadState",
  "ActiveState",
  "SubState",
  "Result",
  "ExecMainStatus",
  "UnitFileState",
];

export const JOURNAL_LINES = 40;
export const SUMMARY_MAX_CHARS = 180;

export function findService(key) {
  return SERVICES.find((s) => s.key === key) || null;
}

/** All unit names across every service, in SERVICES order (for one batched show call). */
export function allUnits() {
  return SERVICES.flatMap((s) => s.units);
}

/**
 * Parse `systemctl show u1 u2 ... --property=...` output into an ordered array of
 * property objects, one per requested unit.
 *
 * Blocks are returned in the order the units were asked for and are separated by a blank
 * line. They are matched positionally, not by `Id`, because systemd resolves an alias to
 * its canonical name: asking for `redis.service` yields `Id=redis-server.service`, so two
 * spellings of the same unit would collapse onto one key. A missing unit still produces a
 * block (`LoadState=not-found`) and exit status 0, so the count stays aligned.
 */
export function parseShowOutput(stdout) {
  return String(stdout)
    .split(/\n\s*\n/)
    .map((block) => {
      const props = {};
      for (const line of block.split("\n")) {
        const eq = line.indexOf("=");
        if (eq <= 0) continue;
        props[line.slice(0, eq)] = line.slice(eq + 1);
      }
      return props;
    })
    .filter((props) => Object.keys(props).length > 0);
}

/**
 * systemd state -> UI status.
 *   ok      : running, or a RemainAfterExit oneshot that finished cleanly
 *   pending : mid-transition
 *   error   : failed, or stopped while still enabled at boot
 *   unknown : unit not installed / unreadable
 */
export function classifyState(props) {
  if (!props || props.LoadState !== "loaded") return "unknown";
  switch (props.ActiveState) {
    case "active":
    case "reloading":
      return "ok";
    case "activating":
    case "deactivating":
      return "pending";
    case "failed":
      return "error";
    case "inactive":
      return props.UnitFileState === "enabled" ? "error" : "pending";
    default:
      return "unknown";
  }
}

/** Short systemd-side state text for a row, e.g. "active (running)" / "failed". */
export function stateText(props) {
  if (!props || props.LoadState !== "loaded") return "not-found";
  const active = props.ActiveState || "unknown";
  const sub = props.SubState;
  return sub && sub !== active ? `${active} (${sub})` : active;
}

// `2026-11-20 10:34:38,136 ERROR   pcb_driver: message` — asctime,millis + levelname + logger.
const PY_LOG_RE =
  /^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3}) (DEBUG|INFO|WARNING|ERROR|CRITICAL)\s+([\w.]+): ([\s\S]*)$/;

// data_crawler_host.py hand-rolls these prefixes; it has no logging config at all.
const PRINT_PREFIX_RE = /^\[(ERROR|WARN|WARNING|INFO)\]\s*([\s\S]*)$/;

// First-party loggers. Third-party ones (notably pymodbus.logging, which emits ERROR
// several times per second whenever the RS485 port is missing) are ranked below these
// when choosing the one-line summary, so real failures are not buried by that noise.
const FIRST_PARTY_LOGGER_RE =
  /^(data_crawler|pcb_driver|pcb_control|dlc_sensors|sensor_exporter|display|root)\b/;

const SEVERE = new Set(["ERROR", "CRITICAL"]);

/** journald MESSAGE is a byte array when the payload is not valid UTF-8. */
function messageToText(message) {
  if (typeof message === "string") return message;
  if (Array.isArray(message)) {
    try {
      return Buffer.from(message).toString("utf8");
    } catch {
      return "";
    }
  }
  return "";
}

function levelFromPriority(priority) {
  const n = Number(priority);
  if (!Number.isFinite(n)) return "INFO";
  if (n <= 3) return "ERROR";
  if (n === 4) return "WARNING";
  return "INFO";
}

/**
 * Turn `journalctl -o json` lines into records.
 *
 * A text line that does not match any known prefix is treated as a continuation of the
 * record before it (`log.exception` tracebacks arrive as separate journal entries), so
 * the summary stays one line while the detail keeps the whole traceback.
 */
export function parseJournal(stdout) {
  const records = [];
  for (const rawLine of String(stdout).split("\n")) {
    const trimmed = rawLine.trim();
    if (!trimmed) continue;
    let entry;
    try {
      entry = JSON.parse(trimmed);
    } catch {
      continue;
    }
    const text = messageToText(entry.MESSAGE);
    if (!text) continue;
    const identifier = entry.SYSLOG_IDENTIFIER || "";
    const priority = entry.PRIORITY;

    for (const line of text.split("\n")) {
      if (!line.trim() && records.length) {
        records[records.length - 1].detail.push(line);
        continue;
      }
      const py = PY_LOG_RE.exec(line);
      if (py) {
        records.push({
          level: py[2],
          logger: py[3],
          text: py[4],
          raw: line,
          detail: [],
        });
        continue;
      }
      const pr = PRINT_PREFIX_RE.exec(line);
      if (pr) {
        records.push({
          level: pr[1] === "WARN" ? "WARNING" : pr[1],
          logger: identifier || "print",
          text: pr[2],
          raw: line,
          detail: [],
        });
        continue;
      }
      if (identifier === "systemd") {
        records.push({
          level: levelFromPriority(priority),
          logger: "systemd",
          text: line,
          raw: line,
          detail: [],
        });
        continue;
      }
      if (records.length) {
        records[records.length - 1].detail.push(line);
        continue;
      }
      records.push({
        level: levelFromPriority(priority),
        logger: identifier || "unknown",
        text: line,
        raw: line,
        detail: [],
      });
    }
  }
  return records;
}

function lastMatch(records, predicate) {
  for (let i = records.length - 1; i >= 0; i -= 1) {
    if (predicate(records[i])) return records[i];
  }
  return null;
}

export function truncate(text, max = SUMMARY_MAX_CHARS) {
  const flat = String(text).replace(/\s+/g, " ").trim();
  return flat.length > max ? `${flat.slice(0, max - 1)}…` : flat;
}

/**
 * Build the one-line summary. Nothing in the codebase emits a ready-made summary, so it
 * is synthesised from the systemd result plus the most relevant log line, in order:
 *   1. first-party logger at ERROR/CRITICAL
 *   2. any logger at ERROR/CRITICAL (third-party fallback)
 *   3. first-party logger at WARNING
 *   4. systemd's own lifecycle message (best for failed oneshots)
 */
export function pickSummary(records, props) {
  const parts = [];
  const result = props?.Result;
  if (result && result !== "success") {
    const code = props?.ExecMainStatus;
    parts.push(code && code !== "0" ? `${result} (status ${code})` : result);
  }

  const chosen =
    lastMatch(
      records,
      (r) => SEVERE.has(r.level) && FIRST_PARTY_LOGGER_RE.test(r.logger),
    ) ||
    lastMatch(records, (r) => SEVERE.has(r.level) && r.logger !== "systemd") ||
    lastMatch(
      records,
      (r) => r.level === "WARNING" && FIRST_PARTY_LOGGER_RE.test(r.logger),
    ) ||
    lastMatch(records, (r) => r.logger === "systemd" && SEVERE.has(r.level));

  if (chosen) {
    const prefix =
      chosen.logger && chosen.logger !== "systemd" ? `${chosen.logger}: ` : "";
    parts.push(truncate(`${prefix}${chosen.text}`));
  }
  return parts;
}

/** Original journal text, tracebacks reattached, for the detail <pre>. */
export function detailLines(records) {
  return records.flatMap((r) => [r.raw, ...r.detail]);
}
