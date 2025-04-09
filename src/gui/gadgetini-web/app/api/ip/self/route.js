import { NextResponse } from "next/server";
import { exec as _exec } from "child_process";
import { promisify } from "util";
import os from "os";

const exec = promisify(_exec);

// Read IPv4 address and Return
export async function GET() {
  try {
    const interfaces = os.networkInterfaces();
    let ipv4Address = "localhost";

    for (let iface in interfaces) {
      if (
        iface.toLowerCase().includes("wlan") ||
        iface.toLowerCase().includes("eth")
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
    console.error("[ip/self/GET]", error);
    return NextResponse.json({ error: "Failed to fetch IP" }, { status: 500 });
  }
}

// Get connected eth connection name
async function getActiveConnectionName() {
  try {
    const { stdout } = await exec(
      "nmcli -t -f NAME,DEVICE,STATE connection show --active"
    );

    const lines = stdout.trim().split("\n");
    for (const line of lines) {
      const [name, device, state] = line.split(":");
      if (device?.startsWith("eth") && state === "activated") {
        return name;
      }
    }
    return null;
  } catch (error) {
    console.error("[ip/self/POST]", error);
    return NextResponse.json(
      { error: "Failed to get activated connection name" },
      { status: 400 }
    );
  }
}

// Update IPv4 address from user input
export async function POST(req) {
  try {
    const payload = await req.json();
    const connectionName = await getActiveConnectionName();

    let command = ``;
    // Change to DHCP or static
    if (payload.mode === "dhcp") {
      const command = `nmcli connection modify "${connectionName}" ipv4.method auto && nmcli connection up "${connectionName}"`;
      await exec(command);
    } else if (payload.mode === "static") {
      const { ip, netmask, gateway, dns1, dns2 } = payload;
      const address = `${ip}/${netmask}`;
      const dns = dns2 ? `${dns1},${dns2}` : dns1;
      if (!ip || !netmask || !gateway) {
        return NextResponse.json(
          { error: "Missing paramters ip, netmask, gateway are required" },
          { status: 400 }
        );
      }
      // USE 'nmcli' command
      const command = `nmcli connection modify "${connectionName}" ipv4.method manual ipv4.addresses "${address}" ipv4.gateway "${gateway}" ipv4.dns "${dns}" && nmcli connection up "${connectionName}"`;
      await exec(command);
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
