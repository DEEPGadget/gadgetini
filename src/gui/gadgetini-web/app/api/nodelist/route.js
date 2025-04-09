import { NextResponse } from "next/server";
import db from "@/database/db";

export async function GET() {
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
    console.log(error);
    return NextResponse.json({}, { status: 500 });
  }
}

// TODO DB에서 일부 노드 삭제 및 일부 노드 display config
export async function POST(request) {
  const body = await request.json();
  const { action, nodes } = body;

  if (action === "delete") {
    try {
      const ipsToDelete = nodes.map((node) => node.ip);
      const deleteStmt = db.prepare(`DELETE FROM nodelist WHERE ip = ?`);
      const deleteMany = db.transaction((ips) => {
        for (const ip of ips) {
          deleteStmt.run(ip);
        }
      });
      deleteMany(ipsToDelete);
      return NextResponse.json({ message: "Nodes deleted successfully." });
    } catch (error) {
      console.error("Error deleting nodes:", error);
      return NextResponse.json(
        { message: "Failed to delete nodes.", error: error.message },
        { status: 500 }
      );
    }
  }

  if (action === "configDisplay") {
    // TODO: display config 작업
    return NextResponse.json({ message: "Display configured" });
  }
}
