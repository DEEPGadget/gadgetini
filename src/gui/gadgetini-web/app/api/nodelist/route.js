import { NextResponse } from "next/server";
import db from "@/database/db";

// Cluster get API
export async function GET() {
  const nodelist = db.prepare("SELECT * FROM nodelist").all();
  return NextResponse.json(nodelist);
}

// Cluster edit API
export async function PATCH(req) {
  try {
    const payload = await req.json();
    const { ip, key, value } = payload;

    let sql;
    if (key === "ip") {
      const selectAliasStmt = db.prepare(
        "SELECT alias FROM nodelist WHERE ip = ?"
      );
      const alias = selectAliasStmt.get(ip)?.alias;
      const deleteStmt = db.prepare("DELETE FROM nodelist WHERE ip = ?");
      deleteStmt.run(ip);
      const insertStmt = db.prepare(
        "INSERT INTO nodelist (ip, alias) VALUES (?,  ?)"
      );
      insertStmt.run(value, alias);
    } else if (key === "alias") {
      sql = "UPDATE nodelist SET alias = ? WHERE ip = ?";
      const stmt = db.prepare(sql);
      stmt.run(value, ip);
    }
    return NextResponse.json({ message: "Node updated successfully" });
  } catch (error) {
    console.error(error);
    return NextResponse.json(
      { message: "Internal server error" },
      { status: 500 }
    );
  }
}

// Cluster add API
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

// Cluster delete api
export async function POST(req) {
  const body = await req.json();
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
