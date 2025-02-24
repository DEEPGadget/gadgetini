import fs from "fs";
import path from "path";

export async function POST(request) {
  try {
    const { status, rotationTime } = await request.json();

    const updateLocalConfig = async (status, rotationTime) => {
      const homeDir = "/home/gadgetini/gadgetini/src/display";
      const configPath = path.join(homeDir, "config.ini"); // Path to config.ini in home directory
      console.log(status);
      // Read the existing config file
      let config = await fs.promises.readFile(configPath, "utf-8");

      // Update the relevant lines in the config file
      config = config
        .replace(/^orientation\s*=\s*.*/m, `orientation=${status.orientation}`)
        .replace(
          /^chassis\s*=\s*.*/m,
          `chassis=${status.chassis ? "on" : "off"}`
        )
        .replace(/^cpu\s*=\s*.*/m, `cpu=${status.cpu ? "on" : "off"}`)
        .replace(/^gpu\s*=\s*.*/m, `gpu=${status.gpu ? "on" : "off"}`)
        .replace(/^memory\s*=\s*.*/m, `memory=${status.memory ? "on" : "off"}`)
        .replace(/^psu\s*=\s*.*/m, `psu=${status.psu ? "on" : "off"}`)
        .replace(/^time\s*=\s*.*/m, `time=${rotationTime}`);

      // Write the updated config file back to the file system
      await fs.promises.writeFile(configPath, config, "utf-8");
    };

    // Update the local config file first
    await updateLocalConfig(status, rotationTime);

    return new Response(JSON.stringify({ message: "Modes updated" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("Error updating modes:", error);
    return new Response(JSON.stringify({ error: "Failed to update modes." }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
}

export async function GET() {
  try {
    const homeDir = "/home/gadgetini/gadgetini/src/display";
    const configPath = path.join(homeDir, "config.ini");

    // 파일 존재 여부 확인
    if (!fs.existsSync(configPath)) {
      return new Response(JSON.stringify({ error: "Config file not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    }

    // 파일 읽기
    const configContent = await fs.promises.readFile(configPath, "utf-8");

    // 정규식을 이용해 각 설정 값을 추출
    const getConfigValue = (key) => {
      const match = configContent.match(
        new RegExp(`^${key}\\s*=\\s*(.*)`, "m")
      );
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
    console.error("Error reading config:", error);
    return new Response(JSON.stringify({ error: "Failed to read config." }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
}
