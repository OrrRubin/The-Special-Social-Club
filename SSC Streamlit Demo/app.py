import sqlite3
from datetime import datetime, date, time
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import repo


DB_PATH = Path(__file__).parent / "ssc_database.db"
CHANNELS = ["whatsapp", "connect", "walk-in"]
REGISTRATION_CHANNELS = ["whatsapp", "connect", "walk-in"]
BOOL_OPTIONS = ["Unknown / not filled", "Yes", "No"]
DOB_MIN = date(1900, 1, 1)
DOB_MAX = date.today()

st.set_page_config(page_title="SSC Event Management", page_icon="🎟️", layout="wide")

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Inter', sans-serif;
}
.block-container {
    padding-top: 1.6rem;
    padding-bottom: 2rem;
    max-width: 1350px;
}
.app-header {
    padding: 0.4rem 0 1.1rem 0;
    margin-bottom: 1rem;
    border-bottom: 1px solid rgba(148, 163, 184, 0.25);
}
.app-title {
    font-size: clamp(2.1rem, 5vw, 3.4rem);
    font-weight: 800;
    line-height: 1.18;
    letter-spacing: -0.04em;
    margin: 0;
    padding: 0.2rem 0 0.35rem 0;
    color: #F8FAFC;
    overflow: visible;
}
.app-subtitle {
    font-size: 1.08rem;
    color: #94A3B8;
    margin: 0;
}
.event-card {
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 18px;
    padding: 1rem;
    margin-bottom: 1rem;
    background: linear-gradient(180deg, rgba(30, 41, 59, 0.96), rgba(15, 23, 42, 0.96));
    box-shadow: 0 10px 24px rgba(0,0,0,0.18);
}
.event-banner {
    height: 105px;
    border-radius: 14px;
    background: linear-gradient(135deg, rgba(56,189,248,.28), rgba(99,102,241,.18));
    display:flex;
    align-items:center;
    justify-content:center;
    margin-bottom:.9rem;
}
.small-muted {color:#94A3B8; font-size:.9rem;}
.status-pill {
    display:inline-block;
    padding:.25rem .7rem;
    border-radius:999px;
    background:rgba(56, 189, 248, 0.18);
    color:#BAE6FD;
    border:1px solid rgba(56, 189, 248, 0.28);
    font-size:.85rem;
}
.kpi-card {
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 16px;
    padding: 1rem;
    background: rgba(30, 41, 59, 0.94);
    margin-bottom: .75rem;
}
.kpi-label {color:#94A3B8; font-size:.88rem;}
.kpi-value {color:#F8FAFC; font-size:1.8rem; font-weight:800; line-height:1.25;}
.sidebar-brand {
    font-size: 1.35rem;
    font-weight: 800;
    line-height: 1.2;
    margin-bottom: .2rem;
}
.sidebar-caption {color:#94A3B8; font-size:.85rem; margin-bottom:.6rem;}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def prevent_enter_to_submit():
    """Prevent accidental form submission when pressing Enter inside text inputs.

    Staff should submit only by clicking explicit buttons. Textareas are excluded
    so multi-line fields remain usable.
    """
    components.html(
        """
        <script>
        const doc = window.parent.document;
        if (!doc.__sscPreventEnterSubmitInstalled) {
            doc.__sscPreventEnterSubmitInstalled = true;
            doc.addEventListener('keydown', function(e) {
                const tag = (e.target && e.target.tagName || '').toUpperCase();
                const type = (e.target && e.target.getAttribute && e.target.getAttribute('type') || '').toLowerCase();
                const isTextInput = tag === 'INPUT' && !['button','submit','checkbox','radio'].includes(type);
                const label = (
                    e.target.getAttribute('aria-label') ||
                    e.target.getAttribute('placeholder') ||
                    e.target.getAttribute('name') ||
                    ''
                ).toLowerCase();
                const isSearchInput = label.includes('search');

                // Keep Enter available for search boxes, but block accidental
                // Enter submission in create/update/check-in data-entry fields.
                if (e.key === 'Enter' && isTextInput && !isSearchInput) {
                    e.preventDefault();
                    e.stopPropagation();
                    return false;
                }
            }, true);
        }
        </script>
        """,
        height=0,
        width=0,
    )


prevent_enter_to_submit()


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


def read_df(query, params=()):
    with conn() as c:
        return pd.read_sql_query(query, c, params=params)


def execute(query, params=()):
    with conn() as c:
        cur = c.cursor()
        cur.execute(query, params)
        c.commit()
        return cur.lastrowid


def current_operator():
    return st.session_state.get("operator_name", "SSC Admin")


def get_events():
    return read_df(
        """
        SELECT e.event_id, e.event_name, e.start_datetime, e.end_datetime,
               e.age_rating, e.price_per_ticket, e.event_description,
               l.location_id, l.location_name, l.street_number, l.city, l.country,
               et.etype_id, et.etype_name
        FROM events e
        JOIN locations l ON e.location_id = l.location_id
        JOIN event_types et ON e.event_type_id = et.etype_id
        WHERE COALESCE(e.is_deleted, 0) = 0
          AND COALESCE(l.is_deleted, 0) = 0
          AND COALESCE(et.is_deleted, 0) = 0
        ORDER BY datetime(e.start_datetime) DESC
        """
    )


def get_locations():
    return read_df("SELECT * FROM locations WHERE COALESCE(is_deleted,0)=0 ORDER BY location_name")


def get_event_types():
    return read_df("SELECT * FROM event_types WHERE COALESCE(is_deleted,0)=0 ORDER BY etype_name")


def next_code(table, id_col, prefix, width):
    """Generate IDs such as L001 or P0001 by reading the largest existing number."""
    with conn() as c:
        rows = c.execute(f"SELECT {id_col} FROM {table}").fetchall()
    max_num = 0
    for r in rows:
        val = str(r[0] or "")
        if not val.upper().startswith(prefix.upper()):
            continue
        digits = "".join(ch for ch in val if ch.isdigit())
        if digits:
            max_num = max(max_num, int(digits))
    return f"{prefix}{max_num + 1:0{width}d}"


def next_participant_id():
    return next_code("participants", "participant_id", "P", 4)


def next_location_id():
    # Existing structure: L001, L002, ...
    return next_code("locations", "location_id", "L", 3)


def make_event_type_base(name):
    """Create a readable 3-letter event-type code from the name.

    Rules:
    - 1 word: first 3 letters, e.g. Workshop -> WOR.
    - 2 words: first 2 letters of word 1 + first letter of word 2, e.g. Company Visit -> COV.
    - 3+ words: initials of first 3 words, e.g. Data Science Workshop -> DSW.
    """
    words = ["".join(ch for ch in w.upper() if ch.isalnum()) for w in str(name).split()]
    words = [w for w in words if w]
    if not words:
        return "TYP"
    if len(words) == 1:
        return words[0][:3].ljust(3, "X")
    if len(words) == 2:
        return (words[0][:2] + words[1][:1]).ljust(3, "X")
    return "".join(w[0] for w in words[:3]).ljust(3, "X")


def next_etype_id(type_name):
    base = make_event_type_base(type_name)
    with conn() as c:
        existing = {str(r[0]).upper() for r in c.execute("SELECT etype_id FROM event_types").fetchall()}
    if base not in existing:
        return base
    for i in range(2, 100):
        candidate = f"{base}{i}"
        if candidate not in existing:
            return candidate
    raise ValueError("Could not generate a unique event type ID.")


def next_event_id():
    with conn() as c:
        max_id = c.execute("SELECT MAX(event_id) FROM events").fetchone()[0]
    return int(max_id or 0) + 1


def next_registration_id(event_id):
    """Generate registration IDs like 251001, 251002 for event_id 251."""
    prefix = str(int(event_id))
    with conn() as c:
        rows = c.execute(
            "SELECT registration_id FROM event_registration WHERE event_id = ?",
            (event_id,),
        ).fetchall()
    max_seq = 0
    for r in rows:
        rid = str(r[0])
        if rid.startswith(prefix):
            suffix = rid[len(prefix):]
            if suffix.isdigit():
                max_seq = max(max_seq, int(suffix))
    return int(f"{prefix}{max_seq + 1:03d}")


def bool_to_db(value):
    if value == "Unknown / not filled":
        return None
    return 1 if value == "Yes" else 0


def db_to_bool_label(value):
    if pd.isna(value) or value is None:
        return "Unknown / not filled"
    return "Yes" if int(value) == 1 else "No"


def dob_to_date(value):
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


def find_participant_by_email(email):
    with conn() as c:
        return c.execute(
            "SELECT * FROM participants WHERE lower(email)=lower(?)", (email.strip(),)
        ).fetchone()


def duplicate_participant_notice(email, label="participant"):
    """Deprecated: participant de-duplication is now background-only.

    The registration UI should warn only when an email is already registered
    for the selected event, not merely because the participant exists in the
    central participants table.
    """
    return


def existing_registration_by_email(event_id, email):
    """Return an active registration for this event that already contains this email.

    Participant lookup/deduplication remains a background database operation,
    but duplicate event registration should be visible to the operator.
    """
    if not email:
        return None
    with conn() as c:
        return c.execute(
            """
            SELECT er.registration_id, er.status, p.participant_id, p.participant_name, p.email,
                   era.role, era.attendance_status
            FROM event_registration er
            JOIN event_registered_attendee era ON er.registration_id = era.registration_id
            JOIN participants p ON era.participant_id = p.participant_id
            WHERE er.event_id = ?
              AND lower(p.email) = lower(?)
              AND COALESCE(er.status, 'registered') != 'cancelled'
            ORDER BY er.registration_id DESC
            LIMIT 1
            """,
            (int(event_id), email.strip()),
        ).fetchone()


def duplicate_registration_notice(event_id, email, label="participant"):
    existing = existing_registration_by_email(event_id, email)
    if existing:
        st.warning(
            f"This {label} email is already registered for this event: "
            f"registration #{existing['registration_id']}, "
            f"{existing['participant_name'] or '-'} ({existing['email'] or '-'}), "
            f"role: {existing['role'] or '-'}, status: {existing['attendance_status'] or '-'} ."
        )


def upsert_participant(data):
    existing = find_participant_by_email(data["email"])
    dob_value = data.get("dob")
    if isinstance(dob_value, (date, datetime)):
        dob_value = dob_value.isoformat()[:10]

    if existing:
        pid = existing["participant_id"]
        execute(
            """
            UPDATE participants
            SET participant_name = COALESCE(NULLIF(?, ''), participant_name),
                phone_number = COALESCE(NULLIF(?, ''), phone_number),
                place_of_residence = COALESCE(NULLIF(?, ''), place_of_residence),
                dob = COALESCE(NULLIF(?, ''), dob),
                in_groupchat = COALESCE(?, in_groupchat),
                have_connect = COALESCE(?, have_connect),
                marketing_subs = COALESCE(?, marketing_subs),
                organization = COALESCE(NULLIF(?, ''), organization)
            WHERE participant_id = ?
            """,
            (
                data.get("participant_name", ""), data.get("phone_number", ""),
                data.get("place_of_residence", ""), dob_value or "",
                data.get("in_groupchat"), data.get("have_connect"), data.get("marketing_subs"),
                data.get("organization", ""), pid,
            ),
        )
        return pid, "updated"

    pid = next_participant_id()
    payload = {
        "participant_id": pid,
        "participant_name": data["participant_name"],
        "email": data["email"].strip().lower(),
        "phone_number": data.get("phone_number") or None,
        "place_of_residence": data.get("place_of_residence") or None,
        "dob": dob_value,
        "in_groupchat": data.get("in_groupchat"),
        "have_connect": data.get("have_connect"),
        "marketing_subs": data.get("marketing_subs"),
        "organization": data.get("organization") or None,
    }
    execute(
        """
        INSERT INTO participants
        (participant_id, participant_name, email, phone_number, place_of_residence, dob,
         in_groupchat, have_connect, marketing_subs, organization)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (payload["participant_id"], payload["participant_name"], payload["email"], payload["phone_number"],
         payload["place_of_residence"], payload["dob"], payload["in_groupchat"], payload["have_connect"],
         payload["marketing_subs"], payload["organization"]),
    )
    repo.log_create("participant", pid, payload, current_operator())
    return pid, "created"




def create_participant_without_email(data):
    """Create a participant record for an attending guest without email.

    Guests only need name and optional email in the group registration UI.
    If email is missing, email stays NULL so multiple guests without email are allowed.
    """
    pid = next_participant_id()
    payload = {"participant_id": pid, "participant_name": data.get("participant_name") or "Guest", "email": None}
    execute(
        """
        INSERT INTO participants
        (participant_id, participant_name, email, phone_number, place_of_residence, dob,
         in_groupchat, have_connect, marketing_subs, organization)
        VALUES (?, ?, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)
        """,
        (pid, payload["participant_name"]),
    )
    repo.log_create("participant", pid, payload, current_operator())
    return pid

def update_participant_full(participant_id, data):
    dob_value = data.get("dob")
    if isinstance(dob_value, (date, datetime)):
        dob_value = dob_value.isoformat()[:10]
    execute(
        """
        UPDATE participants
        SET participant_name = ?, email = ?, phone_number = ?, place_of_residence = ?, dob = ?,
            in_groupchat = ?, have_connect = ?, marketing_subs = ?, organization = ?
        WHERE participant_id = ?
        """,
        (
            data.get("participant_name") or "", data.get("email") or None,
            data.get("phone_number") or None, data.get("place_of_residence") or None,
            dob_value or None, data.get("in_groupchat"), data.get("have_connect"),
            data.get("marketing_subs"), data.get("organization") or None, participant_id,
        ),
    )


def participant_to_data(row):
    """Convert a participant row into the form data dictionary used by update helpers."""
    if row is None:
        return {}
    return {
        "participant_name": row["participant_name"],
        "email": row["email"],
        "phone_number": row["phone_number"],
        "place_of_residence": row["place_of_residence"],
        "dob": dob_to_date(row["dob"]),
        "in_groupchat": row["in_groupchat"],
        "have_connect": row["have_connect"],
        "marketing_subs": row["marketing_subs"],
        "organization": row["organization"],
    }


def merge_attendee_participant(registration_id, old_participant_id, new_participant_id, data=None):
    """Relink an attendee row to an existing participant found by email.

    This handles the common case where a guest was registered without email,
    then provides an email at check-in that already belongs to an existing
    participant record. The attendee row should point to the existing identity,
    not keep a duplicate no-email participant.
    """
    old_pid = str(old_participant_id)
    new_pid = str(new_participant_id)
    reg_id = int(registration_id)
    if old_pid == new_pid:
        if data:
            update_participant_full(old_pid, data)
        return new_pid, "same"

    if data:
        update_participant_full(new_pid, data)

    with conn() as c:
        existing_link = c.execute(
            "SELECT 1 FROM event_registered_attendee WHERE registration_id=? AND participant_id=?",
            (reg_id, new_pid),
        ).fetchone()
        old_row = c.execute(
            "SELECT * FROM event_registered_attendee WHERE registration_id=? AND participant_id=?",
            (reg_id, old_pid),
        ).fetchone()
        if existing_link:
            # Existing participant is already linked to this registration; remove duplicate attendee row.
            c.execute(
                "DELETE FROM event_registered_attendee WHERE registration_id=? AND participant_id=?",
                (reg_id, old_pid),
            )
            action = "deduplicated"
        else:
            c.execute(
                "UPDATE event_registered_attendee SET participant_id=? WHERE registration_id=? AND participant_id=?",
                (new_pid, reg_id, old_pid),
            )
            action = "relinked"

        c.execute(
            "UPDATE event_registration SET registered_by=? WHERE registration_id=? AND registered_by=?",
            (new_pid, reg_id, old_pid),
        )
        c.execute(
            "UPDATE event_registration SET number_of_attendee = "
            "(SELECT COUNT(*) FROM event_registered_attendee WHERE registration_id=?) "
            "WHERE registration_id=?",
            (reg_id, reg_id),
        )
        # Hide temporary no-email participant records once they are replaced.
        c.execute(
            "UPDATE participants SET is_deleted=1 WHERE participant_id=? AND (email IS NULL OR trim(email)='')",
            (old_pid,),
        )
        c.commit()

    repo.log_create(
        "participant_merge",
        f"{reg_id}/{old_pid}->{new_pid}",
        {"registration_id": reg_id, "old_participant_id": old_pid, "new_participant_id": new_pid, "action": action},
        current_operator(),
    )
    return new_pid, action


def participant_already_registered(event_id, participant_id):
    with conn() as c:
        return c.execute(
            """
            SELECT 1
            FROM event_registration er
            JOIN event_registered_attendee era ON er.registration_id = era.registration_id
            WHERE er.event_id = ? AND era.participant_id = ?
              AND COALESCE(er.status, 'registered') != 'cancelled'
            LIMIT 1
            """,
            (event_id, participant_id),
        ).fetchone() is not None


def create_registration(event_id, participant_id, channel, source, notes, immediate_checkin=False):
    if participant_already_registered(event_id, participant_id):
        return None
    registration_id = next_registration_id(event_id)
    reg_payload = {"registration_id": registration_id, "registered_by": participant_id, "event_id": event_id, "number_of_attendee": 1, "channel": channel, "source": source or None, "status": "registered", "notes": notes or None}
    execute(
        """
        INSERT INTO event_registration
        (registration_id, registered_by, event_id, datetime_registered, number_of_attendee, channel, source, status, notes)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, 1, ?, ?, 'registered', ?)
        """,
        (registration_id, participant_id, event_id, channel, source or None, notes or None),
    )
    repo.log_create("registration", registration_id, reg_payload, current_operator())
    attendance_status = "check in" if immediate_checkin else "not check in"
    checkin_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if immediate_checkin else None
    att_payload = {"registration_id": registration_id, "participant_id": participant_id, "role": "main attendee", "need_buddy": 0, "attendance_status": attendance_status, "checkin_datetime": checkin_dt}
    execute(
        """
        INSERT INTO event_registered_attendee
        (registration_id, participant_id, role, need_buddy, attendance_status, checkin_datetime, payment_status, payment_method)
        VALUES (?, ?, 'main attendee', 0, ?, ?, NULL, NULL)
        """,
        (registration_id, participant_id, attendance_status, checkin_dt),
    )
    repo.log_create("attendee", f"{registration_id}/{participant_id}", att_payload, current_operator())
    return registration_id


def create_group_registration(event_id, main_participant_id, attendees, channel, source, notes, immediate_checkin=False):
    """Create one registration with multiple attendees.

    attendees should be a list of dicts containing participant_id and role.
    The main registrant may or may not be included as an attendee.
    """
    if not attendees:
        return None, ["No attendees were selected for this registration."]

    skipped = []
    valid_attendees = []
    for attendee in attendees:
        pid = attendee["participant_id"]
        if participant_already_registered(event_id, pid):
            skipped.append(attendee.get("label") or pid)
        else:
            valid_attendees.append(attendee)

    if not valid_attendees:
        return None, skipped

    registration_id = next_registration_id(event_id)
    reg_payload = {"registration_id": registration_id, "registered_by": main_participant_id, "event_id": event_id, "number_of_attendee": len(valid_attendees), "channel": channel, "source": source or None, "status": "registered", "notes": notes or None}
    execute(
        """
        INSERT INTO event_registration
        (registration_id, registered_by, event_id, datetime_registered, number_of_attendee, channel, source, status, notes)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, 'registered', ?)
        """,
        (registration_id, main_participant_id, event_id, len(valid_attendees), channel, source or None, notes or None),
    )
    repo.log_create("registration", registration_id, reg_payload, current_operator())
    attendance_status = "check in" if immediate_checkin else "not check in"
    checkin_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if immediate_checkin else None
    for attendee in valid_attendees:
        att_payload = {"registration_id": registration_id, "participant_id": attendee["participant_id"], "role": attendee.get("role", "guests"), "need_buddy": attendee.get("need_buddy"), "attendance_status": attendance_status, "checkin_datetime": checkin_dt}
        execute(
            """
            INSERT INTO event_registered_attendee
            (registration_id, participant_id, role, need_buddy, attendance_status, checkin_datetime, payment_status, payment_method)
            VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)
            """,
            (
                registration_id,
                attendee["participant_id"],
                attendee.get("role", "guests"),
                attendee.get("need_buddy"),
                attendance_status,
                checkin_dt,
            ),
        )
        repo.log_create("attendee", f"{registration_id}/{attendee['participant_id']}", att_payload, current_operator())
    return registration_id, skipped

def attendee_df(event_id, include_attended=True):
    attended_filter = "" if include_attended else "AND COALESCE(era.attendance_status, 'not check in') != 'check in'"
    return read_df(
        f"""
        SELECT
            er.registration_id,
            er.registered_by,
            rb.participant_name AS registered_by_name,
            p.participant_id,
            p.participant_name AS name,
            p.email,
            p.phone_number AS phone,
            p.place_of_residence AS residence,
            p.dob,
            p.organization,
            p.in_groupchat,
            p.have_connect,
            p.marketing_subs,
            era.role,
            er.channel,
            er.source,
            er.datetime_registered,
            era.attendance_status,
            era.checkin_datetime
        FROM event_registration er
        JOIN event_registered_attendee era ON er.registration_id = era.registration_id
        JOIN participants p ON era.participant_id = p.participant_id
        LEFT JOIN participants rb ON er.registered_by = rb.participant_id
        WHERE er.event_id = ?
          AND COALESCE(p.is_deleted, 0) = 0
          AND COALESCE(er.status, 'registered') != 'cancelled'
          {attended_filter}
        ORDER BY
            CASE WHEN era.attendance_status = 'check in' THEN 1 ELSE 0 END,
            lower(p.participant_name)
        """,
        (event_id,),
    )


def filter_df(df, query):
    """Filter attendee table.

    If a query matches any person in a group registration, return the whole
    registration group so staff can check in the main attendee and all guests
    from the same registration together.
    """
    if not query or df.empty:
        return df
    q = query.lower().strip()
    text_cols = [
        "registration_id", "registered_by_name", "name", "email", "phone",
        "organization", "channel", "source", "attendance_status", "residence", "role"
    ]
    mask = pd.Series(False, index=df.index)
    for col in text_cols:
        if col in df.columns:
            mask = mask | df[col].fillna("").astype(str).str.lower().str.contains(q, regex=False)

    matched_registration_ids = df.loc[mask, "registration_id"].dropna().unique()
    if len(matched_registration_ids) == 0:
        return df.iloc[0:0]
    return df[df["registration_id"].isin(matched_registration_ids)]


def check_in(registration_id, participant_id):
    """Mark one attendee as checked in.

    Cast values to native Python types first. Streamlit/pandas can pass numpy
    scalar values from a dataframe selection, and sqlite3 may bind those in a
    way that does not match the INTEGER/VARCHAR composite primary key.
    Returns the number of rows updated so the UI can confirm the write worked.
    """
    reg_id = int(registration_id)
    pid = str(participant_id)
    with conn() as c:
        cur = c.execute(
            """
            UPDATE event_registered_attendee
            SET attendance_status = 'check in',
                checkin_datetime = CURRENT_TIMESTAMP
            WHERE registration_id = ?
              AND participant_id = ?
              AND COALESCE(attendance_status, 'not check in') != 'check in'
            """,
            (reg_id, pid),
        )
        c.commit()
        return cur.rowcount


def event_metrics(event_id):
    df = attendee_df(event_id)
    total = len(df)
    attended = int((df["attendance_status"] == "check in").sum()) if not df.empty else 0
    no_show = int((df["attendance_status"] == "no show").sum()) if not df.empty else 0
    not_checked = int((df["attendance_status"].fillna("not check in") == "not check in").sum()) if not df.empty else 0
    rate = attended / total if total else 0
    return df, total, attended, not_checked, rate, no_show


def event_stats_df():
    return read_df(
        """
        SELECT
            e.event_id,
            COUNT(DISTINCT CASE WHEN COALESCE(er.status, 'registered') != 'cancelled' THEN er.registration_id END) AS registered_count,
            SUM(CASE WHEN COALESCE(er.status, 'registered') != 'cancelled' AND era.attendance_status = 'check in' THEN 1 ELSE 0 END) AS attended_count
        FROM events e
        LEFT JOIN event_registration er ON e.event_id = er.event_id
        LEFT JOIN event_registered_attendee era ON er.registration_id = era.registration_id
        GROUP BY e.event_id
        """
    )


def header():
    st.markdown(
        """
        <div class="app-header">
            <div class="app-title">SSC Event Management</div>
            <p class="app-subtitle">Manage events, registrations, check-in, and analytics connected to SQLite.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def flash_success(message):
    st.session_state["flash_success"] = message


def show_flash():
    message = st.session_state.pop("flash_success", None)
    if message:
        st.success(message)


def bump_form_version(name):
    key = f"{name}_version"
    st.session_state[key] = int(st.session_state.get(key, 0)) + 1


def event_status_label(start_value, end_value=None):
    now = pd.Timestamp.now()
    start = pd.to_datetime(start_value, errors="coerce")
    end = pd.to_datetime(end_value, errors="coerce") if end_value is not None else pd.NaT
    if pd.isna(start):
        return "Unknown"
    if pd.notna(end) and start <= now <= end:
        return "Ongoing"
    if start > now:
        return "Upcoming"
    return "Completed"


def open_event(event_id):
    st.session_state["selected_event_id_override"] = int(event_id)
    st.session_state["main_nav"] = "Event Workspace"


def event_card(row, kind="upcoming"):
    registered = int(row.get("registered_count", 0) or 0)
    attended = int(row.get("attended_count", 0) or 0)
    status = event_status_label(row.get("start_datetime"), row.get("end_datetime"))
    image_label = status if status != "Unknown" else ("Upcoming" if kind == "upcoming" else "Past Event")
    rate = f"{(attended / registered):.0%}" if registered else "-"
    st.markdown(
        f"""
        <div class="event-card">
            <div class="event-banner"><span class="status-pill">{image_label}</span></div>
            <h4 style="margin:.1rem 0 .3rem 0;color:#F8FAFC;">{row['event_name']}</h4>
            <div class="small-muted">📍 {row.get('location_name') or '-'} · {row.get('etype_name') or '-'}</div>
            <div class="small-muted">🕒 {row.get('start_datetime') or '-'}</div>
            <hr style="margin:.85rem 0;border-color:rgba(148,163,184,.22);">
            <div style="display:flex;gap:1rem;flex-wrap:wrap;">
                <span><b>{registered}</b><span class="small-muted"> registered</span></span>
                <span><b>{attended}</b><span class="small-muted"> attended</span></span>
                <span><b>{rate}</b><span class="small-muted"> rate</span></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def home_page():
    header()
    events = get_events()
    stats = event_stats_df()
    if not events.empty:
        events = events.merge(stats, on="event_id", how="left")
    total_events = len(events)
    total_participants = read_df("SELECT COUNT(*) AS n FROM participants WHERE COALESCE(is_deleted,0)=0").iloc[0]["n"]
    total_regs = read_df("SELECT COUNT(*) AS n FROM event_registration").iloc[0]["n"]
    total_attended = read_df("SELECT COUNT(*) AS n FROM event_registered_attendee WHERE attendance_status='check in'").iloc[0]["n"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Events", total_events)
    c2.metric("Participants", int(total_participants))
    c3.metric("Registrations", int(total_regs))
    c4.metric("Total checked in", int(total_attended))

    if events.empty:
        st.info("No events yet. Create your first event in Create Event.")
        return

    now = pd.Timestamp.now()
    events["start_ts"] = pd.to_datetime(events["start_datetime"], errors="coerce")
    upcoming = events[events["start_ts"] >= now].sort_values("start_ts", ascending=True)
    past = events[events["start_ts"] < now].sort_values("start_ts", ascending=False)

    st.markdown("### Upcoming Events")
    if upcoming.empty:
        st.caption("No upcoming events yet.")
    else:
        cols = st.columns(3)
        for i, (_, row) in enumerate(upcoming.head(6).iterrows()):
            with cols[i % 3]:
                event_card(row, kind="upcoming")

    st.markdown("### Past Events")
    if past.empty:
        st.caption("No past events yet.")
    else:
        cols = st.columns(3)
        for i, (_, row) in enumerate(past.head(6).iterrows()):
            with cols[i % 3]:
                event_card(row, kind="past")


def create_event_page():
    header()
    show_flash()
    st.subheader("Create Event")

    location_form_version = st.session_state.get("location_form_version", 0)
    event_type_form_version = st.session_state.get("event_type_form_version", 0)
    event_form_version = st.session_state.get("event_form_version", 0)

    with st.expander("➕ Add new location", expanded=False):
        with st.container():
            st.caption(f"Next location ID: {next_location_id()}")
            loc_name = st.text_input("Location name *")
            street = st.text_input("Street + number *")
            c1, c2, c3 = st.columns(3)
            with c1:
                postal = st.text_input("Postal code")
            with c2:
                city = st.text_input("City")
            with c3:
                country = st.text_input("Country")
            capacity = st.text_input("Capacity info")
            access = st.text_area("Accessibility info")
            desc = st.text_area("Location description")
            if st.button("Add Location", use_container_width=True):
                if not loc_name or not street:
                    st.error("Location name and street number are required.")
                else:
                    existing_location = read_df(
                        """
                        SELECT location_id, location_name
                        FROM locations
                        WHERE lower(trim(location_name)) = lower(trim(?))
                          AND lower(trim(street_number)) = lower(trim(?))
                          AND COALESCE(is_deleted,0)=0
                        LIMIT 1
                        """,
                        (loc_name, street),
                    )
                    if not existing_location.empty:
                        st.warning(f"Location already exists: {existing_location.iloc[0]['location_id']} — {existing_location.iloc[0]['location_name']}")
                        return
                    loc_id = next_location_id()
                    payload = {"location_id": loc_id, "location_name": loc_name, "street_number": street, "postal_code": postal or None, "city": city or None, "country": country or None, "capacity_info": capacity or None, "accessibility_info": access or None, "description": desc or None}
                    execute(
                        """
                        INSERT INTO locations
                        (location_id, location_name, street_number, postal_code, city, country, capacity_info, accessibility_info, description)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (payload["location_id"], payload["location_name"], payload["street_number"], payload["postal_code"], payload["city"], payload["country"],
                         payload["capacity_info"], payload["accessibility_info"], payload["description"]),
                    )
                    repo.log_create("location", loc_id, payload, current_operator())
                    flash_success(f"Added location {loc_id}: {loc_name}")
                    bump_form_version("location_form")
                    st.rerun()

    with st.expander("➕ Add new event type", expanded=False):
        with st.container():
            type_name = st.text_input("Event type name *")
            st.caption("Event type ID is generated from the name, e.g. Sports → SPO, Company Visit → COV, Data Science Workshop → DSW.")
            type_desc = st.text_area("Event type description")
            if st.button("Add Event Type", use_container_width=True):
                if not type_name:
                    st.error("Event type name is required.")
                else:
                    existing_type = read_df(
                        """
                        SELECT etype_id, etype_name
                        FROM event_types
                        WHERE lower(trim(etype_name)) = lower(trim(?))
                          AND COALESCE(is_deleted,0)=0
                        LIMIT 1
                        """,
                        (type_name,),
                    )
                    if not existing_type.empty:
                        st.warning(f"Event type already exists: {existing_type.iloc[0]['etype_id']} — {existing_type.iloc[0]['etype_name']}")
                        return
                    etype_id = next_etype_id(type_name)
                    payload = {"etype_id": etype_id, "etype_name": type_name, "description": type_desc or None}
                    execute(
                        "INSERT INTO event_types (etype_id, etype_name, description) VALUES (?, ?, ?)",
                        (payload["etype_id"], payload["etype_name"], payload["description"]),
                    )
                    repo.log_create("event_type", etype_id, payload, current_operator())
                    flash_success(f"Added event type {etype_id}: {type_name}")
                    bump_form_version("event_type_form")
                    st.rerun()

    locations = get_locations()
    types = get_event_types()
    if locations.empty or types.empty:
        st.error("Create at least one location and one event type first.")
        return

    st.markdown("### Event Details")
    with st.container():
        st.caption(f"Next event ID: {next_event_id()}")
        event_name = st.text_input("Event name *")
        loc_label = st.selectbox("Location *", locations.apply(lambda r: f"{r['location_id']} — {r['location_name']}", axis=1))
        type_label = st.selectbox("Event type *", types.apply(lambda r: f"{r['etype_id']} — {r['etype_name']}", axis=1))
        c1, c2 = st.columns(2)
        with c1:
            start_date = st.date_input("Start date")
            start_time = st.time_input("Start time", value=time(18, 0))
        with c2:
            end_date = st.date_input("End date")
            end_time = st.time_input("End time", value=time(20, 0))
        age_rating = st.text_input("Age rating")
        price = st.number_input("Price per ticket", min_value=0.0, step=1.0)
        desc = st.text_area("Description")
        submit = st.button("Create Event", use_container_width=True)
    if submit:
        if not event_name:
            st.error("Event name is required.")
            return
        location_id = loc_label.split(" — ")[0]
        etype_id = type_label.split(" — ")[0]
        start_dt = datetime.combine(start_date, start_time).strftime("%Y-%m-%d %H:%M:%S")
        end_dt = datetime.combine(end_date, end_time).strftime("%Y-%m-%d %H:%M:%S")
        existing_event = read_df(
            """
            SELECT event_id, event_name
            FROM events
            WHERE lower(trim(event_name)) = lower(trim(?))
              AND location_id = ?
              AND event_type_id = ?
              AND start_datetime = ?
              AND end_datetime = ?
              AND COALESCE(is_deleted,0)=0
            LIMIT 1
            """,
            (event_name, location_id, etype_id, start_dt, end_dt),
        )
        if not existing_event.empty:
            st.warning(f"Event already exists: #{existing_event.iloc[0]['event_id']} — {existing_event.iloc[0]['event_name']}")
            return
        event_id = next_event_id()
        payload = {"event_id": event_id, "location_id": location_id, "event_type_id": etype_id, "event_name": event_name, "start_datetime": start_dt, "end_datetime": end_dt, "age_rating": age_rating or None, "price_per_ticket": price, "event_description": desc or None}
        execute(
            """
            INSERT INTO events
            (event_id, location_id, event_type_id, event_name, start_datetime, end_datetime, age_rating, price_per_ticket, event_description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (payload["event_id"], payload["location_id"], payload["event_type_id"], payload["event_name"], payload["start_datetime"], payload["end_datetime"], payload["age_rating"], payload["price_per_ticket"], payload["event_description"]),
        )
        repo.log_create("event", event_id, payload, current_operator())
        flash_success(f"Created event #{event_id}: {event_name}")
        bump_form_version("event_form")
        st.rerun()

    st.markdown("### Existing Events")
    events = get_events()
    if events.empty:
        st.caption("No events yet.")
    else:
        st.dataframe(events, use_container_width=True, hide_index=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Locations")
        st.dataframe(get_locations(), use_container_width=True, hide_index=True)
    with c2:
        st.markdown("### Event Types")
        st.dataframe(get_event_types(), use_container_width=True, hide_index=True)


def participant_inputs(prefix, require_email=True, require_name=True, compact=False):
    """Reusable participant input block.

    Participant duplicate handling is deliberately background-only here:
    when the form is submitted, the database reuses/updates an existing
    participant by email or creates a new participant if no email match exists.

    The form itself should not warn just because a participant already exists,
    because returning SSC participants can register for many different events.
    """
    email_label = "Email *" if require_email else "Email optional"
    c1, c2 = st.columns(2)
    with c1:
        email = st.text_input(email_label, key=f"{prefix}_email").strip().lower()
        name_label = "Participant name *" if require_name else "Participant name"
        name = st.text_input(name_label, key=f"{prefix}_name")
        phone = st.text_input("Phone number", key=f"{prefix}_phone")
        dob_value = None if compact else st.date_input(
            "Date of birth",
            value=None,
            min_value=DOB_MIN,
            max_value=DOB_MAX,
            format="YYYY-MM-DD",
            key=f"{prefix}_dob",
        )
    with c2:
        residence = st.text_input("Place of residence", key=f"{prefix}_residence")
        organization = st.text_input("Organization", key=f"{prefix}_organization")
        in_groupchat = st.selectbox("In SSC groupchat?", BOOL_OPTIONS, key=f"{prefix}_groupchat")
        have_connect = st.selectbox("Have Connect account?", BOOL_OPTIONS, key=f"{prefix}_connect")
        marketing_subs = None if compact else st.selectbox("Marketing subscription?", BOOL_OPTIONS, key=f"{prefix}_marketing")
    return {
        "email": email,
        "participant_name": name,
        "phone_number": phone,
        "place_of_residence": residence,
        "dob": dob_value,
        "in_groupchat": bool_to_db(in_groupchat),
        "have_connect": bool_to_db(have_connect),
        "marketing_subs": None if compact else bool_to_db(marketing_subs),
        "organization": organization,
    }

def guest_inputs(prefix, full_info=False):
    """Guest fields for group registration.

    Guests are always written to the participants table. Email is optional.
    If a guest email is provided, the submit logic silently reuses/updates the
    existing participant with that email; otherwise a temporary no-email
    participant row is created and can be merged later during check-in.
    """
    if not full_info:
        c1, c2, c3 = st.columns([1.2, 1.4, 1])
        with c1:
            name = st.text_input("Guest name *", key=f"{prefix}_name")
        with c2:
            email = st.text_input("Guest email optional", key=f"{prefix}_email").strip().lower()
        with c3:
            need_buddy = st.selectbox("Need buddy?", BOOL_OPTIONS, key=f"{prefix}_need_buddy")
        return {
            "participant_name": name,
            "email": email,
            "need_buddy": bool_to_db(need_buddy),
        }

    st.caption("Full guest information is optional except guest name. Email is still optional for guests.")
    c1, c2 = st.columns(2)
    with c1:
        email = st.text_input("Guest email optional", key=f"{prefix}_email").strip().lower()
        name = st.text_input("Guest name *", key=f"{prefix}_name")
        phone = st.text_input("Phone number", key=f"{prefix}_phone")
        dob_value = st.date_input(
            "Date of birth",
            value=None,
            min_value=DOB_MIN,
            max_value=DOB_MAX,
            format="YYYY-MM-DD",
            key=f"{prefix}_dob",
        )
    with c2:
        residence = st.text_input("Place of residence", key=f"{prefix}_residence")
        organization = st.text_input("Organization", key=f"{prefix}_organization")
        in_groupchat = st.selectbox("In SSC groupchat?", BOOL_OPTIONS, key=f"{prefix}_groupchat")
        have_connect = st.selectbox("Have Connect account?", BOOL_OPTIONS, key=f"{prefix}_connect")
        marketing_subs = st.selectbox("Marketing subscription?", BOOL_OPTIONS, key=f"{prefix}_marketing")
        need_buddy = st.selectbox("Need buddy?", BOOL_OPTIONS, key=f"{prefix}_need_buddy")
    return {
        "participant_name": name,
        "email": email,
        "phone_number": phone,
        "place_of_residence": residence,
        "dob": dob_value,
        "in_groupchat": bool_to_db(in_groupchat),
        "have_connect": bool_to_db(have_connect),
        "marketing_subs": bool_to_db(marketing_subs),
        "organization": organization,
        "need_buddy": bool_to_db(need_buddy),
    }

def get_or_create_participant_from_form(data, email_required=True):
    if email_required and not data.get("email"):
        raise ValueError("Email is required.")
    if not data.get("participant_name"):
        raise ValueError("Participant name is required.")
    if data.get("email"):
        pid, action = upsert_participant(data)
    else:
        pid = create_participant_without_email(data)
        action = "created"
    return pid, action


def quick_walkin_box(event_id):
    """Quick walk-in mode removed. Use the Walk-In tab instead.

    The Walk-In tab supports solo and group walk-ins, writes guests to the
    participants table, and marks all attending people as checked in immediately.
    """
    return

def registration_summary_box(registration_type, registrant_name, registrant_email, channel, source, main_attends=True, main_attendee=None, guests=None, walk_in=False):
    guests = guests or []
    with st.expander("Registration summary", expanded=True):
        st.write(f"**Mode:** {'Walk-in' if walk_in else 'Pre-event registration'}")
        st.write(f"**Type:** {registration_type}")
        st.write(f"**Registrant:** {registrant_name or '-'} ({registrant_email or '-'})")
        if registration_type == "Group":
            if main_attends:
                st.write("**Main attendee:** registrant")
            elif main_attendee:
                st.write(f"**Main attendee:** {main_attendee.get('participant_name') or '-'} ({main_attendee.get('email') or '-'})")
            valid_guest_names = [g.get("participant_name") for g in guests if g.get("participant_name")]
            st.write(f"**Guests entered:** {len(valid_guest_names)}" + (f" — {', '.join(valid_guest_names[:6])}" if valid_guest_names else ""))
        st.write(f"**Channel:** {channel}")
        st.write(f"**Source:** {source or '-'}")


def registration_form(event_id, walk_in=False):
    """Unified registration form.

    There is no user-facing Solo/Group split. The form always records:
    registrant -> optional separate main attendee -> optional guests.
    Solo/group type is inferred from number_of_attendee in event_registration.
    If channel is walk-in, all attendee rows are created as check in immediately.
    """
    form_scope = "registration"
    st.subheader("Make Registration")
    st.caption("Use one form for all registrations. Solo vs group is inferred from the number of attendees. If channel = walk-in, all attendees are checked in immediately.")
    show_flash()

    reg_form_version = st.session_state.get(f"{form_scope}_form_version", 0)

    # Registration and admin editors intentionally avoid st.form.
    # Button-only actions prevent accidental Enter-to-submit behavior.
    st.markdown("#### Registration details")
    r1, r2 = st.columns([1, 2])
    with r1:
        channel = st.selectbox("Registration channel *", REGISTRATION_CHANNELS, key=f"{form_scope}_reg_channel_{reg_form_version}")
    with r2:
        source = st.text_input("Source: how did they hear about SSC/event?", key=f"{form_scope}_reg_source_{reg_form_version}")

    immediate_checkin = (channel == "walk-in")
    if immediate_checkin:
        st.success("Walk-in selected: all attendees in this registration will be checked in immediately.")
    else:
        st.caption("WhatsApp/Connect registrations will be checked in later from the Check-In tab.")

    st.divider()
    st.markdown("#### Main registrant")
    st.caption("The main registrant is the person responsible for the registration. Email is compulsory.")
    main_data = participant_inputs(f"{form_scope}_main_{reg_form_version}", require_email=True, require_name=True, compact=False)
    duplicate_registration_notice(event_id, main_data.get("email"), "registrant")

    st.divider()
    main_attends = st.checkbox("Registrant will also attend", value=True, key=f"{form_scope}_registrant_will_attend_{reg_form_version}")
    main_attendee_data = None
    if main_attends:
        st.info("Registrant will be recorded as the main attendee.")
        main_attendee_need_buddy = bool_to_db(st.selectbox("Registrant/main attendee needs buddy?", BOOL_OPTIONS, key=f"{form_scope}_main_registrant_need_buddy_{reg_form_version}"))
    else:
        st.warning("Registrant is not attending. A separate main attendee is required below, including compulsory email.")
        st.markdown("#### Main attendee")
        main_attendee_data = participant_inputs(f"{form_scope}_main_attendee_{reg_form_version}", require_email=True, require_name=True, compact=True)
        duplicate_registration_notice(event_id, main_attendee_data.get("email"), "main attendee")
        main_attendee_need_buddy = bool_to_db(st.selectbox("Main attendee needs buddy?", BOOL_OPTIONS, key=f"{form_scope}_main_attendee_need_buddy_{reg_form_version}"))

    st.divider()
    guest_count = st.number_input(
        "Number of guests",
        min_value=0,
        max_value=10,
        value=0,
        step=1,
        key=f"{form_scope}_guest_count_{reg_form_version}",
        help="Pressing Enter here only updates the guest fields; it will not submit the registration."
    )
    collect_full_guest_info = False
    if immediate_checkin and int(guest_count) > 0:
        collect_full_guest_info = st.checkbox(
            "Collect full guest info for walk-in guests",
            value=False,
            key=f"{form_scope}_collect_full_guest_info_{reg_form_version}",
            help="If selected, each guest can provide phone, DOB, residence, organization, groupchat, Connect, and marketing fields. Guest email remains optional."
        )

    guest_data = []
    if int(guest_count) > 0:
        st.markdown("#### Guest information")
        if collect_full_guest_info:
            st.caption("Walk-in full guest mode: guest name is required; email and other participant details are optional but saved to the participants table when provided.")
        else:
            st.caption("Guests only need name and optional email. Buddy preference is optional. Every attending guest will be added to participants and event_registered_attendee.")
        for i in range(int(guest_count)):
            with st.expander(f"Guest {i + 1}", expanded=True):
                g = guest_inputs(f"{form_scope}_guest_{reg_form_version}_{i}", full_info=collect_full_guest_info)
                duplicate_registration_notice(event_id, g.get("email"), f"guest {i + 1}")
                guest_data.append(g)

    notes = st.text_area("Notes", key=f"{form_scope}_reg_notes_{reg_form_version}")

    # Derived registration type only for display; the database stores the count.
    estimated_count = 1 + len([g for g in guest_data if g.get("participant_name")])
    derived_type = "Solo" if estimated_count == 1 else "Group"
    registration_summary_box(
        derived_type,
        main_data.get("participant_name"),
        main_data.get("email"),
        channel,
        source,
        main_attends,
        main_attendee_data,
        guest_data,
        immediate_checkin,
    )
    st.caption(f"Calculated number_of_attendee: {estimated_count} ({derived_type})")

    button_label = "Create Registration + CHECK-IN" if immediate_checkin else "Create / Update Registration"
    submitted = st.button(button_label, use_container_width=True, type="primary", key=f"{form_scope}_submit_button_{reg_form_version}")

    if submitted:
        try:
            main_pid, main_action = get_or_create_participant_from_form(main_data, email_required=True)
        except ValueError as exc:
            st.error(str(exc))
            return

        attendees = []
        if main_attends:
            attendees.append({
                "participant_id": main_pid,
                "role": "main attendee",
                "need_buddy": main_attendee_need_buddy,
                "label": main_data.get("participant_name") or main_data.get("email") or main_pid,
            })
        else:
            try:
                main_attendee_pid, _ = get_or_create_participant_from_form(main_attendee_data or {}, email_required=True)
                attendees.append({
                    "participant_id": main_attendee_pid,
                    "role": "main attendee",
                    "need_buddy": main_attendee_need_buddy,
                    "label": (main_attendee_data or {}).get("participant_name") or (main_attendee_data or {}).get("email") or main_attendee_pid,
                })
            except ValueError as exc:
                st.error(f"Main attendee: {exc}")
                return

        guest_errors = []
        for idx, gdata in enumerate(guest_data, start=1):
            if not gdata.get("participant_name"):
                guest_errors.append(f"Guest {idx} needs a name.")
                continue
            try:
                gpid, _ = get_or_create_participant_from_form(gdata, email_required=False)
                attendees.append({
                    "participant_id": gpid,
                    "role": "guests",
                    "need_buddy": gdata.get("need_buddy"),
                    "label": gdata.get("participant_name") or gdata.get("email") or gpid,
                })
            except ValueError as exc:
                guest_errors.append(f"Guest {idx}: {exc}")

        if guest_errors:
            st.error("Please fix: " + "; ".join(guest_errors))
            return
        if not attendees:
            st.error("At least one person must attend.")
            return

        # One-row attendance is still created through the group helper so number_of_attendee
        # is always calculated from actual attendee rows.
        reg_id, skipped = create_group_registration(event_id, main_pid, attendees, channel, source, notes, immediate_checkin)
        if reg_id is None:
            st.warning("No new attendees were added. They may already be registered for this event.")
        else:
            final_count = len(attendees) - len(skipped)
            final_type = "Solo" if final_count == 1 else "Group"
            msg = f"{final_type} registration #{reg_id} created with {final_count} attendee(s)."
            if immediate_checkin:
                msg += " All attendees were checked in immediately."
            if not main_attends:
                msg += " Registrant is recorded as registered_by, while the separate main attendee is recorded as an attendee."
            flash_success(msg + ((" Skipped already-registered attendee(s): " + ", ".join(map(str, skipped))) if skipped else ""))
            bump_form_version(f"{form_scope}_form")
            st.rerun()
        if skipped:
            st.info("Skipped already-registered attendee(s): " + ", ".join(map(str, skipped)))

def _remaining_pending_matches_after_checkin(event_id, search_query):
    """Return how many pending attendees would still match the current search after a check-in.

    If one member of a group still matches, filter_df keeps the full pending group visible.
    Used to decide whether to preserve or clear the search box after check-in.
    """
    remaining_df = attendee_df(event_id, include_attended=False)
    return len(filter_df(remaining_df, search_query))


def _clear_checkin_search(event_id):
    st.session_state[f"checkin_search_version_{event_id}"] = int(st.session_state.get(f"checkin_search_version_{event_id}", 0)) + 1


def checkin_page(event_id):
    st.subheader("Check-In")
    show_flash()
    all_df = attendee_df(event_id, include_attended=True)
    registered_total = len(all_df)
    checked_total = int((all_df["attendance_status"].fillna("").str.lower() == "check in").sum()) if not all_df.empty else 0
    pending_total = max(registered_total - checked_total, 0)
    b1, b2, b3 = st.columns(3)
    b1.metric("Registered attendees", registered_total)
    b2.metric("Checked in", checked_total)
    b3.metric("Remaining", pending_total)
    df = attendee_df(event_id, include_attended=False)
    if df.empty:
        st.info("No pending attendees for this event. Everyone may already be checked in, cancelled at registration level, or not registered yet.")
        return

    search_version = int(st.session_state.get(f"checkin_search_version_{event_id}", 0))
    q = st.text_input(
        "Search pending attendees",
        placeholder="Type name, email, phone, organization, registration ID, source, channel, status...",
        help="Already checked-in people are hidden. If the search matches anyone in a group registration, the full pending group appears.",
        key=f"checkin_search_{event_id}_{search_version}",
    )
    filtered = filter_df(df, q)
    total = len(df)
    shown = len(filtered)
    st.caption(f"Showing {shown} of {total} pending attendees. Already checked-in attendees are hidden from this search list.")

    display = filtered[[
        "name", "email", "phone", "organization", "residence", "role", "registered_by_name", "channel", "source",
        "attendance_status", "checkin_datetime"
    ]].copy()
    display.columns = ["Name", "Email", "Phone", "Organization", "Residence", "Role", "Registered by", "Channel", "Source", "Status", "Check-in time"]
    st.dataframe(display, use_container_width=True, hide_index=True)

    if filtered.empty:
        st.warning("No pending attendee matches your search.")
        return

    st.markdown("### Selected Attendee")
    options = []
    option_map = {}
    for _, r in filtered.iterrows():
        label = f"{r['name']} | {r['email'] or '-'} | {r['role']} | registration #{r['registration_id']}"
        options.append(label)
        option_map[label] = (r["registration_id"], r["participant_id"])
    selected = st.selectbox("Choose participant to check in", options)
    selected_reg, selected_pid = option_map[selected]
    row = filtered[(filtered["registration_id"] == selected_reg) & (filtered["participant_id"] == selected_pid)].iloc[0]

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("Current status", row.get("attendance_status") or "not check in")
        c2.metric("Role", row.get("role") or "-")
        c3.metric("Registered by", row.get("registered_by_name") or "-")
        st.caption(f"Channel: {row['channel'] or '-'} · Source: {row['source'] or '-'} · Registration #{row['registration_id']}")

        # Fast path for event-day operations: check in immediately without opening the edit form.
        if st.button("✅ CHECK-IN", key=f"fast_checkin_{row['registration_id']}_{row['participant_id']}", use_container_width=True):
            updated = check_in(row["registration_id"], row["participant_id"])
            if updated:
                remaining_matches = _remaining_pending_matches_after_checkin(event_id, q)
                if remaining_matches > 0:
                    flash_success(f"✅ {row['name']} checked in successfully. {remaining_matches} pending result(s) still match this search.")
                else:
                    flash_success(f"✅ {row['name']} checked in successfully. No pending results remain for this search, so the search was cleared.")
                    _clear_checkin_search(event_id)
            else:
                flash_success("⚠️ No row was updated. This attendee may already be checked in or the selected row no longer exists.")
            st.rerun()

        # This edit section uses versioned widget keys so after pressing
        # Update Info + CHECK-IN the widgets reset/close on rerun instead of
        # keeping stale values from the previous selected attendee.
        edit_version_key = f"checkin_edit_version_{event_id}_{row['registration_id']}_{row['participant_id']}"
        edit_version = int(st.session_state.get(edit_version_key, 0))
        edit_prefix = f"checkin_edit_{event_id}_{row['registration_id']}_{row['participant_id']}_{edit_version}"

        with st.expander("Add / update participant info", expanded=False):
            st.caption(
                "Use this when information is missing or wrong. If you enter an email that already exists, "
                "the attendee row can be linked to that existing participant instead of creating a duplicate."
            )
            with st.container():
                a, b = st.columns(2)
                with a:
                    name = st.text_input("Participant name *", value=row["name"] or "", key=f"{edit_prefix}_name")
                    email = st.text_input("Email", value=row["email"] or "", key=f"{edit_prefix}_email").strip().lower()
                    if email:
                        email_match = find_participant_by_email(email)
                        if email_match and str(email_match["participant_id"]) != str(row["participant_id"]):
                            st.warning(
                                f"Email already belongs to existing participant {email_match['participant_id']} — "
                                f"{email_match['participant_name'] or '-'} ({email_match['email']}). "
                                "Submitting will relink this attendee to the existing participant and archive the temporary no-email record when applicable."
                            )
                    phone = st.text_input("Phone number", value=row["phone"] or "", key=f"{edit_prefix}_phone")
                    dob_value = st.date_input(
                        "Date of birth",
                        value=dob_to_date(row["dob"]),
                        min_value=DOB_MIN,
                        max_value=DOB_MAX,
                        format="YYYY-MM-DD",
                        key=f"{edit_prefix}_dob",
                    )
                with b:
                    residence = st.text_input("Place of residence", value=row["residence"] or "", key=f"{edit_prefix}_residence")
                    organization = st.text_input("Organization", value=row["organization"] or "", key=f"{edit_prefix}_organization")
                    in_groupchat = st.selectbox(
                        "In SSC groupchat?",
                        BOOL_OPTIONS,
                        index=BOOL_OPTIONS.index(db_to_bool_label(row["in_groupchat"])),
                        key=f"{edit_prefix}_in_groupchat",
                    )
                    have_connect = st.selectbox(
                        "Have Connect account?",
                        BOOL_OPTIONS,
                        index=BOOL_OPTIONS.index(db_to_bool_label(row["have_connect"])),
                        key=f"{edit_prefix}_have_connect",
                    )
                    marketing_subs = st.selectbox(
                        "Marketing subscription?",
                        BOOL_OPTIONS,
                        index=BOOL_OPTIONS.index(db_to_bool_label(row["marketing_subs"])),
                        key=f"{edit_prefix}_marketing_subs",
                    )

                btn_a, btn_b = st.columns(2)
                save_only_clicked = btn_a.button("Save Info", key=f"{edit_prefix}_save_only", use_container_width=True)
                save_checkin_clicked = btn_b.button("Save Info + CHECK-IN", key=f"{edit_prefix}_update_checkin", use_container_width=True, type="primary")

            if save_only_clicked or save_checkin_clicked:
                if not name:
                    st.error("Name is required.")
                    return
                new_data = {
                    "participant_name": name,
                    "email": email or None,
                    "phone_number": phone,
                    "place_of_residence": residence,
                    "dob": dob_value,
                    "in_groupchat": bool_to_db(in_groupchat),
                    "have_connect": bool_to_db(have_connect),
                    "marketing_subs": bool_to_db(marketing_subs),
                    "organization": organization,
                }

                active_pid = str(row["participant_id"])
                relink_note = ""
                if email:
                    existing_by_email = find_participant_by_email(email)
                    if existing_by_email and str(existing_by_email["participant_id"]) != active_pid:
                        active_pid, merge_action = merge_attendee_participant(
                            row["registration_id"], row["participant_id"], existing_by_email["participant_id"], new_data
                        )
                        relink_note = f" Attendee identity was {merge_action} to existing participant {active_pid}."
                    else:
                        update_participant_full(active_pid, new_data)
                else:
                    update_participant_full(active_pid, new_data)

                updated = 0
                if save_checkin_clicked:
                    updated = check_in(row["registration_id"], active_pid)

                # Reset this edit form's widget state for the next run.
                st.session_state[edit_version_key] = edit_version + 1
                if save_checkin_clicked:
                    if updated:
                        remaining_matches = _remaining_pending_matches_after_checkin(event_id, q)
                        if remaining_matches > 0:
                            flash_success(f"✅ Participant info saved and {name} checked in.{relink_note} {remaining_matches} pending result(s) still match this search.")
                        else:
                            flash_success(f"✅ Participant info saved and {name} checked in.{relink_note} No pending results remain for this search, so the search was cleared.")
                            _clear_checkin_search(event_id)
                    else:
                        flash_success(f"⚠️ Participant info saved, but no attendee row changed. They may already be checked in.{relink_note}")
                else:
                    flash_success(f"✅ Participant info saved.{relink_note}")
                st.rerun()



def checked_in_attendee_list(event_id):
    st.subheader("Attendee List")
    st.caption("This list shows registered attendees who have already checked in for the selected event.")
    df = attendee_df(event_id, include_attended=True)
    if df.empty:
        st.info("No attendees found for this event yet.")
        return

    checked = df[df["attendance_status"].fillna("").str.lower().eq("check in")].copy()
    q = st.text_input(
        "Search checked-in attendees",
        placeholder="Type name, email, phone, organization, registration ID...",
        key=f"checked_attendee_search_{event_id}",
    )
    checked = filter_df(checked, q)

    st.metric("Checked-in attendees", len(checked))
    if checked.empty:
        st.info("No checked-in attendee matches your search yet.")
        return

    display = checked[[
        "name", "email", "phone", "organization", "role", "registered_by_name",
        "channel", "source", "attendance_status", "checkin_datetime", "registration_id"
    ]].copy()
    display.columns = [
        "Name", "Email", "Phone", "Organization", "Role", "Registered by",
        "Channel", "Source", "Status", "Check-in time", "Registration ID"
    ]
    st.dataframe(display, use_container_width=True, hide_index=True)

def import_connect(event_id):
    st.subheader("Connect Import")
    st.caption("Upload CSV/XLSX exported from Connect. Required columns: email and participant_name/name.")
    uploaded = st.file_uploader("Upload Connect export", type=["csv", "xlsx"])
    if uploaded is None:
        return
    try:
        if uploaded.name.endswith(".csv"):
            df = pd.read_csv(uploaded)
        else:
            df = pd.read_excel(uploaded)
    except Exception as exc:
        st.error(f"Could not read file: {exc}")
        return
    st.dataframe(df.head(30), use_container_width=True)
    cols = list(df.columns)
    email_col = st.selectbox("Email column", cols, index=cols.index("email") if "email" in cols else 0)
    name_options = [c for c in cols if c.lower() in ["participant_name", "name", "full_name"]]
    name_col = st.selectbox("Name column", cols, index=cols.index(name_options[0]) if name_options else 0)
    source_col = st.selectbox("Source column optional", ["None"] + cols)
    if st.button("Import registrations as channel = connect", use_container_width=True):
        created = 0
        skipped = 0
        for _, r in df.iterrows():
            email = str(r.get(email_col, "")).strip().lower()
            name = str(r.get(name_col, "")).strip()
            if not email or email == "nan" or not name or name == "nan":
                skipped += 1
                continue
            source = None if source_col == "None" else str(r.get(source_col, "") or "").strip()
            pid, _ = upsert_participant({
                "email": email, "participant_name": name, "phone_number": "",
                "place_of_residence": "", "dob": None, "in_groupchat": None,
                "have_connect": 1, "marketing_subs": None, "organization": "",
            })
            reg_id = create_registration(event_id, pid, "connect", source, "Imported from Connect", False)
            if reg_id is None:
                skipped += 1
            else:
                created += 1
        st.success(f"Imported {created} registrations. Skipped {skipped} rows/duplicates.")


def event_dashboard(event_id):
    st.subheader("Dashboard")
    df, total, attended, not_checked, rate, no_show = event_metrics(event_id)
    m1, m2, m3, m4 = st.columns(4)
    for col, icon, label, value in [
        (m1, "👥", "Registered", total),
        (m2, "✅", "Checked in", attended),
        (m3, "🕒", "Pending", not_checked),
        (m4, "📈", "Attendance rate", f"{rate:.0%}"),
    ]:
        col.markdown(f'<div class="kpi-card"><div class="kpi-label">{icon} {label}</div><div class="kpi-value">{value}</div></div>', unsafe_allow_html=True)
    if no_show:
        st.info(f"No-shows marked: {no_show}")
    if df.empty:
        return

    st.markdown("#### Close Event")
    pending_no_show = int(((df["attendance_status"].fillna("not check in") == "not check in") & (df.get("registration_status", "registered") != "cancelled")).sum()) if "registration_status" in df.columns else not_checked
    if pending_no_show > 0:
        st.warning(f"There are {pending_no_show} attendee(s) still marked as not check in.")
        confirm_close = st.checkbox(
            "I confirm the event is finished and remaining not-check-in attendees should be marked as no show",
            key=f"confirm_close_event_{event_id}",
        )
        if st.button("Close Event: Mark Remaining as No Show", disabled=not confirm_close, use_container_width=True, key=f"close_event_{event_id}"):
            changed = repo.close_event_mark_no_shows(event_id, current_operator())
            st.session_state[f"closed_event_msg_{event_id}"] = f"Marked {changed} attendee(s) as no show."
            st.rerun()
    else:
        st.success("No pending not-check-in attendees for this event.")
    if st.session_state.get(f"closed_event_msg_{event_id}"):
        st.success(st.session_state.pop(f"closed_event_msg_{event_id}"))

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Registrations by channel")
        st.bar_chart(df["channel"].fillna("Unknown").value_counts())
    with c2:
        st.markdown("#### Registrations by registration type")
        reg_types = read_df(
            """
            SELECT CASE WHEN number_of_attendee = 1 THEN 'Solo' ELSE 'Group' END AS registration_type,
                   COUNT(*) AS registrations
            FROM event_registration
            WHERE event_id = ?
              AND COALESCE(status, 'registered') != 'cancelled'
            GROUP BY registration_type
            ORDER BY registration_type
            """,
            (event_id,),
        )
        if reg_types.empty:
            st.caption("No registration type data yet.")
        else:
            st.bar_chart(reg_types.set_index("registration_type")["registrations"])
    st.markdown("#### Full attendee data")
    st.dataframe(df, use_container_width=True, hide_index=True)


def event_workspace_page(selected_event_id=None):
    header()
    events = get_events()
    if events.empty:
        st.info("Create an event first.")
        return
    st.subheader("Event Workspace")

    if selected_event_id is None:
        event_labels = events.apply(lambda r: f"#{r['event_id']} — {r['event_name']} ({r['start_datetime']})", axis=1).tolist()
        selected_label = st.selectbox("Choose event", event_labels)
        event_id = int(selected_label.split(" — ")[0].replace("#", ""))
    else:
        event_id = int(selected_event_id)

    ev = events[events["event_id"] == event_id]
    if ev.empty:
        st.warning("Selected event could not be found. Please choose another event from the sidebar.")
        return
    ev = ev.iloc[0]

    st.markdown(f"## {ev['event_name']}")
    d1, d2, d3, d4 = st.columns(4)
    d1.info(f"📍 **Location**\n\n{ev['location_name']}")
    d2.info(f"🕒 **Start**\n\n{ev['start_datetime']}")
    d3.info(f"🏷️ **Type**\n\n{ev['etype_name']}")
    d4.info(f"💶 **Price**\n\n{ev['price_per_ticket'] if pd.notna(ev['price_per_ticket']) else 0}")
    if ev.get("event_description"):
        st.caption(ev["event_description"])

    sub_register, sub_checkin, sub_attendees, sub_dashboard = st.tabs([
        "Registration", "Check-In", "Attendee List", "Dashboard"
    ])
    with sub_register:
        registration_form(event_id, walk_in=False)
    with sub_checkin:
        checkin_page(event_id)
    with sub_attendees:
        checked_in_attendee_list(event_id)
    with sub_dashboard:
        event_dashboard(event_id)



# ---------------------------------------------------------------------------
# Admin / Database Manager pages (V10)
# ---------------------------------------------------------------------------
def _bool_editor(label, value, key):
    options = BOOL_OPTIONS
    return bool_to_db(st.selectbox(label, options, index=options.index(db_to_bool_label(value)), key=key))


def _safe_df(rows):
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def manage_events_tab(operator):
    st.markdown("### Manage Events")
    rows = repo.get_events()
    df = _safe_df(rows)
    if df.empty:
        st.info("No active events.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    labels = [f"#{r['event_id']} — {r['event_name']}" for r in rows]
    selected = st.selectbox("Select event", labels, key="manage_event_select")
    event_id = int(selected.split(" — ")[0].replace("#", ""))
    rec = next(r for r in rows if int(r["event_id"]) == event_id)
    with st.container():
        name = st.text_input("Event name", value=rec.get("event_name") or "")
        start = st.text_input("Start datetime", value=rec.get("start_datetime") or "")
        end = st.text_input("End datetime", value=rec.get("end_datetime") or "")
        age = st.text_input("Age rating", value=rec.get("age_rating") or "")
        price = st.number_input("Price per ticket", min_value=0.0, value=float(rec.get("price_per_ticket") or 0), step=1.0)
        desc = st.text_area("Description", value=rec.get("event_description") or "")
        c1, c2 = st.columns(2)
        save = c1.button("Save Event Changes", use_container_width=True)
        delete = c2.button("Archive Event", use_container_width=True)
    if save:
        repo.update_event(event_id, {"event_name": name, "start_datetime": start, "end_datetime": end, "age_rating": age, "price_per_ticket": price, "event_description": desc}, operator)
        st.success("Event updated.")
        st.rerun()
    if delete:
        repo.soft_delete_event(event_id, operator)
        st.warning("Event archived. It is hidden but can be restored via Undo Last Action.")
        st.rerun()


def manage_locations_tab(operator):
    st.markdown("### Manage Locations")
    rows = repo.get_locations()
    df = _safe_df(rows)
    if df.empty:
        st.info("No active locations.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    labels = [f"{r['location_id']} — {r['location_name']}" for r in rows]
    selected = st.selectbox("Select location", labels, key="manage_location_select")
    loc_id = selected.split(" — ")[0]
    rec = next(r for r in rows if r["location_id"] == loc_id)
    with st.container():
        name = st.text_input("Location name", value=rec.get("location_name") or "")
        street = st.text_input("Street/number", value=rec.get("street_number") or "")
        postal = st.text_input("Postal code", value=rec.get("postal_code") or "")
        city = st.text_input("City", value=rec.get("city") or "")
        country = st.text_input("Country", value=rec.get("country") or "")
        capacity = st.text_area("Capacity info", value=rec.get("capacity_info") or "")
        access = st.text_area("Accessibility info", value=rec.get("accessibility_info") or "")
        desc = st.text_area("Description", value=rec.get("description") or "")
        c1, c2 = st.columns(2)
        save = c1.button("Save Location Changes", use_container_width=True)
        delete = c2.button("Archive Location", use_container_width=True)
    if save:
        repo.update_location(loc_id, {"location_name": name, "street_number": street, "postal_code": postal, "city": city, "country": country, "capacity_info": capacity, "accessibility_info": access, "description": desc}, operator)
        st.success("Location updated.")
        st.rerun()
    if delete:
        repo.soft_delete_location(loc_id, operator)
        st.warning("Location archived.")
        st.rerun()


def manage_event_types_tab(operator):
    st.markdown("### Manage Event Types")
    rows = repo.get_event_types()
    df = _safe_df(rows)
    if df.empty:
        st.info("No active event types.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    labels = [f"{r['etype_id']} — {r['etype_name']}" for r in rows]
    selected = st.selectbox("Select event type", labels, key="manage_type_select")
    etype_id = selected.split(" — ")[0]
    rec = next(r for r in rows if r["etype_id"] == etype_id)
    with st.container():
        name = st.text_input("Event type name", value=rec.get("etype_name") or "")
        desc = st.text_area("Description", value=rec.get("description") or "")
        c1, c2 = st.columns(2)
        save = c1.button("Save Event Type Changes", use_container_width=True)
        delete = c2.button("Archive Event Type", use_container_width=True)
    if save:
        repo.update_event_type(etype_id, {"etype_name": name, "description": desc}, operator)
        st.success("Event type updated.")
        st.rerun()
    if delete:
        repo.soft_delete_event_type(etype_id, operator)
        st.warning("Event type archived.")
        st.rerun()


def manage_participants_tab(operator):
    st.markdown("### Manage Participants")
    rows = repo.get_participants()
    df = _safe_df(rows)
    q = st.text_input("Search participants", key="manage_participants_search")
    if not df.empty and q:
        mask = pd.Series(False, index=df.index)
        for col in ["participant_name", "email", "phone_number", "organization", "place_of_residence"]:
            if col in df:
                mask = mask | df[col].fillna("").astype(str).str.lower().str.contains(q.lower(), regex=False)
        df = df[mask]
    st.dataframe(df, use_container_width=True, hide_index=True)
    if df.empty:
        st.info("No matching participants.")
        return
    labels = [f"{r['participant_id']} — {r['participant_name']} — {r.get('email') or 'no email'}" for _, r in df.iterrows()]
    selected = st.selectbox("Select participant", labels, key="manage_participant_select")
    pid = selected.split(" — ")[0]
    rec = next(r for r in rows if r["participant_id"] == pid)
    with st.container():
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Name", value=rec.get("participant_name") or "")
            email = st.text_input("Email", value=rec.get("email") or "")
            phone = st.text_input("Phone", value=rec.get("phone_number") or "")
            dob_value = st.date_input("Date of birth", value=dob_to_date(rec.get("dob")), min_value=DOB_MIN, max_value=DOB_MAX, format="YYYY-MM-DD")
        with c2:
            residence = st.text_input("Residence", value=rec.get("place_of_residence") or "")
            organization = st.text_input("Organization", value=rec.get("organization") or "")
            in_gc = _bool_editor("In groupchat?", rec.get("in_groupchat"), "manage_p_gc")
            have_conn = _bool_editor("Have Connect?", rec.get("have_connect"), "manage_p_connect")
            marketing = _bool_editor("Marketing subscription?", rec.get("marketing_subs"), "manage_p_marketing")
        c1, c2 = st.columns(2)
        save = c1.button("Save Participant Changes", use_container_width=True)
        delete = c2.button("Archive Participant", use_container_width=True)
    if save:
        repo.update_participant(pid, {"participant_name": name, "email": email, "phone_number": phone, "place_of_residence": residence, "dob": dob_value, "in_groupchat": in_gc, "have_connect": have_conn, "marketing_subs": marketing, "organization": organization}, operator)
        st.success("Participant updated.")
        st.rerun()
    if delete:
        repo.soft_delete_participant(pid, operator)
        st.warning("Participant archived.")
        st.rerun()

    with st.expander("Event history for this participant"):
        hist = read_df("""
            SELECT e.event_name, er.registration_id, er.channel, er.source, era.role, era.attendance_status, era.checkin_datetime
            FROM event_registered_attendee era
            JOIN event_registration er ON era.registration_id = er.registration_id
            JOIN events e ON er.event_id = e.event_id
            WHERE era.participant_id = ?
            ORDER BY datetime(er.datetime_registered) DESC
        """, (pid,))
        st.dataframe(hist, use_container_width=True, hide_index=True)



def get_all_attendees_admin():
    """System-wide view of event_registered_attendee joined with registrations, events, and participants."""
    return read_df(
        """
        SELECT
            era.registration_id,
            era.participant_id,
            p.participant_name,
            p.email,
            e.event_name,
            er.channel,
            er.source,
            era.role,
            era.need_buddy,
            era.attendance_status,
            era.checkin_datetime,
            era.payment_status,
            era.payment_method
        FROM event_registered_attendee era
        LEFT JOIN participants p ON era.participant_id = p.participant_id
        LEFT JOIN event_registration er ON era.registration_id = er.registration_id
        LEFT JOIN events e ON er.event_id = e.event_id
        ORDER BY era.registration_id DESC, lower(COALESCE(p.participant_name, ''))
        """
    )


def manage_attendees_tab(operator):
    st.markdown("### Manage Attendees")
    st.caption("Directly manage rows from `event_registered_attendee` across all events.")
    df = get_all_attendees_admin()
    q = st.text_input("Search attendees", key="manage_all_attendees_search")
    if not df.empty and q:
        mask = pd.Series(False, index=df.index)
        for col in ["participant_name", "email", "event_name", "channel", "source", "role", "attendance_status"]:
            if col in df:
                mask = mask | df[col].fillna("").astype(str).str.lower().str.contains(q.lower(), regex=False)
        df = df[mask]
    st.dataframe(df, use_container_width=True, hide_index=True)
    if df.empty:
        st.info("No matching attendee rows.")
        return

    labels = [
        f"Reg #{int(r['registration_id'])} / {r['participant_id']} — {r.get('participant_name') or '-'} — {r.get('event_name') or '-'}"
        for _, r in df.iterrows()
    ]
    selected = st.selectbox("Select attendee row", labels, key="manage_all_attendee_select")
    left = selected.split(" — ")[0]
    reg_id = int(left.split("/")[0].replace("Reg #", "").strip())
    pid = left.split("/")[1].strip()
    rec = df[(df["registration_id"].astype(int) == reg_id) & (df["participant_id"].astype(str) == pid)].iloc[0].to_dict()

    with st.container():
        c1, c2 = st.columns(2)
        with c1:
            role = st.selectbox("Role", repo.ROLES, index=repo.ROLES.index(rec.get("role")) if rec.get("role") in repo.ROLES else 0)
            need_buddy = _bool_editor("Need buddy?", rec.get("need_buddy"), "manage_all_att_buddy")
            attendance = st.selectbox("Attendance status", repo.ATTENDANCE, index=repo.ATTENDANCE.index(rec.get("attendance_status")) if rec.get("attendance_status") in repo.ATTENDANCE else 0)
        with c2:
            checkin = st.text_input("Check-in datetime", value=rec.get("checkin_datetime") or "")
            payment_status = st.selectbox("Payment status", [None] + repo.PAYMENT_STATUS, format_func=lambda x: "Not filled" if x is None else x, index=([None] + repo.PAYMENT_STATUS).index(rec.get("payment_status")) if rec.get("payment_status") in repo.PAYMENT_STATUS else 0)
            payment_method = st.selectbox("Payment method", [None] + repo.PAYMENT_METHOD, format_func=lambda x: "Not filled" if x is None else x, index=([None] + repo.PAYMENT_METHOD).index(rec.get("payment_method")) if rec.get("payment_method") in repo.PAYMENT_METHOD else 0)
        c1, c2 = st.columns(2)
        save = c1.button("Save Attendee Changes", use_container_width=True)
        delete = c2.button("Hard Delete Attendee Row", use_container_width=True)
    if save:
        repo.update_attendee(reg_id, pid, {"role": role, "need_buddy": need_buddy, "attendance_status": attendance, "checkin_datetime": checkin, "payment_status": payment_status, "payment_method": payment_method}, operator)
        st.success("Attendee row updated.")
        st.rerun()
    if delete:
        repo.delete_attendee(reg_id, pid, operator)
        st.warning("Attendee row deleted.")
        st.rerun()


def manage_registrations_tab(operator):
    st.markdown("### Manage Registrations")
    rows = repo.get_registrations()
    df = _safe_df(rows)
    if df.empty:
        st.info("No registrations.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    labels = [f"#{r['registration_id']} — {r.get('event_name') or '-'} — {r.get('registered_by_name') or '-'}" for r in rows]
    selected = st.selectbox("Select registration", labels, key="manage_reg_select")
    reg_id = int(selected.split(" — ")[0].replace("#", ""))
    rec = next(r for r in rows if int(r["registration_id"]) == reg_id)
    with st.container():
        channel = st.selectbox("Channel", repo.CHANNELS, index=repo.CHANNELS.index(rec.get("channel")) if rec.get("channel") in repo.CHANNELS else 0)
        source = st.text_input("Source", value=rec.get("source") or "")
        status = st.selectbox("Status", repo.REG_STATUS, index=repo.REG_STATUS.index(rec.get("status")) if rec.get("status") in repo.REG_STATUS else 0)
        notes = st.text_area("Notes", value=rec.get("notes") or "")
        c1, c2, c3 = st.columns(3)
        save = c1.button("Save Registration Changes", use_container_width=True)
        cancel = c2.button("Cancel Registration", use_container_width=True)
        delete = c3.button("Hard Delete Registration", use_container_width=True)
    if save:
        repo.update_registration(reg_id, {"channel": channel, "source": source, "status": status, "notes": notes}, operator)
        st.success("Registration updated.")
        st.rerun()
    if cancel:
        repo.cancel_registration(reg_id, operator)
        st.warning("Registration was marked as cancelled. Attendee attendance statuses were left unchanged; active views exclude cancelled registrations.")
        st.rerun()
    if delete:
        repo.delete_registration(reg_id, operator)
        st.warning("Registration and its attendee rows were deleted. Audit payload was kept.")
        st.rerun()

    st.markdown("#### Attendees in this registration")
    att = repo.get_attendees(reg_id)
    adf = _safe_df(att)
    st.dataframe(adf, use_container_width=True, hide_index=True)
    if not adf.empty:
        att_labels = [f"{r['participant_id']} — {r.get('participant_name') or '-'}" for r in att]
        selected_att = st.selectbox("Select attendee row", att_labels, key="manage_att_select")
        pid = selected_att.split(" — ")[0]
        arec = next(r for r in att if r["participant_id"] == pid)
        with st.container():
            role = st.selectbox("Role", repo.ROLES, index=repo.ROLES.index(arec.get("role")) if arec.get("role") in repo.ROLES else 0)
            need_buddy = _bool_editor("Need buddy?", arec.get("need_buddy"), "manage_att_buddy")
            attendance = st.selectbox("Attendance status", repo.ATTENDANCE, index=repo.ATTENDANCE.index(arec.get("attendance_status")) if arec.get("attendance_status") in repo.ATTENDANCE else 0)
            checkin = st.text_input("Check-in datetime", value=arec.get("checkin_datetime") or "")
            payment_status = st.selectbox("Payment status", [None] + repo.PAYMENT_STATUS, format_func=lambda x: "Not filled" if x is None else x, index=([None] + repo.PAYMENT_STATUS).index(arec.get("payment_status")) if arec.get("payment_status") in repo.PAYMENT_STATUS else 0)
            payment_method = st.selectbox("Payment method", [None] + repo.PAYMENT_METHOD, format_func=lambda x: "Not filled" if x is None else x, index=([None] + repo.PAYMENT_METHOD).index(arec.get("payment_method")) if arec.get("payment_method") in repo.PAYMENT_METHOD else 0)
            c1, c2 = st.columns(2)
            save_att = c1.button("Save Attendee Row", use_container_width=True)
            del_att = c2.button("Hard Delete Attendee Row", use_container_width=True)
        if save_att:
            repo.update_attendee(reg_id, pid, {"role": role, "need_buddy": need_buddy, "attendance_status": attendance, "checkin_datetime": checkin, "payment_status": payment_status, "payment_method": payment_method}, operator)
            st.success("Attendee row updated.")
            st.rerun()
        if del_att:
            repo.delete_attendee(reg_id, pid, operator)
            st.warning("Attendee row deleted.")
            st.rerun()


def archived_records_tab(operator):
    st.markdown("### Archived Records")
    st.caption("Archived records are soft-deleted rows. You can restore them or hard delete them permanently. Hard delete may fail if other tables still reference the record.")

    table = st.selectbox("Archived table", ["Events", "Participants", "Locations", "Event Types"], key="archived_table_select")

    if table == "Events":
        rows = repo.get_archived_events()
        pk = "event_id"
        label_fn = lambda r: f"#{r['event_id']} — {r.get('event_name') or '-'}"
        restore_fn = repo.restore_event
        hard_delete_fn = repo.hard_delete_event
    elif table == "Participants":
        rows = repo.get_archived_participants()
        pk = "participant_id"
        label_fn = lambda r: f"{r['participant_id']} — {r.get('participant_name') or '-'} — {r.get('email') or 'no email'}"
        restore_fn = repo.restore_participant
        hard_delete_fn = repo.hard_delete_participant
    elif table == "Locations":
        rows = repo.get_archived_locations()
        pk = "location_id"
        label_fn = lambda r: f"{r['location_id']} — {r.get('location_name') or '-'}"
        restore_fn = repo.restore_location
        hard_delete_fn = repo.hard_delete_location
    else:
        rows = repo.get_archived_event_types()
        pk = "etype_id"
        label_fn = lambda r: f"{r['etype_id']} — {r.get('etype_name') or '-'}"
        restore_fn = repo.restore_event_type
        hard_delete_fn = repo.hard_delete_event_type

    df = _safe_df(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    if df.empty:
        st.info(f"No archived {table.lower()}.")
        return

    labels = [label_fn(r) for r in rows]
    selected = st.selectbox("Select archived record", labels, key=f"archived_{table}_select")
    selected_index = labels.index(selected)
    record = rows[selected_index]
    record_id = record[pk]

    with st.container(border=True):
        st.json(record, expanded=False)
        c1, c2 = st.columns(2)
        if c1.button("Restore", use_container_width=True, key=f"restore_{table}_{record_id}"):
            restore_fn(record_id, operator)
            st.success("Record restored.")
            st.rerun()

        confirm = c2.checkbox("Confirm permanent hard delete", key=f"confirm_hard_delete_{table}_{record_id}")
        if c2.button("Hard Delete Permanently", use_container_width=True, disabled=not confirm, key=f"hard_delete_{table}_{record_id}"):
            try:
                hard_delete_fn(record_id, operator)
                st.warning("Record permanently deleted.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not hard delete this record. It is probably still referenced by another table. Details: {exc}")


def audit_tab(operator):
    st.markdown("### Audit Log & Undo")
    c1, c2 = st.columns([1, 2])
    if c1.button("↩ Undo Last Action", use_container_width=True):
        msg = repo.undo_last_action(operator)
        st.info(msg)
        st.rerun()
    c2.caption("Undo supports updates and soft deletes. Create, restore, hard delete, cancellation, and other writes are recorded in the audit log.")
    st.dataframe(pd.DataFrame(repo.get_audit(200)), use_container_width=True, hide_index=True)


def manage_data_page():
    header()
    title_col, audit_col, undo_col = st.columns([4, 1.4, 1.4])
    title_col.subheader("Admin / Database Manager")
    title_col.caption("Edit/archive records from every database table, delete transactional rows, inspect audit history, and undo supported actions.")

    operator = st.text_input("Operator name", value=st.session_state.get("operator_name", "SSC Admin"))
    st.session_state["operator_name"] = operator

    if "admin_section" not in st.session_state:
        st.session_state["admin_section"] = "Events"

    if audit_col.button("Audit Log", use_container_width=True):
        st.session_state["admin_section"] = "Audit / Undo"
        st.rerun()
    if undo_col.button("↩ Undo", use_container_width=True):
        msg = repo.undo_last_action(operator)
        st.info(msg)
        st.rerun()

    sections = ["Events", "Participants", "Registrations", "Attendees", "Locations", "Event Types", "Archived Records", "Audit / Undo"]
    current = st.radio(
        "Database table",
        sections,
        horizontal=True,
        index=sections.index(st.session_state.get("admin_section", "Events")) if st.session_state.get("admin_section", "Events") in sections else 0,
    )
    st.session_state["admin_section"] = current

    if current == "Events":
        manage_events_tab(operator)
    elif current == "Participants":
        manage_participants_tab(operator)
    elif current == "Registrations":
        manage_registrations_tab(operator)
    elif current == "Attendees":
        manage_attendees_tab(operator)
    elif current == "Locations":
        manage_locations_tab(operator)
    elif current == "Event Types":
        manage_event_types_tab(operator)
    elif current == "Archived Records":
        archived_records_tab(operator)
    else:
        audit_tab(operator)

with st.sidebar:
    st.markdown('<div class="sidebar-brand">SSC Event Management</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-caption">SQLite event operations dashboard</div>', unsafe_allow_html=True)
    st.divider()

    events_for_sidebar = get_events()
    selected_event_id = None
    if not events_for_sidebar.empty:
        event_labels = events_for_sidebar.apply(
            lambda r: f"#{r['event_id']} — {r['event_name']}", axis=1
        ).tolist()
        default_event_id = st.session_state.get("selected_event_id_override")
        default_index = 0
        if default_event_id is not None:
            for i, label in enumerate(event_labels):
                if label.startswith(f"#{default_event_id} —"):
                    default_index = i
                    break
        selected_event_label = st.selectbox("Current Event", event_labels, index=default_index, key="sidebar_current_event")
        selected_event_id = int(selected_event_label.split(" — ")[0].replace("#", ""))
        st.session_state["selected_event_id_override"] = selected_event_id
    else:
        st.caption("No events yet")

    st.divider()
    page = st.radio(
        "Navigation",
        ["Home", "Create Event", "Event Workspace", "Admin / Database Manager"],
        index=["Home", "Create Event", "Event Workspace", "Admin / Database Manager"].index(st.session_state.get("main_nav", "Home")),
        key="main_nav",
    )
    st.divider()
    st.caption(f"🟢 Connected to {DB_PATH.name}")

if page == "Home":
    home_page()
elif page == "Create Event":
    create_event_page()
elif page == "Event Workspace":
    event_workspace_page(selected_event_id)
elif page == "Admin / Database Manager":
    manage_data_page()
