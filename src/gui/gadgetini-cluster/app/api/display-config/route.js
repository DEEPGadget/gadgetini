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
      orientation: getConfigValue("orientation") || "horizontal",
      display: getConfigValue("display") !== "off",
      chassis: getConfigValue("chassis") === "on",
      cpu: getConfigValue("cpu") === "on",
      gpu: getConfigValue("gpu") === "on",
      memory: getConfigValue("memory") === "on",
      psu: getConfigValue("psu") === "on",
      coolant: getConfigValue("coolant") === "on",
      coolantDetail: getConfigValue("coolant_detail") === "on",
      coolantDaily: getConfigValue("coolant_daily") === "on",
      gpuDaily: getConfigValue("gpu_daily") === "on",
      cpuDaily: getConfigValue("cpu_daily") === "on",
      leak: getConfigValue("leak") === "on",
      rotationTime: parseInt(getConfigValue("rotation_sec") || "7", 10),
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

      config = config
        .replace(
          /^orientation\s*=\s*.*/m,
          `orientation=${displayMode.orientation}`
        )
        .replace(
          /^display\s*=\s*.*/m,
          `display=${displayMode.display ? "on" : "off"}`
        )
        .replace(
          /^chassis\s*=\s*.*/m,
          `chassis=${displayMode.chassis ? "on" : "off"}`
        )
        .replace(/^cpu\s*=\s*.*/m, `cpu=${displayMode.cpu ? "on" : "off"}`)
        .replace(/^gpu\s*=\s*.*/m, `gpu=${displayMode.gpu ? "on" : "off"}`)
        .replace(
          /^memory\s*=\s*.*/m,
          `memory=${displayMode.memory ? "on" : "off"}`
        )
        .replace(/^psu\s*=\s*.*/m, `psu=${displayMode.psu ? "on" : "off"}`)
        .replace(
          /^coolant\s*=\s*.*/m,
          `coolant=${displayMode.coolant ? "on" : "off"}`
        )
        .replace(
          /^coolant_detail\s*=\s*.*/m,
          `coolant_detail=${displayMode.coolantDetail ? "on" : "off"}`
        )
        .replace(
          /^coolant_daily\s*=\s*.*/m,
          `coolant_daily=${displayMode.coolantDaily ? "on" : "off"}`
        )
        .replace(
          /^gpu_daily\s*=\s*.*/m,
          `gpu_daily=${displayMode.gpuDaily ? "on" : "off"}`
        )
        .replace(
          /^cpu_daily\s*=\s*.*/m,
          `cpu_daily=${displayMode.cpuDaily ? "on" : "off"}`
        )
        .replace(
          /^leak\s*=\s*.*/m,
          `leak=${displayMode.leak ? "on" : "off"}`
        )
        .replace(
          /^rotation_sec\s*=\s*.*/m,
          `rotation_sec=${displayMode.rotationTime}`
        );

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
