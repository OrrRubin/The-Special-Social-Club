import sqlite3
from datetime import datetime, date, time
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).parent / "ssc_database.db"
CHANNELS = ["whatsapp", "connect", "walk-in"]
BOOL_OPTIONS = ["Unknown / not filled", "Yes", "No"]

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
        ORDER BY datetime(e.start_datetime) DESC
        """
    )


def get_locations():
    return read_df("SELECT * FROM locations ORDER BY location_name")


def get_event_types():
    return read_df("SELECT * FROM event_types ORDER BY etype_name")


def next_code(table, id_col, prefix, width):
    with conn() as c:
        rows = c.execute(f"SELECT {id_col} FROM {table}").fetchall()
    max_num = 0
    for r in rows:
        val = str(r[0] or "")
        digits = "".join(ch for ch in val if ch.isdigit())
        if digits:
            max_num = max(max_num, int(digits))
    return f"{prefix}{max_num + 1:0{width}d}"


def next_participant_id():
    return next_code("participants", "participant_id", "P", 4)


def next_location_id():
    return next_code("locations", "location_id", "LOC", 3)


def next_etype_id():
    return next_code("event_types", "etype_id", "ET", 3)


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
    execute(
        """
        INSERT INTO participants
        (participant_id, participant_name, email, phone_number, place_of_residence, dob,
         in_groupchat, have_connect, marketing_subs, organization)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            pid, data["participant_name"], data["email"].strip().lower(),
            data.get("phone_number") or None, data.get("place_of_residence") or None,
            dob_value, data.get("in_groupchat"), data.get("have_connect"),
            data.get("marketing_subs"), data.get("organization") or None,
        ),
    )
    return pid, "created"




def create_participant_without_email(data):
    """Create a participant record for an attending guest without email.

    Guests only need name and optional email in the group registration UI.
    If email is missing, email stays NULL so multiple guests without email are allowed.
    """
    pid = next_participant_id()
    execute(
        """
        INSERT INTO participants
        (participant_id, participant_name, email, phone_number, place_of_residence, dob,
         in_groupchat, have_connect, marketing_subs, organization)
        VALUES (?, ?, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)
        """,
        (pid, data.get("participant_name") or "Guest"),
    )
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


def participant_already_registered(event_id, participant_id):
    with conn() as c:
        return c.execute(
            """
            SELECT 1
            FROM event_registration er
            JOIN event_registered_attendee era ON er.registration_id = era.registration_id
            WHERE er.event_id = ? AND era.participant_id = ?
            LIMIT 1
            """,
            (event_id, participant_id),
        ).fetchone() is not None


def create_registration(event_id, participant_id, channel, source, notes, immediate_checkin=False):
    if participant_already_registered(event_id, participant_id):
        return None
    registration_id = execute(
        """
        INSERT INTO event_registration
        (registered_by, event_id, datetime_registered, number_of_attendee, channel, source, status, notes)
        VALUES (?, ?, CURRENT_TIMESTAMP, 1, ?, ?, 'registered', ?)
        """,
        (participant_id, event_id, channel, source or None, notes or None),
    )
    attendance_status = "attended" if immediate_checkin else "not checked in"
    checkin_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if immediate_checkin else None
    execute(
        """
        INSERT INTO event_registered_attendee
        (registration_id, participant_id, role, need_buddy, attendance_status, checkin_datetime, payment_status, payment_method)
        VALUES (?, ?, 'main attendee', 0, ?, ?, NULL, NULL)
        """,
        (registration_id, participant_id, attendance_status, checkin_dt),
    )
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

    registration_id = execute(
        """
        INSERT INTO event_registration
        (registered_by, event_id, datetime_registered, number_of_attendee, channel, source, status, notes)
        VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, ?, 'registered', ?)
        """,
        (main_participant_id, event_id, len(valid_attendees), channel, source or None, notes or None),
    )
    attendance_status = "attended" if immediate_checkin else "not checked in"
    checkin_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if immediate_checkin else None
    for attendee in valid_attendees:
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
    return registration_id, skipped

def attendee_df(event_id):
    return read_df(
        """
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
        ORDER BY
            CASE WHEN era.attendance_status = 'attended' THEN 1 ELSE 0 END,
            lower(p.participant_name)
        """,
        (event_id,),
    )


def filter_df(df, query):
    if not query or df.empty:
        return df
    q = query.lower().strip()
    text_cols = ["name", "email", "phone", "organization", "channel", "source", "attendance_status", "residence"]
    mask = pd.Series(False, index=df.index)
    for col in text_cols:
        if col in df.columns:
            mask = mask | df[col].fillna("").astype(str).str.lower().str.contains(q, regex=False)
    return df[mask]


