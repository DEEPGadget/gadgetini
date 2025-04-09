import { NextResponse } from "next/server";
import db from "@/database/db";

export async function GET() {
  //TODO DB에서 ip, alias 정보를 꺼냄
  const nodelist = db.prepare("SELECT * FROM nodelist").all();
  return NextResponse.json(nodelist);
}

// TODO DB에서 ip 수정
export async function PATCH() {
  return NextResponse.json({ message: "Edit success" });
}

// TODO DB에 nodetable 업데이트
export async function PUT(req) {
  const nodes = await req.json();

  try {
    const insertStmt = db.prepare(
      "INSERT INTO nodelist (ip, alias) VALUES (@ip, @alias)"
    );
    const insertMany = db.transaction((nodes) => {
      for (const node of nodes) {
        insertStmt.run(node);
      }
    });

    insertMany(nodes);

    return NextResponse.json(
      { message: "Nodes added successfully" },
      { status: 200 }
    );
  } catch (error) {
    console.error("Database insertion error:", error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

// TODO DB에서 일부 노드 삭제 및 일부 노드 display config
export async function POST() {
  const body = await request.json();
  const { action, nodes } = body;
  if (action === "delete") {
    // TODO: DB에서 nodes에 해당하는 노드 삭제
    return NextResponse.json({ message: "Nodes deleted" });
  }

  if (action === "configDisplay") {
    // TODO: display config 작업
    return NextResponse.json({ message: "Display configured" });
  }
}
