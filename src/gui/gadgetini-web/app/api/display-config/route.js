import fs from "fs";
import path from "path";

export async function POST(request) {
  try {
    const { displayMode } = await request.json();

    const updateDisplayConfig = async (displayMode) => {
      // Read existing config
      const homeDir = "/home/gadgetini/gadgetini/src/display";
      const configPath = path.join(homeDir, "config.ini");
      let config = await fs.promises.readFile(configPath, "utf-8");

      // Update the relevant lines in the config file
      config = config
        .replace(
          /^orientation\s*=\s*.*/m,
          `orientation=${displayMode.orientation}`
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
        .replace(/^time\s*=\s*.*/m, `time=${displayMode.rotationTime}`);

      // Write the updated config file back to the file system
      await fs.promises.writeFile(configPath, config, "utf-8");
    };

    // Update the local config file first
    await updateDisplayConfig(displayMode);

    return new Response(JSON.stringify({ message: "Modes updated" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("[display/POST]", error);
    return new Response(
      JSON.stringify({ error: "Failed to update display modes." }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
}

export async function GET() {
  try {
    const homeDir = "/home/gadgetini/gadgetini/src/display";
    const configPath = path.join(homeDir, "config.ini");

    // Check if file exist & read
    if (!fs.existsSync(configPath)) {
      return new Response(JSON.stringify({ error: "Config file not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    }
    const config = await fs.promises.readFile(configPath, "utf-8");

    // Returns the value of a given key from the config string
    const getConfigValue = (key) => {
      const match = config.match(new RegExp(`^${key}\\s*=\\s*(.*)`, "m"));
      return match ? match[1].trim() : null;
    };

    // JSON 형태로 변환
    const configData = {
      orientation: getConfigValue("orientation") || "vertical",
      chassis: getConfigValue("chassis") === "on",
      cpu: getConfigValue("cpu") === "on",
      gpu: getConfigValue("gpu") === "on",
      memory: getConfigValue("memory") === "on",
      psu: getConfigValue("psu") === "on",
      rotationTime: parseInt(getConfigValue("time") || "5", 10),
    };

    return new Response(JSON.stringify(configData), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("[display/GET]", error);
    return new Response(JSON.stringify({ error: "Failed to read config." }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
}
