// GET /api/control/status
// Returns:
//   service_active : whether control_board.service systemd unit is running
//   pcb_connected  : whether PCB Modbus communication is OK (Redis comm_status === 'ok')
//   comm_status    : 'ok' / 'timeout' / 'disconnected' (raw Redis value)
//   active         : (legacy) service_active && pcb_connected — used as a single boolean in the UI
//   mode           : currently fixed to 'auto' (Manual not implemented yet)
//
// Even if the service is active, active=false when the PCB is detached/timed out. Avoids stale Redis data influence.
import { NextResponse } from "next/server";
import { exec } from "node:child_process";
import { promisify } from "node:util";
import { getRedis } from "../../../../lib/redis";

const execAsync = promisify(exec);

async function checkServiceActive() {
  try {
    const { stdout } = await execAsync("systemctl is-active control_board");
    return stdout.trim() === "active";
  } catch (err) {
    return (err?.stdout || "").trim() === "active";
  }
}

async function getCommStatus() {
  try {
    const v = await getRedis().get("comm_status");
    return v || "unknown";
  } catch {
    return "unknown";
  }
}

export async function GET() {
  const [serviceActive, commStatus] = await Promise.all([
    checkServiceActive(),
    getCommStatus(),
  ]);
  const pcbConnected = commStatus === "ok";
  return NextResponse.json({
    active: serviceActive && pcbConnected,
    service_active: serviceActive,
    pcb_connected: pcbConnected,
    comm_status: commStatus,
    mode: "auto",
  });
}
