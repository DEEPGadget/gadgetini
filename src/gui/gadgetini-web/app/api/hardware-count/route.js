import { getRedis } from "@/app/utils/redis";
import { NextResponse } from "next/server";

export async function GET() {
  try {
    const redis = getRedis();
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
