import { NextResponse } from "next/server";
export async function GET() {
  //TODO DB에서 ip, alias 정보를 꺼냄
  const nodeList = [
    { ip: "192.168.1.100", status: false, alias: "worker" },
    { ip: "192.168.1.101", status: false, alias: "worker1" },
  ];
  return NextResponse.json(nodeList);
}

// TODO DB에서 ip 수정
export async function PATCH() {
  return NextResponse.json({ message: "Edit success" });
}

// TODO DB에 nodetable 업데이트
export async function PUT() {
  return NextResponse.json({ message: "Edit success" });
}
