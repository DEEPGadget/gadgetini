import { getRedis } from "../../../lib/redis";
import { NextResponse } from "next/server";

export async function GET() {
  try {
    const redis = getRedis();

    const hostAlive = await redis.exists("host_ttl");
    if (!hostAlive) {
      return NextResponse.json({ error: "host offline" }, { status: 503 });
    }

    const [gpuKeys, cpuKeys, nvmeKeys] = await Promise.all([
      redis.keys("gpu_temp_*"),
      redis.keys("cpu_temp_*"),
      redis.keys("nvme_*_temp"),
    ]);
    return NextResponse.json({
      gpuCount: gpuKeys.length,
      cpuCount: cpuKeys.length,
      nvmeCount: nvmeKeys.length,
    });
  } catch {
    return NextResponse.json({ error: "redis unavailable" }, { status: 503 });
  }
}
