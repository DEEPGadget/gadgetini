import Database from "better-sqlite3";
import path from "path";

const dbPath = path.join(process.cwd(), "database", "data.db");
const db = new Database(dbPath);

db.exec(`
  CREATE TABLE IF NOT EXISTS nodelist (
    ip VARCHAR(15) PRIMARY KEY,
    alias VARCHAR(50)
  );
`);

export default db;
