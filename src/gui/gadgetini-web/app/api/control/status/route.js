// GET /api/control/status
// Returns:
//   service_active : control_board.service systemd 실행 여부
//   pcb_connected  : PCB Modbus 통신 OK 여부 (Redis comm_status === 'ok')
//   comm_status    : 'ok' / 'timeout' / 'disconnected' (raw Redis 값)
//   active         : (legacy) service_active && pcb_connected — UI에서 단일 boolean으로 사용
//   mode           : 현재 'auto' 고정 (Manual은 미구현)
//
// Service가 active여도 PCB가 분리/타임아웃되면 active=false. Redis stale data 영향 회피.
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
