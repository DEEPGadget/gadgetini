import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import os from "os";

const homeDir =
  os.platform() === "win32"
    ? "C:\\Users\\yjeon\\OneDrive\\바탕 화면\\gadgetini\\src\\display\\"
    : "/home/gadgetini/gadgetini/src/display";

const CONFIG_PATH = path.join(homeDir, "config.ini");

export async function GET() {
  try {
    const config = await fs.promises.readFile(CONFIG_PATH, "utf-8");
    const match = config.match(/^name\s*=\s*(.*)/m);
    const server = match ? match[1].trim() : "dg5r";
    return NextResponse.json({ server });
  } catch (error) {
    console.error("[server-select/GET]", error);
    return NextResponse.json({ error: "Failed to read config" }, { status: 500 });
  }
}

export async function POST(request) {
  try {
    const { server } = await request.json();
    let config = await fs.promises.readFile(CONFIG_PATH, "utf-8");
    config = config.replace(/^name\s*=\s*.*/m, `name=${server}`);
    await fs.promises.writeFile(CONFIG_PATH, config, "utf-8");
    return NextResponse.json({ server });
  } catch (error) {
    console.error("[server-select/POST]", error);
    return NextResponse.json({ error: "Failed to update config" }, { status: 500 });
  }
}
