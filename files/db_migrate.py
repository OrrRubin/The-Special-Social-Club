"""
db_migrate.py  --  PHASE 1 (Foundation), run ONCE before launching the app.

What it does, and why each piece matters for the rest of the plan:

  1. journal_mode = WAL      -> lets several Streamlit sessions READ while one
                               WRITES. This is what makes "multiple operators on
                               the LAN at once" safe. WAL is written into the .db
                               file header, so it PERSISTS -- app.py's own
                               connections automatically inherit it afterwards.
  2. audit_log table         -> every write in repo.py records who/what/when here.
                               Phase 3's "Undo last action" reads from this table.
  3. is_deleted columns      -> soft delete. Instead of destroying rows that other
                               tables point to (events, participants, locations,
                               event_types), we flag them hidden. Registrations and
                               attendees are leaf rows, so they can be hard-deleted.

This script is IDEMPOTENT: safe to run repeatedly. It never touches existing data.
It does NOT modify app.py or any existing table data.

Usage:
    python db_migrate.py            # migrates ./ssc_database.db
    python db_migrate.py other.db   # migrates a named file
"""

import sqlite3
import sys
from pathlib import Path

# Tables that other tables reference -> use soft delete (hide, don't destroy).
SOFT_DELETE_TABLES = ["events", "locations", "event_types", "participants"]


def column_exists(conn, table, column):
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    return column in cols


def migrate(db_path: Path):
    print(f"Migrating: {db_path}")
    conn = sqlite3.connect(db_path)
    try:
        # --- 1. WAL mode (persists in the file header) ---------------------
        mode = conn.execute("PRAGMA journal_mode = WAL").fetchone()[0]
        print(f"  journal_mode -> {mode}")

        # --- 2. audit_log table -------------------------------------------
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                audit_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                ts           DATETIME DEFAULT CURRENT_TIMESTAMP,
                operator     TEXT,            -- who was signed in
                action       TEXT,            -- 'create' | 'update' | 'delete' | 'undo'
                entity       TEXT,            -- 'event' | 'participant' | ...
                entity_id    TEXT,
                payload_json TEXT,            -- {"before": {...}, "after": {...}}
                undone       INTEGER DEFAULT 0
            )
            """
        )
        print("  audit_log table ready")

        # --- 3. is_deleted soft-delete columns ----------------------------
        for table in SOFT_DELETE_TABLES:
            if not column_exists(conn, table, "is_deleted"):
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN is_deleted INTEGER DEFAULT 0"
                )
                print(f"  added {table}.is_deleted")
            else:
                print(f"  {table}.is_deleted already present")

        conn.commit()
        print("Migration complete.\n")
    finally:
        conn.close()


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "ssc_database.db"
    if not target.exists():
        sys.exit(f"Database not found: {target}")
    migrate(target)
