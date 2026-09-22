// GET    /api/grafana/smtp → current [smtp] settings of grafana.ini (password is never returned)
// PUT    /api/grafana/smtp → validate, write [smtp], restart grafana-server (rollback on failure)
// DELETE /api/grafana/smtp → reset [smtp] to the installation defaults (commented lines from
//                             the packaged sample.ini); wipes the stored user/password
//
// Password handling: an empty password in PUT means "keep the stored one", but only while
// host and user are unchanged — otherwise the stored credential could be redirected to a
// different server by anyone who can reach this (unauthenticated) UI.
import { NextResponse } from "next/server";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import {
  applySmtp,
  parseSmtp,
  readDefaultSmtpLines,
  readGrafanaIni,
  resetSmtp,
  restoreGrafanaIniBackup,
  validateSmtp,
  writeGrafanaIni,
} from "../../../utils/grafana/smtpConfig";

const execFileAsync = promisify(execFile);
const SYSTEMCTL = "/usr/bin/systemctl";

let busy = false;

async function restartGrafana() {
  await execFileAsync("sudo", [SYSTEMCTL, "restart", "grafana-server"], { timeout: 60000 });
  // A bad config can make grafana exit a moment after systemd reports it started.
  await new Promise((r) => setTimeout(r, 3000));
  await execFileAsync(SYSTEMCTL, ["is-active", "--quiet", "grafana-server"]);
}

// Write + restart; if grafana doesn't come back, put the previous file back and restart again.
async function applyAndRestart(text) {
  await writeGrafanaIni(text);
  try {
    await restartGrafana();
  } catch (err) {
    await restoreGrafanaIniBackup();
    await restartGrafana().catch(() => {});
    throw new Error(`grafana-server failed to restart with the new settings; previous settings restored (${err?.message || err})`);
  }
}

async function withLock(fn) {
  if (busy) {
    return NextResponse.json({ error: "Another update is in progress" }, { status: 409 });
  }
  busy = true;
  try {
    return await fn();
  } finally {
    busy = false;
  }
}

export async function GET() {
  try {
    const cur = parseSmtp(await readGrafanaIni());
    return NextResponse.json({
      enabled: cur.enabled === "true",
      host: cur.host ?? "",
      user: cur.user ?? "",
      passwordSet: !!cur.password,
      from_address: cur.from_address ?? "",
      from_name: cur.from_name ?? "",
      startTLS_policy: cur.startTLS_policy || "MandatoryStartTLS",
    });
  } catch (err) {
    console.error("[grafana/smtp GET]", err);
    return NextResponse.json({ error: err?.message || "Failed to read grafana.ini" }, { status: 500 });
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

  const v = {
    enabled: body.enabled,
    host: body.host ?? "",
    user: body.user ?? "",
    password: body.password ?? "",
    from_address: body.from_address ?? "",
    from_name: body.from_name ?? "",
    startTLS_policy: body.startTLS_policy ?? "",
  };
  const err = validateSmtp(v);
  if (err) return NextResponse.json({ error: err }, { status: 400 });

  return withLock(async () => {
    try {
      const text = await readGrafanaIni();
      const cur = parseSmtp(text);

      let values;
      if (!v.enabled) {
        values = { enabled: "false" };
      } else {
        values = {
          enabled: "true",
          host: v.host.trim(),
          user: v.user.trim(),
          from_address: v.from_address.trim(),
          from_name: v.from_name.trim(),
          startTLS_policy: v.startTLS_policy,
        };
        if (v.password) {
          values.password = v.password;
        } else {
          const sameTarget = values.host === (cur.host ?? "") && values.user === (cur.user ?? "");
          if (!cur.password || !sameTarget) {
            return NextResponse.json(
              { error: "password is required (new setup, or host/user changed)" },
              { status: 400 }
            );
          }
        }
      }

      await applyAndRestart(applySmtp(text, values));
      return NextResponse.json({ ok: true });
    } catch (e) {
      console.error("[grafana/smtp PUT]", e);
      return NextResponse.json({ error: e?.message || "Failed to update grafana.ini" }, { status: 500 });
    }
  });
}

export async function DELETE() {
  return withLock(async () => {
    try {
      const text = await readGrafanaIni();
      await applyAndRestart(resetSmtp(text, await readDefaultSmtpLines()));
      return NextResponse.json({ ok: true });
    } catch (e) {
      console.error("[grafana/smtp DELETE]", e);
      return NextResponse.json({ error: e?.message || "Failed to update grafana.ini" }, { status: 500 });
    }
  });
}
