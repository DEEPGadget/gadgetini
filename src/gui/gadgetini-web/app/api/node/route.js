import { NextResponse } from "next/server";
import { exec as _exec } from "child_process";
import { promisify } from "util";

const exec = promisify(_exec);

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
      return NextResponse.json({ status: "active" });
    } catch (err) {
      return NextResponse.json({ status: "inactive" });
    }
  } catch (error) {
    return NextResponse.json(
      { error: "Invalid request", detail: error.message },
      { status: 500 }
    );
  }
}
