"""
repo.py  --  the DATA-ACCESS LAYER (used by pages/1_Manage_Data.py).

Why this file exists
--------------------
Your app.py talks to SQLite directly. That works, but if every new page also
writes its own SQL you end up with the same query copied in five places. This
module is the single place that knows how to read/write the database for the new
admin features. The UI never writes SQL; it calls repo.update_event(...) etc.

How it connects to the plan
---------------------------
  * conn()        -> same WAL + foreign_keys setup as app.py, so both coexist.
  * _log()        -> Phase 1 audit trail. EVERY mutating function calls it.
  * get_*()       -> Phase 2 reads. They hide soft-deleted rows (is_deleted = 0).
  * update_* / soft_delete_* / delete_* -> Phase 2/3 writes, all audit-logged.
  * undo_last_action() -> Phase 3 safety net, reverses the most recent write.

It deliberately does NOT import streamlit, so it can be unit-tested on its own.
It does NOT touch app.py.
"""

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "ssc_database.db"

# Allowed values mirror the CHECK constraints in the schema. The UI uses these
# to build dropdowns so operators can never type an illegal value.
CHANNELS = ["connect", "whatsapp", "walk-in"]
REG_STATUS = ["registered", "cancelled", "waitlisted"]
ATTENDANCE = ["not check in", "check in", "no show"]
ROLES = ["main attendee", "guests"]
PAYMENT_STATUS = ["paid", "unpaid", "free"]
PAYMENT_METHOD = ["cash", "card", "transfer", "other"]


# ---------------------------------------------------------------------------
# Connection + low-level helpers
# ---------------------------------------------------------------------------
def conn():
    c = sqlite3.connect(DB_PATH, timeout=5.0)   # timeout: wait for WAL writer
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("PRAGMA journal_mode = WAL")
    return c


def _row_to_dict(row):
    return dict(row) if row is not None else None


def _log(c, operator, action, entity, entity_id, before, after):
    """Record one mutation in audit_log. Called inside the same transaction
    as the change itself, so the log and the data never drift apart."""
    c.execute(
        """
        INSERT INTO audit_log (operator, action, entity, entity_id, payload_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            operator,
            action,
            entity,
            str(entity_id),
            json.dumps({"before": before, "after": after}, default=str),
        ),
    )


def _norm(value):
    """Empty string -> None, date/datetime -> ISO string, else unchanged."""
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10] if isinstance(value, date) and not isinstance(value, datetime) else value.isoformat(sep=" ")[:19]
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


# ---------------------------------------------------------------------------
# READS  (Phase 2)  -- all hide soft-deleted rows
# ---------------------------------------------------------------------------
def get_events():
    with conn() as c:
        rows = c.execute(
            """
            SELECT e.event_id, e.event_name, e.location_id, e.event_type_id,
                   e.start_datetime, e.end_datetime, e.age_rating,
                   e.price_per_ticket, e.event_description
            FROM events e
            WHERE COALESCE(e.is_deleted, 0) = 0
            ORDER BY datetime(e.start_datetime) DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def get_locations():
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM locations WHERE COALESCE(is_deleted,0)=0 ORDER BY location_name"
        ).fetchall()
    return [dict(r) for r in rows]


def get_event_types():
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM event_types WHERE COALESCE(is_deleted,0)=0 ORDER BY etype_name"
        ).fetchall()
    return [dict(r) for r in rows]


def get_participants():
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM participants WHERE COALESCE(is_deleted,0)=0 ORDER BY lower(participant_name)"
        ).fetchall()
    return [dict(r) for r in rows]


