import { NextResponse } from "next/server";
import { exec } from "child_process";
import os from "os";

export async function GET() {
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

  return NextResponse.json({ ipv4: ipv4Address });
}

export async function POST(req) {
  const connectionName = "Wired connection 1";

  try {
    const payload = await req.json();
    console.log("Received IP Configuration Payload:", payload);

    // 모드 확인
    if (!["dhcp", "static"].includes(payload.mode)) {
      throw new Error("Invalid mode. Allowed values: 'dhcp', 'static'");
    }

    // DHCP 모드 변경
    if (payload.mode === "dhcp") {
      exec(
        `sudo nmcli connection modify "${connectionName}" ipv4.method auto && sudo nmcli connection up "${connectionName}"`,
        (error, stdout, stderr) => {
          if (error) {
            console.error("Error setting DHCP mode:", error);
            return;
          }
          console.log("DHCP mode enabled:", stdout);
        }
      );
    }

    // Static 모드 변경
    if (payload.mode === "static") {
      if (!payload.ip || !payload.netmask || !payload.gateway) {
        throw new Error("Missing required static IP parameters");
      }

      const address = `${payload.ip}/${payload.netmask}`;
      const gateway = payload.gateway;
      const dns = `${payload.dns1}${payload.dns2 ? `,${payload.dns2}` : ""}`;

      const command = `sudo nmcli connection modify "${connectionName}" ipv4.method manual ipv4.addresses "${address}" ipv4.gateway "${gateway}" ipv4.dns "${dns}" && sudo nmcli connection up "${connectionName}"`;

      exec(command, (error, stdout, stderr) => {
        if (error) {
          console.error("Error setting static IP mode:", error);
          return;
        }
        console.log("Static IP mode applied:", stdout);
      });
    }

    return NextResponse.json({
      success: true,
      message: `Network configuration updated to ${payload.mode}`,
    });
  } catch (error) {
    console.error("Error processing IP payload:", error);
    return NextResponse.json(
      { success: false, error: "Failed to process request" },
      { status: 500 }
    );
  }
}
