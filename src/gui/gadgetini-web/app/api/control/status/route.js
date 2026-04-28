// GET /api/control/status
// Returns whether control_board.service is active and current mode.
// Mode is currently always "auto" — Manual is deferred (see plan).
import { NextResponse } from "next/server";
import { exec } from "node:child_process";
import { promisify } from "node:util";

const execAsync = promisify(exec);

export async function GET() {
  let active = false;
  try {
    // `systemctl is-active` exits 0 when active, 3 when inactive — both produce stdout.
    const { stdout } = await execAsync("systemctl is-active control_board");
    active = stdout.trim() === "active";
  } catch (err) {
    // Non-zero exit means inactive/failed/not-found — treat as not active.
    const out = (err?.stdout || "").trim();
    active = out === "active";
  }
  return NextResponse.json({ active, mode: "auto" });
}
