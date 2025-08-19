import { NextResponse } from "next/server";
import { exec } from "node:child_process";
import { promisify } from "node:util";

const execAsync = promisify(exec);

export async function POST() {
  try {
    execAsync("sudo /usr/bin/systemctl reboot").catch(() => {});
    return NextResponse.json(
      { ok: true, message: "Reboot scheduled." },
      { status: 202 }
    );
  } catch (err) {
    return NextResponse.json(
      { ok: false, error: err?.message || "Failed to execute reboot." },
      { status: 500 }
    );
  }
}
