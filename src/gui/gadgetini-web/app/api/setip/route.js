export async function POST(req) {
  try {
    const { ipv4 } = await req.json();
    if (ipv4) {
      currentIP = ipv4; // 현재 IP 값 업데이트
      return NextResponse.json({ success: true, ipv4 });
    }
    return NextResponse.json({ success: false, error: "Invalid IP" });
  } catch (error) {
    return NextResponse.json({ success: false, error: "Failed to update IP" });
  }
}
