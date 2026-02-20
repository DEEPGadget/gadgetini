import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import os from "os";

let homeDir;
if (os.platform() === "win32") {
  // at windows => TODO erase at final code
  homeDir = "C:\\Users\\yjeon\\OneDrive\\바탕 화면\\gadgetini\\src\\display\\";
} else {
  // at Linux
  homeDir = "/home/gadgetini/gadgetini/src/display";
}

// Read display config at 'config.ini' file and return
export async function GET() {
  try {
    const configPath = path.join(homeDir, "config.ini");

    if (!fs.existsSync(configPath)) {
      return NextResponse.json(
        { error: "Config file not found" },
        { status: 500 }
      );
    }

    const config = await fs.promises.readFile(configPath, "utf-8");

    const getConfigValue = (key) => {
      const match = config.match(new RegExp(`^${key}\\s*=\\s*(.*)`, "m"));
      return match ? match[1].trim() : null;
    };

    const configData = {
      orientation: getConfigValue("orientation") || "vertical",
      display: getConfigValue("display") === "on",
      coolant: getConfigValue("coolant") === "on",
      coolant_detail: getConfigValue("coolant_detail") === "on",
      chassis: getConfigValue("chassis") === "on",
      cpu: getConfigValue("cpu") === "on",
      gpu: getConfigValue("gpu") === "on",
      memory: getConfigValue("memory") === "on",
      coolant_daily: getConfigValue("coolant_daily") === "on",
      gpu_daily: getConfigValue("gpu_daily") === "on",
      cpu_daily: getConfigValue("cpu_daily") === "on",
      psu: getConfigValue("psu") === "on",
      leak: getConfigValue("leak") === "on",
      rotationTime: parseInt(getConfigValue("rotation_sec") || "5", 10),
    };

    return NextResponse.json(configData);
  } catch (error) {
    console.error("[display/GET]", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}

// Update display config at 'config.ini' file
export async function POST(request) {
  try {
    const displayMode = await request.json();

    const updateDisplayConfig = async (displayMode) => {
      const configPath = path.join(homeDir, "config.ini");
      let config = await fs.promises.readFile(configPath, "utf-8");

      const onOff = (v) => (v ? "on" : "off");
      config = config
        .replace(/^orientation\s*=\s*.*/m, `orientation=${displayMode.orientation}`)
        .replace(/^display\s*=\s*.*/m, `display=${onOff(displayMode.display)}`)
        .replace(/^coolant\s*=\s*.*/m, `coolant=${onOff(displayMode.coolant)}`)
        .replace(/^coolant_detail\s*=\s*.*/m, `coolant_detail=${onOff(displayMode.coolant_detail)}`)
        .replace(/^chassis\s*=\s*.*/m, `chassis=${onOff(displayMode.chassis)}`)
        .replace(/^cpu\s*=\s*.*/m, `cpu=${onOff(displayMode.cpu)}`)
        .replace(/^gpu\s*=\s*.*/m, `gpu=${onOff(displayMode.gpu)}`)
        .replace(/^memory\s*=\s*.*/m, `memory=${onOff(displayMode.memory)}`)
        .replace(/^coolant_daily\s*=\s*.*/m, `coolant_daily=${onOff(displayMode.coolant_daily)}`)
        .replace(/^gpu_daily\s*=\s*.*/m, `gpu_daily=${onOff(displayMode.gpu_daily)}`)
        .replace(/^cpu_daily\s*=\s*.*/m, `cpu_daily=${onOff(displayMode.cpu_daily)}`)
        .replace(/^psu\s*=\s*.*/m, `psu=${onOff(displayMode.psu)}`)
        .replace(/^leak\s*=\s*.*/m, `leak=${onOff(displayMode.leak)}`)
        .replace(/^rotation_sec\s*=\s*.*/m, `rotation_sec=${displayMode.rotationTime}`);

      await fs.promises.writeFile(configPath, config, "utf-8");
    };

    await updateDisplayConfig(displayMode);

    return NextResponse.json({ message: "Display config updated" });
  } catch (error) {
    console.error("[display/POST]", error);
    return NextResponse.json(
      { error: "Failed to update display modes." },
      { status: 500 }
    );
  }
}