def check_in(registration_id, participant_id):
    execute(
        """
        UPDATE event_registered_attendee
        SET attendance_status = 'attended',
            checkin_datetime = CURRENT_TIMESTAMP
        WHERE registration_id = ? AND participant_id = ?
        """,
        (registration_id, participant_id),
    )


def event_metrics(event_id):
    df = attendee_df(event_id)
    total = len(df)
    attended = int((df["attendance_status"] == "attended").sum()) if not df.empty else 0
    not_checked = total - attended
    rate = attended / total if total else 0
    return df, total, attended, not_checked, rate


def event_stats_df():
    return read_df(
        """
        SELECT
            e.event_id,
            COUNT(DISTINCT er.registration_id) AS registered_count,
            SUM(CASE WHEN era.attendance_status = 'attended' THEN 1 ELSE 0 END) AS attended_count
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


def event_card(row, kind="upcoming"):
    registered = int(row.get("registered_count", 0) or 0)
    attended = int(row.get("attended_count", 0) or 0)
    image_label = "Upcoming" if kind == "upcoming" else "Past Event"
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
    total_participants = read_df("SELECT COUNT(*) AS n FROM participants").iloc[0]["n"]
    total_regs = read_df("SELECT COUNT(*) AS n FROM event_registration").iloc[0]["n"]
    total_attended = read_df("SELECT COUNT(*) AS n FROM event_registered_attendee WHERE attendance_status='attended'").iloc[0]["n"]
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
    st.subheader("Create Event")

    with st.expander("➕ Add new location", expanded=False):
        with st.form("new_location_form"):
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
            if st.form_submit_button("Add Location", use_container_width=True):
                if not loc_name or not street:
                    st.error("Location name and street number are required.")
                else:
                    loc_id = next_location_id()
                    execute(
                        """
                        INSERT INTO locations
                        (location_id, location_name, street_number, postal_code, city, country, capacity_info, accessibility_info, description)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (loc_id, loc_name, street, postal or None, city or None, country or None,
                         capacity or None, access or None, desc or None),
                    )
                    st.success(f"Added location {loc_id}: {loc_name}")
                    st.rerun()

    with st.expander("➕ Add new event type", expanded=False):
        with st.form("new_event_type_form"):
            type_name = st.text_input("Event type name *")
            type_desc = st.text_area("Event type description")
            if st.form_submit_button("Add Event Type", use_container_width=True):
                if not type_name:
                    st.error("Event type name is required.")
                else:
                    etype_id = next_etype_id()
                    execute(
                        "INSERT INTO event_types (etype_id, etype_name, description) VALUES (?, ?, ?)",
                        (etype_id, type_name, type_desc or None),
                    )
                    st.success(f"Added event type {etype_id}: {type_name}")
                    st.rerun()

    locations = get_locations()
    types = get_event_types()
    if locations.empty or types.empty:
        st.error("Create at least one location and one event type first.")
        return

    st.markdown("### Event Details")
    with st.form("create_event"):
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
        submit = st.form_submit_button("Create Event", use_container_width=True)
    if submit:
        if not event_name:
            st.error("Event name is required.")
            return
        location_id = loc_label.split(" — ")[0]
        etype_id = type_label.split(" — ")[0]
        start_dt = datetime.combine(start_date, start_time).strftime("%Y-%m-%d %H:%M:%S")
        end_dt = datetime.combine(end_date, end_time).strftime("%Y-%m-%d %H:%M:%S")
        event_id = execute(
            """
            INSERT INTO events
            (location_id, event_type_id, event_name, start_datetime, end_datetime, age_rating, price_per_ticket, event_description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (location_id, etype_id, event_name, start_dt, end_dt, age_rating or None, price, desc or None),
        )
        st.success(f"Created event #{event_id}: {event_name}")

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
    """Reusable participant input block."""
    c1, c2 = st.columns(2)
    with c1:
        email_label = "Email *" if require_email else "Email optional"
        email = st.text_input(email_label, key=f"{prefix}_email").strip().lower()
        name_label = "Participant name *" if require_name else "Participant name"
        name = st.text_input(name_label, key=f"{prefix}_name")
        phone = st.text_input("Phone number", key=f"{prefix}_phone")
        dob_value = None if compact else st.date_input("Date of birth", value=None, format="YYYY-MM-DD", key=f"{prefix}_dob")
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


def guest_inputs(prefix):
    """Guest fields for group registration.

    Guests are still stored in participants if they attend, but the form only asks
    for name, optional email, and whether they need a buddy.
    """
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


def registration_form(event_id):
    st.subheader("Make Registration")
    st.caption("Use this for solo registration, group registration, and walk-ins. Registrant email is required. For groups, there is always one main attendee with compulsory email; guests only need name and optional email/buddy preference.")

    registration_type = st.radio("Registration type", ["Solo", "Group"], horizontal=True)

    with st.form("registration_form", clear_on_submit=False):
        st.markdown("#### Main registrant")
        st.caption("The main registrant is the person responsible for the registration. Email is compulsory.")
        main_data = participant_inputs("main", require_email=True, require_name=True, compact=False)

        main_attends = True
        main_attendee_data = None
        guest_data = []
        if registration_type == "Group":
            st.divider()
            main_attends = st.checkbox("Registrant will also attend", value=True)

            if main_attends:
                st.info("Registrant will be recorded as the main attendee for this group.")
            else:
                st.markdown("#### Main attendee")
                st.caption("Because the registrant is not attending, choose one attending person as the main attendee. Main attendee email is compulsory.")
                main_attendee_data = participant_inputs("main_attendee", require_email=True, require_name=True, compact=True)

            guest_count = st.number_input("Number of guests", min_value=0, max_value=10, value=1, step=1)
            st.markdown("#### Guest information")
            st.caption("Guests only need name and optional email. Buddy preference is optional. Every attending guest will be added to participants and event_registered_attendee.")
            for i in range(int(guest_count)):
                with st.expander(f"Guest {i + 1}", expanded=True):
                    guest_data.append(guest_inputs(f"guest_{i}"))

        st.divider()
        st.markdown("#### Registration details")
        r1, r2, r3 = st.columns([1, 1, 1])
        with r1:
            channel = st.selectbox("Registration channel *", CHANNELS)
        with r2:
            source = st.text_input("Source: how did they hear about SSC/event?")
        with r3:
            immediate_checkin = st.checkbox("Immediate check-in", value=False, help="Use this for walk-ins or if the group is already at the event.")
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Create / Update Registration", use_container_width=True)

    if submitted:
        try:
            main_pid, main_action = get_or_create_participant_from_form(main_data, email_required=True)
        except ValueError as exc:
            st.error(str(exc))
            return

        if registration_type == "Solo":
            reg_id = create_registration(event_id, main_pid, channel, source, notes, immediate_checkin)
            if reg_id is None:
                st.warning("This participant is already registered for this event. Participant information was updated.")
            else:
                st.success(f"Participant {main_action}. Solo registration #{reg_id} created." + (" Checked in immediately." if immediate_checkin else ""))
            return

        attendees = []
        if main_attends:
            attendees.append({
                "participant_id": main_pid,
                "role": "main attendee",
                "need_buddy": 0,
                "label": main_data.get("participant_name") or main_data.get("email") or main_pid,
            })
        else:
            try:
                main_attendee_pid, _ = get_or_create_participant_from_form(main_attendee_data or {}, email_required=True)
                attendees.append({
                    "participant_id": main_attendee_pid,
                    "role": "main attendee",
                    "need_buddy": 0,
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
            st.error("At least one person in the group must attend.")
            return

        reg_id, skipped = create_group_registration(event_id, main_pid, attendees, channel, source, notes, immediate_checkin)
        if reg_id is None:
            st.warning("No new attendees were added. They may already be registered for this event.")
        else:
            msg = f"Group registration #{reg_id} created with {len(attendees) - len(skipped)} attendee(s)."
            if not main_attends:
                msg += " Registrant is recorded as registered_by, while the separate main attendee is recorded as an attendee."
            if immediate_checkin:
                msg += " Checked in immediately."
            st.success(msg)
        if skipped:
            st.info("Skipped already-registered attendee(s): " + ", ".join(map(str, skipped)))

def checkin_page(event_id):
    st.subheader("Check-In")
    df = attendee_df(event_id)
    if df.empty:
        st.info("No registered attendees yet for this event.")
        return

    q = st.text_input(
        "Search registered attendees",
        placeholder="Type name, email, phone, organization, source, channel, status...",
        help="The table filters as the input changes. In some Streamlit versions, press Enter or leave the field to refresh.",
    )
    filtered = filter_df(df, q)
    total = len(df)
    shown = len(filtered)
    attended = int((df["attendance_status"] == "attended").sum())
    st.caption(f"Showing {shown} of {total} registered attendees • {attended} checked in")

    display = filtered[[
        "name", "email", "phone", "organization", "residence", "role", "registered_by_name", "channel", "source",
        "attendance_status", "checkin_datetime"
    ]].copy()
    display.columns = ["Name", "Email", "Phone", "Organization", "Residence", "Role", "Registered by", "Channel", "Source", "Status", "Check-in time"]
    st.dataframe(display, use_container_width=True, hide_index=True)

    if filtered.empty:
        st.warning("No attendee matches your search.")
        return

    st.markdown("### Selected Attendee")
    options = []
    for _, r in filtered.iterrows():
        options.append(f"{r['name']} | {r['email']} | registration #{r['registration_id']}")
    selected = st.selectbox("Choose participant to update/check in", options)
    selected_reg = int(selected.split("registration #")[-1])
    row = filtered[filtered["registration_id"] == selected_reg].iloc[0]

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("Current status", "Checked in" if row["attendance_status"] == "attended" else "Not checked in")
        c2.metric("Role", row.get("role") or "-")
        c3.metric("Registered by", row.get("registered_by_name") or "-")
        st.caption(f"Channel: {row['channel'] or '-'} · Source: {row['source'] or '-'}")

        with st.form(f"update_attendee_{row['registration_id']}_{row['participant_id']}"):
            st.markdown("#### Update Participant Info")
            a, b = st.columns(2)
            with a:
                name = st.text_input("Participant name *", value=row["name"] or "")
                email = st.text_input("Email *", value=row["email"] or "")
                phone = st.text_input("Phone number", value=row["phone"] or "")
                dob_value = st.date_input("Date of birth", value=dob_to_date(row["dob"]), format="YYYY-MM-DD")
            with b:
                residence = st.text_input("Place of residence", value=row["residence"] or "")
                organization = st.text_input("Organization", value=row["organization"] or "")
                in_groupchat = st.selectbox("In SSC groupchat?", BOOL_OPTIONS, index=BOOL_OPTIONS.index(db_to_bool_label(row["in_groupchat"])))
                have_connect = st.selectbox("Have Connect account?", BOOL_OPTIONS, index=BOOL_OPTIONS.index(db_to_bool_label(row["have_connect"])))
                marketing_subs = st.selectbox("Marketing subscription?", BOOL_OPTIONS, index=BOOL_OPTIONS.index(db_to_bool_label(row["marketing_subs"])))

            col_update, col_checkin = st.columns(2)
            update_clicked = col_update.form_submit_button("Update Participant Info", use_container_width=True)
            checkin_clicked = col_checkin.form_submit_button("Update Info + CHECK-IN", use_container_width=True, disabled=(row["attendance_status"] == "attended"))

        if update_clicked or checkin_clicked:
            if not email or not name:
                st.error("Name and email are required.")
                return
            update_participant_full(row["participant_id"], {
                "participant_name": name,
                "email": email.strip().lower(),
                "phone_number": phone,
                "place_of_residence": residence,
                "dob": dob_value,
                "in_groupchat": bool_to_db(in_groupchat),
                "have_connect": bool_to_db(have_connect),
                "marketing_subs": bool_to_db(marketing_subs),
                "organization": organization,
            })
            if checkin_clicked:
                check_in(row["registration_id"], row["participant_id"])
                st.success("Participant info updated and attendee checked in.")
            else:
                st.success("Participant info updated.")
            st.rerun()

        if row["attendance_status"] == "attended":
            st.success(f"Already checked in at {row['checkin_datetime'] or '-'}")
        else:
            if st.button("CHECK-IN without changing info", key=f"direct_checkin_{row['registration_id']}_{row['participant_id']}", use_container_width=True):
                check_in(row["registration_id"], row["participant_id"])
                st.success("Checked in.")
                st.rerun()


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
    df, total, attended, not_checked, rate = event_metrics(event_id)
    m1, m2, m3, m4 = st.columns(4)
    for col, icon, label, value in [
        (m1, "👥", "Registered", total),
        (m2, "✅", "Checked in", attended),
        (m3, "🕒", "Pending / no-show", not_checked),
        (m4, "📈", "Attendance rate", f"{rate:.0%}"),
    ]:
        col.markdown(f'<div class="kpi-card"><div class="kpi-label">{icon} {label}</div><div class="kpi-value">{value}</div></div>', unsafe_allow_html=True)
    if df.empty:
        return
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Registrations by channel")
        st.bar_chart(df["channel"].fillna("Unknown").value_counts())
    with c2:
        st.markdown("#### Registrations by source")
        st.bar_chart(df["source"].fillna("Unknown").value_counts())
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

    sub_register, sub_import, sub_checkin, sub_dashboard = st.tabs([
        "Registration", "Connect Import", "Check-In", "Dashboard"
    ])
    with sub_register:
        registration_form(event_id)
    with sub_import:
        import_connect(event_id)
    with sub_checkin:
        checkin_page(event_id)
    with sub_dashboard:
        event_dashboard(event_id)

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
        selected_event_label = st.selectbox("Current Event", event_labels)
        selected_event_id = int(selected_event_label.split(" — ")[0].replace("#", ""))
    else:
        st.caption("No events yet")

    st.divider()
    page = st.radio(
        "Navigation",
        ["Home", "Create Event", "Event Workspace"],
        index=0,
    )
    st.divider()
    st.caption(f"🟢 Connected to {DB_PATH.name}")

if page == "Home":
    home_page()
elif page == "Create Event":
    create_event_page()
else:
    event_workspace_page(selected_event_id)