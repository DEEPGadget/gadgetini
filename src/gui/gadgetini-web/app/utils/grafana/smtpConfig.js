// Read / rewrite the [smtp] section of /etc/grafana/grafana.ini.
//
// Only the keys listed in SMTP_KEYS are touched, and only inside [smtp] — the rest of the
// (≈78KB, package-owned) file is preserved byte for byte. For each key the active line is
// replaced; failing that the commented default (";key = ...") is uncommented in place;
// failing that the key is appended to the end of the section.
//
// The file is root:grafana 0640 (it holds the SMTP password), so the write keeps the
// original owner/mode, goes through a temp file + rename, and leaves the previous version
// at grafana.ini.bak so a Grafana start failure can be rolled back.
import fs from "fs";
import path from "path";

export const GRAFANA_INI = "/etc/grafana/grafana.ini";
export const GRAFANA_INI_BAK = `${GRAFANA_INI}.bak`;

export const SMTP_KEYS = [
  "enabled",
  "host",
  "user",
  "password",
  "from_address",
  "from_name",
  "startTLS_policy",
];

export const STARTTLS_POLICIES = ["MandatoryStartTLS", "OpportunisticStartTLS", "NoStartTLS"];

const SECTION_RE = /^\s*\[([^\]]+)\]\s*$/;
const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const keyRe = (key, commented) =>
  new RegExp(`^\\s*${commented ? "[;#]\\s*" : ""}${escapeRe(key)}\\s*=`);

// [start, end) line indices of the [smtp] section body (header excluded).
function findSmtpSection(lines) {
  const start = lines.findIndex((l) => SECTION_RE.exec(l)?.[1] === "smtp");
  if (start < 0) return null;
  let end = lines.findIndex((l, i) => i > start && SECTION_RE.test(l));
  if (end < 0) end = lines.length;
  return { start: start + 1, end };
}

function unquote(v) {
  if (v.length >= 6 && v.startsWith('"""') && v.endsWith('"""')) return v.slice(3, -3);
  if (v.length >= 2 && v.startsWith('"') && v.endsWith('"')) return v.slice(1, -1);
  return v;
}

