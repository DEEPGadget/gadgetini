import db from "./db.js";

db.exec(`
  CREATE TABLE IF NOT EXISTS nodelist (
    ip VARCHAR(15) PRIMARY KEY,
    alias VARCHAR(50)
  );
`);
