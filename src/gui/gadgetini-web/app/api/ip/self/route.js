import { NextResponse } from "next/server";
import { exec } from "child_process";
import os from "os";

// Read IPv4 address and Return
export async function GET() {
  try {
    const interfaces = os.networkInterfaces();
    let ipv4Address = "localhost";

    for (let iface in interfaces) {
      if (
        iface.toLowerCase().includes("wifi") ||
        iface.toLowerCase().includes("wi-fi") ||
        iface.toLowerCase().includes("wlan") ||
        iface.toLowerCase().includes("eth") ||
        iface.toLowerCase().includes("VMnet")
      ) {
        for (let alias of interfaces[iface]) {
          if (alias.family === "IPv4" && !alias.internal) {
            ipv4Address = alias.address;
            break;
          }
        }
      }
      if (ipv4Address !== "localhost") break;
    }

    return NextResponse.json(ipv4Address);
  } catch (error) {
    console.error("[ip/self/GET]]", error);
    return NextResponse.json({ error: "Failed to fetch IP" }, { status: 500 });
  }
}

// Update IPv4 address from user input
export async function POST(req) {
  // Get connected eth connection name
  function getActiveConnectionName() {
    try {
      const output = execSync(
        "nmcli -t -f NAME,DEVICE,STATE connection show --active"
      )
        .toString()
        .trim();

      const lines = output.split("\n");
      for (const line of lines) {
        const [name, device, state] = line.split(":");
        if (device?.startsWith("eth") && state === "activated") {
          return name;
        }
      }

      return null;
    } catch (error) {
      console.error("[getActiveEthernetConnectionName]", error);
      return null;
    }
  }

  const connectionName = getActiveConnectionName();

  try {
    const payload = await req.json();
    console.log("Received IP Configuration Payload:", payload);
    let command = ``;
    // Change to DHCP or static
    if (payload.mode === "dhcp") {
      // USE 'nmcli' command
      command = `sudo nmcli connection modify "${connectionName}" ipv4.method auto && sudo nmcli connection up "${connectionName}"`;

      exec(command, (error, stdout, stderr) => {
        if (error) {
          return NextResponse.json(
            { error: "Failed to execute dhcp IP config" },
            { status: 500 }
          );
        }
      });
    } else if (payload.mode === "static") {
      if (!payload.ip || !payload.netmask || !payload.gateway) {
        return NextResponse.json(
          { error: "Missing paramters ip, netmask, gateway are required" },
          { status: 400 }
        );
      }
      const address = `${payload.ip}/${payload.netmask}`;
      const gateway = payload.gateway;
      const dns = `${payload.dns1}${payload.dns2 ? `,${payload.dns2}` : ""}`;
      // USE 'nmcli' command
      command = `sudo nmcli connection modify "${connectionName}" ipv4.method manual ipv4.addresses "${address}" ipv4.gateway "${gateway}" ipv4.dns "${dns}" && sudo nmcli connection up "${connectionName}"`;

      exec(command, (error, stdout, stderr) => {
        if (error) {
          return NextResponse.json(
            { error: "Failed to execute static IP config" },
            { status: 500 }
          );
        }
      });
    }
    return NextResponse.json(payload);
  } catch (error) {
    console.error("[ip/self/POST]]", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
