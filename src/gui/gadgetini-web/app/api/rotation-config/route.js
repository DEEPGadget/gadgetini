import { Client } from "ssh2";
import mysql from "mysql2/promise";
import fs from "fs";
import path from "path";
import dbConfig from "../../utils/dbConfig";

export async function GET(request) {
  const parseConfig = (configContent) => {
    const configLines = configContent.split("\n");
    const config = {};

    configLines.forEach((line) => {
      const [key, value] = line.split("=");
      if (key && value) {
        config[key.trim()] = value.trim();
      }
    });

    return {
      orientation: config.orientation,
      cpu: config.cpumode,
      gpu: config.gpumode,
      psu: config.psumode,
      network: config.networkmode,
      sensors: config.sensormode,
      rotationTime: Number(config.time),
    };
  };

  try {
    const homeDir = "/home/gadgetini";
    const configFilePath = path.join(homeDir, "config.ini");

    const configContent = await fs.promises.readFile(configFilePath, "utf-8");
    const parsedConfig = parseConfig(configContent);

    console.log(parsedConfig);
    return new Response(JSON.stringify(parsedConfig), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("Error reading config file:", error);
    return new Response(
      JSON.stringify({ error: "Failed to read config file." }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
}

export async function POST(request) {
  try {
    const { rotation } = await request.json();

    // Fetch node IP addresses and credentials from the database
    const connection = await mysql.createConnection(dbConfig);
    const [rows] = await connection.execute(
      "SELECT piusername, piipaddress, pipassword FROM iplists"
    );
    console.log("Fetched IP list from database:", rows);
    await connection.end();

    const updateRotation = (piusername, piipaddress, pipassword, rotation) => {
      return new Promise((resolve, reject) => {
        const conn = new Client();
        conn
          .on("ready", () => {
            // Command to update only the orientation in config.ini
            const command = `sed -i 's/^orientation\\s*=.*/orientation=${rotation}/' ~/config.ini`;
            // Execute the command on the remote node
            conn.exec(command, (err) => {
              if (err) {
                reject(err);
                conn.end();
              } else {
                resolve(true);
                conn.end();
              }
            });
          })
          .on("error", (err) => {
            reject(err);
          })
          .connect({
            host: piipaddress,
            port: 22,
            username: piusername,
            password: pipassword,
          });
      });
    };

    const updateLocalRotation = async (rotation) => {
      const homeDir = "/home/gadgetini"; // Get home directory
      const configPath = path.join(homeDir, "config.ini"); // Path to config.ini in home directory

      // Read the existing config file
      let config = await fs.promises.readFile(configPath, "utf-8");

      // Update the orientation in the config file
      config = config.replace(/^orientation\s*=.*/m, `orientation=${rotation}`);

      // Write the updated config file back to the file system
      await fs.promises.writeFile(configPath, config, "utf-8");

      console.log(`Local config.ini updated with orientation=${rotation}`);
    };

    // Update the local config.ini file first
    await updateLocalRotation(rotation);

    // Iterate over each node and update only the orientation
    for (const node of rows) {
      await updateRotation(
        node.piusername,
        node.piipaddress,
        node.pipassword,
        rotation
      );
    }

    return new Response(
      JSON.stringify({ message: "Rotation updated on all nodes!" }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }
    );
  } catch (error) {
    console.error("Error updating rotation:", error);
    return new Response(
      JSON.stringify({ error: "Failed to update rotation." }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
}
