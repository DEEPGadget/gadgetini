// GET /api/control/status
// Returns:
//   pcb_connected  : whether PCB Modbus communication is OK (Redis comm_status === 'ok')
//   comm_status    : 'ok' / 'timeout' / 'disconnected' (raw Redis value)
//   active         : whether controls are enabled (pcb_connected && mode is enabled)
//   mode           : 'auto' or 'manual'
import { NextResponse } from "next/server";
import { getRedis } from "../../../../lib/redis";

async function getCommStatus() {
  try {
    const v = await getRedis().get("comm_status");
    return v || "unknown";
  } catch {
    return "unknown";
  }
}

async function getControlMode() {
  try {
    const v = await getRedis().get("control_mode");
    return (v === "manual" ? "manual" : "auto");
  } catch {
    return "auto";
  }
}

export async function GET() {
  const [commStatus, controlMode] = await Promise.all([
    getCommStatus(),
    getControlMode(),
  ]);
  const pcbConnected = commStatus === "ok";
  return NextResponse.json({
    pcb_connected: pcbConnected,
    comm_status: commStatus,
    mode: controlMode,
    active: pcbConnected && controlMode !== "disabled",
  });
}