def get_registrations():
    """Registrations joined to the registrant's name and the event name."""
    with conn() as c:
        rows = c.execute(
            """
            SELECT er.registration_id, er.event_id, ev.event_name,
                   er.registered_by, p.participant_name AS registered_by_name,
                   er.datetime_registered, er.number_of_attendee,
                   er.channel, er.source, er.status, er.notes
            FROM event_registration er
            LEFT JOIN events ev ON er.event_id = ev.event_id
            LEFT JOIN participants p ON er.registered_by = p.participant_id
            ORDER BY er.registration_id DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def get_attendees(registration_id):
    with conn() as c:
        rows = c.execute(
            """
            SELECT era.registration_id, era.participant_id,
                   p.participant_name, era.role, era.need_buddy,
                   era.attendance_status, era.checkin_datetime,
                   era.payment_status, era.payment_method
            FROM event_registered_attendee era
            LEFT JOIN participants p ON era.participant_id = p.participant_id
            WHERE era.registration_id = ?
            ORDER BY era.role DESC, lower(p.participant_name)
            """,
            (registration_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# UPDATES  (Phase 2)
# ---------------------------------------------------------------------------
def _generic_update(table, pk_col, pk_value, changes, entity, operator):
    """Update an arbitrary set of columns on one row, with audit logging.

    `changes` is {column: new_value}. Only those columns are touched, so
    columns the operator didn't edit are never overwritten.
    """
    if not changes:
        return
    clean = {k: _norm(v) for k, v in changes.items()}
    with conn() as c:
        before = _row_to_dict(
            c.execute(f"SELECT * FROM {table} WHERE {pk_col}=?", (pk_value,)).fetchone()
        )
        sets = ", ".join(f"{col}=?" for col in clean)
        c.execute(
            f"UPDATE {table} SET {sets} WHERE {pk_col}=?",
            (*clean.values(), pk_value),
        )
        _log(c, operator, "update", entity, pk_value, before, clean)
        c.commit()


def update_event(event_id, changes, operator="unknown"):
    _generic_update("events", "event_id", event_id, changes, "event", operator)


def update_location(location_id, changes, operator="unknown"):
    _generic_update("locations", "location_id", location_id, changes, "location", operator)


def update_event_type(etype_id, changes, operator="unknown"):
    _generic_update("event_types", "etype_id", etype_id, changes, "event_type", operator)


def update_participant(participant_id, changes, operator="unknown"):
    _generic_update("participants", "participant_id", participant_id, changes, "participant", operator)


def update_registration(registration_id, changes, operator="unknown"):
    _generic_update("event_registration", "registration_id", registration_id, changes, "registration", operator)


def update_attendee(registration_id, participant_id, changes, operator="unknown"):
    """Composite-key update for one attendee row."""
    if not changes:
        return
    clean = {k: _norm(v) for k, v in changes.items()}
    with conn() as c:
        before = _row_to_dict(
            c.execute(
                "SELECT * FROM event_registered_attendee WHERE registration_id=? AND participant_id=?",
                (registration_id, participant_id),
            ).fetchone()
        )
        sets = ", ".join(f"{col}=?" for col in clean)
        c.execute(
            f"UPDATE event_registered_attendee SET {sets} "
            f"WHERE registration_id=? AND participant_id=?",
            (*clean.values(), registration_id, participant_id),
        )
        _log(c, operator, "update", "attendee",
             f"{registration_id}/{participant_id}", before, clean)
        c.commit()


# ---------------------------------------------------------------------------
# DELETES  (Phase 3)
# ---------------------------------------------------------------------------
def _soft_delete(table, pk_col, pk_value, entity, operator):
    with conn() as c:
        before = _row_to_dict(
            c.execute(f"SELECT * FROM {table} WHERE {pk_col}=?", (pk_value,)).fetchone()
        )
        c.execute(f"UPDATE {table} SET is_deleted=1 WHERE {pk_col}=?", (pk_value,))
        _log(c, operator, "delete", entity, pk_value, before, {"is_deleted": 1})
        c.commit()


def soft_delete_event(event_id, operator="unknown"):
    _soft_delete("events", "event_id", event_id, "event", operator)


def soft_delete_location(location_id, operator="unknown"):
    _soft_delete("locations", "location_id", location_id, "location", operator)


def soft_delete_event_type(etype_id, operator="unknown"):
    _soft_delete("event_types", "etype_id", etype_id, "event_type", operator)


def soft_delete_participant(participant_id, operator="unknown"):
    _soft_delete("participants", "participant_id", participant_id, "participant", operator)



def cancel_registration(registration_id, operator="unknown"):
    """Mark a registration as cancelled without deleting it.

    This is the preferred workflow when someone registered but later cancels.
    It preserves the registration for audit/history, and marks all linked attendee
    rows unchanged; cancellation is stored on event_registration.status and active views exclude cancelled registrations.
    """
    with conn() as c:
        reg_before = _row_to_dict(
            c.execute("SELECT * FROM event_registration WHERE registration_id=?",
                      (registration_id,)).fetchone()
        )
        attendees_before = [dict(r) for r in c.execute(
            "SELECT * FROM event_registered_attendee WHERE registration_id=?",
            (registration_id,)).fetchall()]
        c.execute(
            "UPDATE event_registration SET status='cancelled' WHERE registration_id=?",
            (registration_id,),
        )
        _log(c, operator, "update", "registration", registration_id,
             {"registration": reg_before, "attendees": attendees_before},
             {"status": "cancelled"})
        c.commit()

def delete_registration(registration_id, operator="unknown"):
    """Hard delete a registration AND its attendee rows (leaf data).
    Done in one transaction so we never leave orphan attendees."""
    with conn() as c:
        reg = _row_to_dict(
            c.execute("SELECT * FROM event_registration WHERE registration_id=?",
                      (registration_id,)).fetchone()
        )
        att = [dict(r) for r in c.execute(
            "SELECT * FROM event_registered_attendee WHERE registration_id=?",
            (registration_id,)).fetchall()]
        c.execute("DELETE FROM event_registered_attendee WHERE registration_id=?", (registration_id,))
        c.execute("DELETE FROM event_registration WHERE registration_id=?", (registration_id,))
        _log(c, operator, "delete", "registration", registration_id,
             {"registration": reg, "attendees": att}, None)
        c.commit()


def delete_attendee(registration_id, participant_id, operator="unknown"):
    with conn() as c:
        before = _row_to_dict(
            c.execute(
                "SELECT * FROM event_registered_attendee WHERE registration_id=? AND participant_id=?",
                (registration_id, participant_id)).fetchone()
        )
        c.execute(
            "DELETE FROM event_registered_attendee WHERE registration_id=? AND participant_id=?",
            (registration_id, participant_id))
        # keep number_of_attendee in sync
        c.execute(
            "UPDATE event_registration SET number_of_attendee = "
            "(SELECT COUNT(*) FROM event_registered_attendee WHERE registration_id=?) "
            "WHERE registration_id=?",
            (registration_id, registration_id))
        _log(c, operator, "delete", "attendee",
             f"{registration_id}/{participant_id}", before, None)
        c.commit()



# ---------------------------------------------------------------------------
# CREATE AUDIT + ARCHIVE RESTORE / HARD DELETE (V15)
# ---------------------------------------------------------------------------
def log_create(entity, entity_id, after=None, operator="unknown"):
    """Record a create action in audit_log. Used by app.py create flows."""
    with conn() as c:
        _log(c, operator, "create", entity, entity_id, None, after or {"created": True})
        c.commit()


def _get_archived(table, order_col):
    with conn() as c:
        rows = c.execute(
            f"SELECT * FROM {table} WHERE COALESCE(is_deleted,0)=1 ORDER BY {order_col}"
        ).fetchall()
    return [dict(r) for r in rows]


def get_archived_events():
    return _get_archived("events", "datetime(start_datetime) DESC")


def get_archived_locations():
    return _get_archived("locations", "location_name")


def get_archived_event_types():
    return _get_archived("event_types", "etype_name")


def get_archived_participants():
    return _get_archived("participants", "lower(participant_name)")


def _restore(table, pk_col, pk_value, entity, operator):
    with conn() as c:
        before = _row_to_dict(c.execute(f"SELECT * FROM {table} WHERE {pk_col}=?", (pk_value,)).fetchone())
        c.execute(f"UPDATE {table} SET is_deleted=0 WHERE {pk_col}=?", (pk_value,))
        after = _row_to_dict(c.execute(f"SELECT * FROM {table} WHERE {pk_col}=?", (pk_value,)).fetchone())
        _log(c, operator, "restore", entity, pk_value, before, after)
        c.commit()


def restore_event(event_id, operator="unknown"):
    _restore("events", "event_id", event_id, "event", operator)


def restore_location(location_id, operator="unknown"):
    _restore("locations", "location_id", location_id, "location", operator)


def restore_event_type(etype_id, operator="unknown"):
    _restore("event_types", "etype_id", etype_id, "event_type", operator)


def restore_participant(participant_id, operator="unknown"):
    _restore("participants", "participant_id", participant_id, "participant", operator)


def _hard_delete(table, pk_col, pk_value, entity, operator):
    """Permanently remove an archived row. This may fail if foreign keys still reference it."""
    with conn() as c:
        before = _row_to_dict(c.execute(f"SELECT * FROM {table} WHERE {pk_col}=?", (pk_value,)).fetchone())
        c.execute(f"DELETE FROM {table} WHERE {pk_col}=?", (pk_value,))
        _log(c, operator, "hard_delete", entity, pk_value, before, None)
        c.commit()


def hard_delete_event(event_id, operator="unknown"):
    _hard_delete("events", "event_id", event_id, "event", operator)


def hard_delete_location(location_id, operator="unknown"):
    _hard_delete("locations", "location_id", location_id, "location", operator)


def hard_delete_event_type(etype_id, operator="unknown"):
    _hard_delete("event_types", "etype_id", etype_id, "event_type", operator)


def hard_delete_participant(participant_id, operator="unknown"):
    _hard_delete("participants", "participant_id", participant_id, "participant", operator)


def close_event_mark_no_shows(event_id, operator="unknown"):
    """Post-event operation: mark all remaining active, not-checked-in attendees
    for one event as no show. Returns the number of attendee rows updated.

    Registration cancellation is handled in event_registration.status, so this
    only targets registrations that are still active/registered.
    """
    with conn() as c:
        before = [dict(r) for r in c.execute(
            """
            SELECT era.registration_id, era.participant_id, era.attendance_status
            FROM event_registered_attendee era
            JOIN event_registration er ON era.registration_id = er.registration_id
            WHERE er.event_id = ?
              AND COALESCE(er.status, 'registered') != 'cancelled'
              AND COALESCE(era.attendance_status, 'not check in') = 'not check in'
            """,
            (event_id,),
        ).fetchall()]
        cur = c.execute(
            """
            UPDATE event_registered_attendee
            SET attendance_status = 'no show'
            WHERE registration_id IN (
                SELECT registration_id
                FROM event_registration
                WHERE event_id = ?
                  AND COALESCE(status, 'registered') != 'cancelled'
            )
              AND COALESCE(attendance_status, 'not check in') = 'not check in'
            """,
            (event_id,),
        )
        _log(c, operator, "update", "event_no_shows", event_id, before, {"attendance_status": "no show", "rows_updated": cur.rowcount})
        c.commit()
        return cur.rowcount

# ---------------------------------------------------------------------------
# AUDIT + UNDO  (Phase 3)
# ---------------------------------------------------------------------------
def get_audit(limit=100):
    with conn() as c:
        rows = c.execute(
            "SELECT audit_id, ts, operator, action, entity, entity_id, undone "
            "FROM audit_log ORDER BY audit_id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def undo_last_action(operator="unknown"):
    """Reverse the most recent not-yet-undone write.

    Supported reversals:
      * update  -> restore the 'before' values
      * delete (soft) -> set is_deleted back to 0
    Hard deletes of registrations are intentionally NOT auto-undone here
    (they remove rows from two tables); the payload is kept in the log so a
    human can restore manually if ever needed.
    Returns a short human-readable message.
    """
    table_by_entity = {
        "event": ("events", "event_id"),
        "location": ("locations", "location_id"),
        "event_type": ("event_types", "etype_id"),
        "participant": ("participants", "participant_id"),
        "registration": ("event_registration", "registration_id"),
    }
    with conn() as c:
        row = c.execute(
            "SELECT * FROM audit_log WHERE undone=0 ORDER BY audit_id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return "Nothing to undo."
        entry = dict(row)
        payload = json.loads(entry["payload_json"] or "{}")
        action, entity = entry["action"], entry["entity"]

        if entity not in table_by_entity and entity != "attendee":
            return f"Cannot auto-undo entity '{entity}'."

        if action == "update":
            before = payload.get("before") or {}
            if entity == "attendee":
                reg_id, pid = entry["entity_id"].split("/")
                cols = [k for k in before if k not in ("registration_id", "participant_id")]
                if cols:
                    sets = ", ".join(f"{k}=?" for k in cols)
                    c.execute(
                        f"UPDATE event_registered_attendee SET {sets} "
                        f"WHERE registration_id=? AND participant_id=?",
                        (*[before[k] for k in cols], reg_id, pid))
            else:
                table, pk = table_by_entity[entity]
                cols = [k for k in before if k != pk]
                sets = ", ".join(f"{k}=?" for k in cols)
                c.execute(f"UPDATE {table} SET {sets} WHERE {pk}=?",
                          (*[before[k] for k in cols], entry["entity_id"]))
            msg = f"Reverted update on {entity} {entry['entity_id']}."

        elif action == "delete" and entity in table_by_entity and entity != "registration":
            table, pk = table_by_entity[entity]
            c.execute(f"UPDATE {table} SET is_deleted=0 WHERE {pk}=?", (entry["entity_id"],))
            msg = f"Restored {entity} {entry['entity_id']}."

        else:
            return f"Cannot auto-undo a {action} on {entity}. Payload kept in the log."

        c.execute("UPDATE audit_log SET undone=1 WHERE audit_id=?", (entry["audit_id"],))
        _log(c, operator, "undo", entity, entry["entity_id"], None, {"undid_audit_id": entry["audit_id"]})
        c.commit()
        return msg
