import { NextResponse } from "next/server";

export async function POST(req) {
  try {
    const body = await req.json();
    const { ip } = body;

    if (!ip) {
      return NextResponse.json({ error: "IP not provided" }, { status: 400 });
    }

    const pingCommand = `ping -c 1 -W 1 ${ip}`;

    try {
      await exec(pingCommand);
      return NextResponse.json({ status: "online" });
    } catch (err) {
      return NextResponse.json({ status: "offline" });
    }
  } catch (error) {
    return NextResponse.json(
      { error: "Invalid request", detail: error.message },
      { status: 500 }
    );
  }
}
