# SSC Event Management — Admin/Operator Integration Guide

This draft adds full database operation for non-coding operators **without
changing your working `app.py` or your data**. Everything new is in separate
files. You can delete them and you're back to the original app.

## File map

```
ssc/
├── app.py                  UNCHANGED — your V8 operator console
├── ssc_database.db         your data (migration adds columns, no data touched)
├── requirements.txt        + streamlit-autorefresh (optional)
│
├── db_migrate.py           PHASE 1 — run ONCE: WAL, audit_log, is_deleted
├── repo.py                 PHASES 1–3 — data-access layer (reads/writes/undo)
├── ui_helpers.py           PHASES 1–4 — login, editable grid, export, refresh
├── pages/
│   └── 1_Manage_Data.py    PHASES 2–4 — the admin page (auto-added to nav)
└── .streamlit/
    └── secrets.toml        PHASE 1 — operator accounts (edit before real use)
```

## How the pieces connect

```
            operator's browser
                   │
     ┌─────────────┴──────────────┐
     │                            │
   app.py                  pages/1_Manage_Data.py        ← Streamlit shows BOTH
 (your console)                   │                         in one sidebar nav
     │                            │ calls
     │ direct SQL            ui_helpers.py  (login, grid, export, refresh)
     │ (unchanged)                │ calls
     └──────────┬─────────────────┘
                ▼
             repo.py   ← only place the new page writes SQL; every write goes
                │         through _log() into audit_log
                ▼
          ssc_database.db (WAL mode)
                ▲
         db_migrate.py (run once: WAL + audit_log + is_deleted columns)
```

* **`app.py`** keeps doing registration / check-in / dashboard exactly as before.
* **`pages/1_Manage_Data.py`** is the new surface for *fixing and removing* data.
  Streamlit's `pages/` convention makes it appear in the sidebar automatically —
  that's why no edit to `app.py` is needed.
* Both write to the **same `ssc_database.db`**. WAL mode (set once by the
  migration and stored in the file header) lets them run at the same time, so a
  change made on one page shows up on the other after a rerun. That's your
  "real-time, locally hosted" behaviour.

## The five phases, mapped to the files

1. **Foundation** — `db_migrate.py` turns on WAL (concurrency), creates
   `audit_log` (history), and adds `is_deleted` (soft delete). `repo.conn()` and
   `repo._log()` plug into it. `ui_helpers.require_login()` adds the password gate.
2. **Close the CRUD gaps** — `repo.py` gains update/delete for every table;
   `ui_helpers.editable_table()` renders any table as an edit-in-place grid;
   `pages/1_Manage_Data.py` wires five tabs (Events, Locations, Event types,
   People, Registrations) using that one widget. New rows still go through your
   existing `app.py` forms — this page is for editing/removing what exists.
3. **Operator safety** — soft delete (hide, don't destroy) on referenced tables,
   confirm-twice delete in the grid, and `repo.undo_last_action()` driven by the
   audit log (the "Audit / Undo" tab).
4. **Concurrency & polish** — WAL (done in P1), `safe_autorefresh()` on the live
   audit view, `export_buttons()` for CSV/Excel on every grid, and a
   viewer-vs-operator role from `secrets.toml`.
5. **Deployment** — see below.

## Run it (local demo)

```bash
pip install -r requirements.txt
python db_migrate.py            # ONCE — safe to re-run, never touches data

# set real passwords first:
python -c "import hashlib;print(hashlib.sha256('mypassword'.encode()).hexdigest())"
# paste the hash into .streamlit/secrets.toml

streamlit run app.py            # serves app.py + the Manage Data page together
```

## Deployment for the team (Phase 5)

Run on the host machine and let operators reach it over the office WiFi:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Operators open `http://<host-ip>:8501` on their laptops. Keep
`ssc_database.db` next to `app.py`. Back it up daily, e.g.:

```bash
cp ssc_database.db backups/ssc_$(date +%F).db     # cron / Task Scheduler
```

## What's intentionally left for you to decide

* New-row creation in the admin grids is disabled (`num_rows="fixed"`) so IDs are
  always generated the same way as in `app.py`. If you want add-row here too,
  reuse `app.py`'s `next_code()` helpers from `repo.py`.
* Participant boolean fields (groupchat/connect/marketing) are read-only in the
  People tab to preserve the three-state "unknown" logic; edit them via the
  registration screens.
* `undo_last_action()` reverses edits and soft-deletes automatically; hard-deleted
  registrations are preserved in `audit_log.payload_json` for manual restore.
