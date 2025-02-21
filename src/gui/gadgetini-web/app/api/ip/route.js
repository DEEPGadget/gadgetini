import mysql from "mysql2/promise";
import dbConfig from "../../utils/dbConfig";

// Define a map for database error codes and their corresponding messages
const dbErrorMessages = {
  ER_DUP_ENTRY: "Duplicate entry.",
  ER_DATA_TOO_LONG: "Too Long Data.",
};

// Function to get error message from error code
const getDbErrorMessage = (code) => dbErrorMessages[code] || "Database error.";

// Utility function to create a MySQL connection
const createConnection = async () => mysql.createConnection(dbConfig);

// Utility function for responding with JSON
const jsonResponse = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });

// GET: Fetch all IP list entries
export async function GET() {
  try {
    const connection = await createConnection();
    const [rows] = await connection.execute(
      "SELECT serveralias, serveripaddress, piipaddress FROM iplists"
    );
    await connection.end();
    return jsonResponse(rows);
  } catch (error) {
    console.error("Database error:", error);
    return jsonResponse({ error: "Database error." }, 500);
  }
}

// POST: Register a new IP entry
export async function POST(request) {
  try {
    const { serveralias, serveripaddress, piipaddress } = await request.json();
    const piusername = "gadgetini";
    const pipassword = process.env.PI_PASSWORD;

    if (!serveripaddress || !piipaddress) {
      return jsonResponse(
        {
          error:
            "Missing required fields: serverusername, serveripaddress, serverpassword, piipaddress.",
        },
        400
      );
    }

    // Insert into database
    try {
      const connection = await createConnection();
      await connection.execute(
        "INSERT INTO iplists (serveralias, serveripaddress, piusername, piipaddress, pipassword) VALUES (?, ?, ?, ?, ?)",
        [serveralias, serveripaddress, piusername, piipaddress, pipassword]
      );
      await connection.end();
      return jsonResponse({ message: "Data inserted successfully!" });
    } catch (dbError) {
      const errorResponse = getDbErrorMessage(dbError.code);
      return jsonResponse({ error: errorResponse }, 400);
    }
  } catch (error) {
    console.error("Database error:", error);
    return jsonResponse({ error: "Database error." }, 500);
  }
}

// PUT: Update an existing IP entry
export async function PUT(request) {
  try {
    const { serveripaddress, piipaddress, field, value } = await request.json();
    if (!serveripaddress || !piipaddress || !field || !value) {
      return jsonResponse({ error: "Missing required fields." }, 400);
    }

    try {
      const connection = await createConnection();
      const query = `UPDATE iplists SET ${field} = ? WHERE serveripaddress = ? AND piipaddress = ?`;
      await connection.execute(query, [value, serveripaddress, piipaddress]);
      await connection.end();
      return jsonResponse({ message: "Data updated successfully!" });
    } catch (dbError) {
      const errorResponse = getDbErrorMessage(dbError.code);
      return jsonResponse({ error: errorResponse }, 400);
    }
  } catch (error) {
    console.error("Database error:", error);
    return jsonResponse({ error: "Database error." }, 500);
  }
}

// DELETE: Delete an existing IP entry
export async function DELETE(request) {
  try {
    const { serveripaddress, piipaddress } = await request.json();
    if (!serveripaddress || !piipaddress) {
      return jsonResponse({ error: "Missing required fields." }, 400);
    }

    try {
      const connection = await createConnection();
      const [result] = await connection.execute(
        "DELETE FROM iplists WHERE serveripaddress = ? AND piipaddress = ?",
        [serveripaddress, piipaddress]
      );
      await connection.end();

      if (result.affectedRows === 0) {
        return jsonResponse({ message: "No record found to delete." }, 404);
      }

      return jsonResponse({ message: "Data deleted successfully!" });
    } catch (dbError) {
      const errorResponse = getDbErrorMessage(dbError.code);
      return jsonResponse({ error: errorResponse }, 400);
    }
  } catch (error) {
    console.error("Database error:", error);
    return jsonResponse({ error: "Database error." }, 500);
  }
}