// Grafana (go-ini) treats # and ; as comment starts, so such values must be wrapped in
// triple quotes. The password is always wrapped so its content never matters.
function quote(key, v) {
  if (v === "") return v;
  if (key === "password" || /[#;"]|^\s|\s$/.test(v)) return `"""${v}"""`;
  return v;
}

export function parseSmtp(text) {
  const lines = text.split("\n");
  const sec = findSmtpSection(lines);
  const out = {};
  if (!sec) return out;
  for (const key of SMTP_KEYS) {
    const re = keyRe(key, false);
    const line = lines.slice(sec.start, sec.end).find((l) => re.test(l));
    if (line !== undefined) out[key] = unquote(line.slice(line.indexOf("=") + 1).trim());
  }
  return out;
}

export function applySmtp(text, values) {
  const lines = text.split("\n");
  let sec = findSmtpSection(lines);
  if (!sec) {
    lines.push("", "[smtp]");
    sec = { start: lines.length, end: lines.length };
  }

  for (const key of SMTP_KEYS) {
    if (values[key] === undefined) continue;
    const newLine = `${key} = ${quote(key, String(values[key]))}`;
    const body = lines.slice(sec.start, sec.end);
    let idx = body.findIndex((l) => keyRe(key, false).test(l));
    if (idx < 0) idx = body.findIndex((l) => keyRe(key, true).test(l));
    if (idx >= 0) {
      lines[sec.start + idx] = newLine;
    } else {
      // Append after the last non-blank line of the section.
      let at = sec.end;
      while (at > sec.start && lines[at - 1].trim() === "") at--;
      lines.splice(at, 0, newLine);
      sec.end++;
    }
  }
  return lines.join("\n");
}

// Package-shipped copy of the default grafana.ini (world-readable). Its [smtp] lines are
// what a fresh install has, so a reset writes them back verbatim.
const SAMPLE_INI = "/usr/share/grafana/conf/sample.ini";
// Grafana 11.2 [smtp] defaults, used only if sample.ini cannot be read.
const FALLBACK_DEFAULT_LINES = {
  enabled: ";enabled = false",
  host: ";host = localhost:25",
  user: ";user =",
  password: ";password =",
  from_address: ";from_address = admin@grafana.localhost",
  from_name: ";from_name = Grafana",
  startTLS_policy: ";startTLS_policy = NoStartTLS",
};

export async function readDefaultSmtpLines() {
  const out = { ...FALLBACK_DEFAULT_LINES };
  try {
    const lines = (await fs.promises.readFile(SAMPLE_INI, "utf-8")).split("\n");
    const sec = findSmtpSection(lines);
    if (sec) {
      for (const key of SMTP_KEYS) {
        const line = lines.slice(sec.start, sec.end).find((l) => keyRe(key, true).test(l));
        if (line !== undefined) out[key] = line.trimEnd();
      }
    }
  } catch {
    // keep the fallback lines
  }
  return out;
}

// Put every active SMTP_KEYS line in [smtp] back to its commented default, so the section
// reads exactly as after installation (Grafana then uses its built-in defaults).
export function resetSmtp(text, defaultLines) {
  const lines = text.split("\n");
  const sec = findSmtpSection(lines);
  if (!sec) return text;
  for (const key of SMTP_KEYS) {
    const re = keyRe(key, false);
    for (let i = sec.start; i < sec.end; i++) {
      if (re.test(lines[i])) lines[i] = defaultLines[key];
    }
  }
  return lines.join("\n");
}

export async function readGrafanaIni() {
  return fs.promises.readFile(GRAFANA_INI, "utf-8");
}

export async function writeGrafanaIni(text) {
  const st = await fs.promises.stat(GRAFANA_INI);
  const tmp = path.join(path.dirname(GRAFANA_INI), `.grafana.ini.${process.pid}.tmp`);
  await fs.promises.copyFile(GRAFANA_INI, GRAFANA_INI_BAK);
  await fs.promises.chown(GRAFANA_INI_BAK, st.uid, st.gid);
  await fs.promises.chmod(GRAFANA_INI_BAK, st.mode & 0o777);
  try {
    await fs.promises.writeFile(tmp, text, { encoding: "utf-8", mode: st.mode & 0o777 });
    await fs.promises.chown(tmp, st.uid, st.gid);
    await fs.promises.chmod(tmp, st.mode & 0o777);
    await fs.promises.rename(tmp, GRAFANA_INI);
  } catch (err) {
    await fs.promises.rm(tmp, { force: true });
    throw err;
  }
}

export async function restoreGrafanaIniBackup() {
  await fs.promises.copyFile(GRAFANA_INI_BAK, GRAFANA_INI);
}

const HOST_RE = /^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?:(\d{1,5})$/;
const EMAIL_RE = /^[^\s@"<>]+@[^\s@"<>]+\.[^\s@"<>]+$/;
// Newlines would inject extra ini lines; other control chars have no business here.
const CTRL_RE = /[\x00-\x1f\x7f]/;

// Returns an error string, or null when `v` (the full incoming form) is valid.
// `v.password` may be "" meaning "keep the stored one" — the route decides if that's allowed.
export function validateSmtp(v) {
  if (typeof v.enabled !== "boolean") return "enabled must be a boolean";
  for (const k of ["host", "user", "password", "from_address", "from_name", "startTLS_policy"]) {
    if (typeof v[k] !== "string") return `${k} must be a string`;
    if (CTRL_RE.test(v[k])) return `${k} contains invalid characters`;
  }
  if (v.password.includes('"""')) return 'password must not contain """';
  if (!v.enabled) return null; // disabling: keep whatever is there, no further checks

  const m = HOST_RE.exec(v.host.trim());
  if (!m || Number(m[2]) < 1 || Number(m[2]) > 65535)
    return "host must be in the form server:port (e.g. smtp.example.com:587)";
  if (!v.user.trim()) return "user is required";
  if (!EMAIL_RE.test(v.from_address.trim())) return "from_address must be a valid email address";
  if (!v.from_name.trim()) return "from_name is required";
  if (!STARTTLS_POLICIES.includes(v.startTLS_policy))
    return `startTLS_policy must be one of ${STARTTLS_POLICIES.join(", ")}`;
  return null;
}
