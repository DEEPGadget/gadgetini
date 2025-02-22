import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import { exec } from "child_process";

const filePath = "/etc/systemd/network/static-ip.network";

export async function POST(req) {
  try {
    const payload = await req.json();
    console.log("Received IP Configuration Payload:", payload);

    let newNetworkContent = "";
    if (payload.mode === "static") {
      newNetworkContent = `DHCP=no
Address=${payload.ip}/${payload.netmask}
Gateway=${payload.gateway}
DNS=${payload.dns1}
DNS=${payload.dns2}
`;
    } else if (payload.mode === "dhcp") {
      newNetworkContent = `DHCP=yes
Address=
Gateway=
DNS=
DNS=
`;
    } else {
      return NextResponse.json(
        { success: false, error: "Invalid mode" },
        { status: 400 }
      );
    }

    const fileData = await fs.readFile(filePath, "utf8");
    const networkMarker = "[Network]";
    const markerIndex = fileData.indexOf(networkMarker);
    const preservedContent = fileData.substring(0, markerIndex).trimEnd();
    const newFileContent = `${preservedContent}
${networkMarker}
${newNetworkContent}`;

    await fs.writeFile(filePath, newFileContent);
    console.log("Configuration updated:", newFileContent);

    exec("sudo systemctl restart systemd-networkd", (error, stdout, stderr) => {
      if (error) {
        console.error("Error restarting systemd-networkd:", error);
      } else {
        console.log("systemd-networkd restarted successfully:", stdout);
      }
    });

    return NextResponse.json({
      success: true,
      message:
        "Configuration updated and network service restarted successfully",
      updatedFileContent: newFileContent,
    });
  } catch (error) {
    console.error("Error processing IP payload:", error);
    return NextResponse.json(
      { success: false, error: "Failed to process request" },
      { status: 500 }
    );
  }
}
