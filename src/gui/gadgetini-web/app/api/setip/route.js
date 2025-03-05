import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import { exec } from "child_process";

const filePath = `/etc/NetworkManager/system-connections/'Wired connection 1.nmconnection'`;

export async function POST(req) {
  try {
    const payload = await req.json();
    console.log("Received IP Configuration Payload:", payload);

    // 파일 읽기
    let fileData = await fs.readFile(filePath, "utf8");

    // IPv4 섹션 찾기
    const ipv4Marker = "[ipv4]";
    const ipv6Marker = "[ipv6]";

    const ipv4StartIndex = fileData.indexOf(ipv4Marker);
    if (ipv4StartIndex === -1) {
      throw new Error("Invalid configuration file: Missing [ipv4] section");
    }

    // IPv4 섹션 추출
    const ipv6StartIndex = fileData.indexOf(ipv6Marker);
    const ipv4EndIndex =
      ipv6StartIndex !== -1 ? ipv6StartIndex : fileData.length;
    const ipv4Content = fileData.substring(ipv4StartIndex, ipv4EndIndex);

    // IPv4 섹션 수정
    let newIpv4Content = ipv4Content.replace(
      /method=.*/g,
      `method=${payload.mode === "dhcp" ? "auto" : "manual"}`
    );

    if (payload.mode === "static") {
      // static 설정 적용 (address1, dns 수정)
      newIpv4Content = newIpv4Content
        .replace(
          /address1=.*/g,
          `address1=${payload.ip}/${payload.netmask},${payload.gateway}`
        )
        .replace(/dns=.*/g, `dns=${payload.dns1};${payload.dns2};`);
    }

    // IPv4 섹션만 변경한 새로운 파일 내용 생성
    const newFileContent =
      fileData.substring(0, ipv4StartIndex) +
      newIpv4Content +
      fileData.substring(ipv4EndIndex);

    // 변경된 설정 저장
    await fs.writeFile(filePath, newFileContent, { mode: 0o600 });
    console.log("Configuration updated:", newFileContent);

    // NetworkManager 설정 적용
    exec(
      `sudo nmcli connection reload && sudo nmcli connection down "Wired connection 1" && sudo nmcli connection up "Wired connection 1"`,
      (error, stdout, stderr) => {
        if (error) {
          console.error("Error restarting NetworkManager connection:", error);
        } else {
          console.log(
            "NetworkManager connection restarted successfully:",
            stdout
          );
        }
      }
    );

    return NextResponse.json({
      success: true,
      message:
        "Configuration updated and NetworkManager restarted successfully",
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
