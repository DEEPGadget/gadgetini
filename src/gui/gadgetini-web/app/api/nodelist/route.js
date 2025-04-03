import { NextResponse } from "next/server";
export async function GET() {
  const nodeList = [
    { ip: "192.168.1.100", name: "worker" },
    { ip: "192.168.1.101", name: "worker1" },
  ];
  return NextResponse.json(nodeList);
}
