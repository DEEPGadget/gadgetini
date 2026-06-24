// GET /api/control/mode — get current control_mode
// PUT /api/control/mode — set control_mode ('auto' or 'manual')
import { NextResponse } from "next/server";
import { getRedis } from "../../../../lib/redis";

export async function GET() {
  try {
    const mode = await getRedis().get("control_mode");
    return NextResponse.json({
      mode: (mode === "manual" ? "manual" : "auto"),
    });
  } catch (err) {
    return NextResponse.json(
      { error: err?.message || "Failed to get control mode" },
      { status: 500 }
    );
  }
}

export async function PUT(request) {
  try {
    const body = await request.json();
    const { mode } = body;

    if (mode !== "auto" && mode !== "manual") {
      return NextResponse.json(
        { error: "mode must be 'auto' or 'manual'" },
        { status: 400 }
      );
    }

    await getRedis().set("control_mode", mode);
    return NextResponse.json({
      success: true,
      mode: mode,
    });
  } catch (err) {
    return NextResponse.json(
      { error: err?.message || "Failed to set control mode" },
      { status: 500 }
    );
  }
}
