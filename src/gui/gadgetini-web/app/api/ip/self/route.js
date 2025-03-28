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
  const connectionName = "Wired connection 1";

  try {
    const payload = await req.json();
    console.log("Received IP Configuration Payload:", payload);

    // Change to DHCP or static
    if (payload.mode === "dhcp") {
      // USE 'nmcli' command
      const command = `sudo nmcli connection modify "${connectionName}" ipv4.method auto && sudo nmcli connection up "${connectionName}"`;

      exec(command, (error, stdout, stderr) => {
        if (error) {
          console.error("exec DHCP mode change", error);
          throw new Error("IP update fail");
        }
      });
    } else if (payload.mode === "static") {
      if (!payload.ip || !payload.netmask || !payload.gateway) {
        throw new Error("Missing required static IP parameters");
      }

      const address = `${payload.ip}/${payload.netmask}`;
      const gateway = payload.gateway;
      const dns = `${payload.dns1}${payload.dns2 ? `,${payload.dns2}` : ""}`;
      // USE 'nmcli' command
      const command = `sudo nmcli connection modify "${connectionName}" ipv4.method manual ipv4.addresses "${address}" ipv4.gateway "${gateway}" ipv4.dns "${dns}" && sudo nmcli connection up "${connectionName}"`;

      exec(command, (error, stdout, stderr) => {
        if (error) {
          console.error("exec Static mode change", error);
          return;
        }
      });
    }
    return NextResponse.json(payload);
  } catch (error) {
    console.error("[ip/self/POST]]", error);
    return NextResponse.json(
      { error: "Failed to process request" },
      { status: 500 }
    );
  }
}
