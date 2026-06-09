import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# ----- Config ----- 
DATABASE = "ssc_database.db"
st.set_page_config(page_title="SSC Database", layout="wide")


# ----- Database connection ----- 
def get_conn():
    conn = sqlite3.connect(DATABASE)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


# ----- Backend functions (same as notebook Section 4) ----- 

def get_or_create_location(cursor, conn, location_name, street=None,
                           postal_code=None, city=None, country=None,
                           capacity=None, accessibility_info=None, description=None):
    cursor.execute(
        "SELECT location_id FROM locations WHERE location_name = ?",
        (location_name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute(
        """INSERT INTO locations
           (location_name, street_number, postal_code, city, country,
            capacity_info, accessibility_info, description)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (location_name, street, postal_code, city, country,
         capacity, accessibility_info, description))
    conn.commit()
    return cursor.lastrowid


def get_or_create_participant(cursor, conn, participant_name,
                              email=None, phone_number=None, place_of_residence=None,
                              dob=None, in_groupchat=0, have_connect=0,
                              marketing_subs=0, organization=None):
    if email:
        cursor.execute(
            "SELECT participant_id FROM participants WHERE email = ?",
            (email,))
        row = cursor.fetchone()
        if row:
            return row[0], False  # existing
    cursor.execute(
        """SELECT participant_id FROM participants
           WHERE participant_name = ?
             AND (Phone_Number = ? OR (Phone_Number IS NULL AND ? IS NULL))""",
        (participant_name, phone_number,))
    row = cursor.fetchone()
    if row:
        return row[0], False  # existing
    cursor.execute(
        """INSERT INTO participants
           (participant_name, email, phone_number, place_of_residence, dob,
            in_groupchat, have_connect, marketing_subs, organization)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (participant_name, email, phone_number, place_of_residence, dob,
         in_groupchat, have_connect, marketing_subs, organization))
    conn.commit()
    return cursor.lastrowid, True  # newly created


# ----- Sidebar navigation ----- 
page = st.sidebar.radio(
    "Navigation",
    ["Events", "Register", "Check-in", "Analytics"]
)


# ====================
# PAGE 1: EVENTS
# ====================

if page == "Events":
    st.title("Event Management")

    # ----- View existing events ----- 
    conn = get_conn()
    # visible info per event can be changed upon request (check online_offline)
    df = pd.read_sql("""
        SELECT e.event_id, e.online_offline, e.location_id, e.event_type_id, e.event_name,
               e.start_datetime, e.end_datetime,
               l.location_name, e.age_rating,
               e.price_per_ticket, e.event_description
        FROM event e
        LEFT JOIN location l ON e.location_id = l.location_id
        ORDER BY e.start_datetime
    """, conn)
    st.subheader("Current Events")
    st.dataframe(df, use_container_width=True)

    # ----- Create new event ----- 
    st.subheader("Create New Event")
    with st.form("create_event_form"):
        col1, col2 = st.columns(2)
        with col1:
            ev_name = st.text_input("Event Name")
            ev_type = st.selectbox("Type", ["Nightlife", "Sports", "Dating", "Other"]) # can add more types
            ev_start = st.text_input("Start (YYYY-MM-DD HH:MM)", "2026-07-01 19:00")
            ev_end = st.text_input("End (YYYY-MM-DD HH:MM)", "2026-07-01 23:00")
            ev_price = st.number_input("Price per ticket", min_value=0.0, value=0.0)
        with col2:
            ev_mode = st.selectbox("Mode", ["Offline", "Online"]) # important, check if works
            ev_loc = st.text_input("Location Name (leave blank for online)")
            ev_loc_city = st.text_input("City")
            ev_capacity = st.number_input("Venue Capacity", min_value=0, value=100)
            ev_access = st.multiselect("Accessibility", [
                "Automatic doors", "Low bar", "Elevator",
                "Accessible Toilet", "Low-stimulus rooms",
                "Wheelchair accessible entrance/exit"])

        submitted = st.form_submit_button("Create Event")
        if submitted and ev_name:
            cursor = conn.cursor()
            loc_id = None
            if ev_loc:
                loc_id = get_or_create_location(
                    cursor, conn, ev_loc, city=ev_loc_city,
                    capacity=ev_capacity if ev_capacity > 0 else None)
            cursor.execute(
                """INSERT INTO events
                   (event_name, online_offline, location_id, event_type_id, 
                    start_datetime, end_datetime, price_per_ticket, accessibility)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (ev_name, ev_mode, loc_id, ev_type, ev_start, ev_end, 
                 ev_price, ",".join(ev_access) if ev_access else None))
            conn.commit()
            st.success(f"Event: '{ev_name}' was created!")
            st.rerun()
    conn.close()


# ====================
# PAGE 2: REGISTRATION
# ====================
elif page == "Register":
    st.title("Event Registration")
    conn = get_conn()

    # pick event
    events = pd.read_sql(
        "SELECT event_id, event_name, start_datetime FROM events ORDER BY start_datetime", conn)
    event_options = {f"{r.event_name} ({r.start_datetime})": r.event_id
                     for r in events.itertuples()}
    selected_event = st.selectbox("Select Event", list(event_options.keys()))
    event_id = event_options[selected_event]

    reg_type = st.radio("Registration Type", ["Solo", "Group", "Walk-in"], horizontal=True)
    employee = st.selectbox("Event Registering Employee", ["Employee A", "Employee B", "Employee C"])

    with st.form("registration_form"):
        st.markdown("**Registrant Info**")
        col1, col2 = st.columns(2)
        with col1:
            full_name = st.text_input("Full Name")
            email = st.text_input("Email")
        with col2:
            phone = st.text_input("Phone (optional)")
            need_buddy = st.checkbox("Need a buddy?")
            channel = st.selectbox("Channel", ["Website", "Connect", "App", "Walk-in"])

        # group members section
        guest_names = []
        if reg_type == "Group":
            st.markdown("**Guest Members** (guests can have only name, email, or phone)")
            num_guests = st.number_input("Number of guests", 1, 20, 1)
            for i in range(int(num_guests)):
                g = st.text_input(f"Guest {i+1} name", key=f"guest_{i}")
                guest_names.append(g)

        submitted = st.form_submit_button("Register")
        if submitted and full_name:
            cursor = conn.cursor()
            pid, is_new = get_or_create_participant(
                cursor, conn, participant_name=full_name,
                email=email or None, phone=phone or None)
            status_msg = "New participant created" if is_new else "Existing participant found"
            st.info(status_msg + f" (ID={pid})")

            now = datetime.now().isoformat()
            num_attendees = len(guest_names) + 1 if reg_type == "Group" else 1
            notes = None # can add a text area for notes if needed
            cursor.execute(
                """INSERT INTO event_registration
                   (registered_by, event_id, datetime_registered,
                    number_of_attendees, channel, source, status, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (employee, event_id, now, num_attendees, channel, 'Streamlit', 'Registered', notes))
            reg_id = cursor.lastrowid

            if reg_type == "Group":
                # registrant row
                checkin_dt = now if reg_type == "Walk-in" else None
                attended = 1 if reg_type == "Walk-in" else 0
                cursor.execute(
                    """INSERT INTO event_registered_attendee
                       (registration_id, participant_id, role, need_buddy, attendance_status, 
                       checkin_datetime, payment_status, payment_method)
                       VALUES (?, ?, 'Registrant', ?, ?, ?, ?, ?)""",
                    (reg_id, pid, 'Registrant', int(need_buddy), attended, checkin_dt, None, None))
                # guest rows
                for gn in guest_names:
                    if gn:
                        cursor.execute(
                            """INSERT INTO event_registered_attendee
                               (Registration_id, participant_id, role, need_buddy, attendance_status, 
                                checkin_datetime, payment_status, payment_method)
                               VALUES (?, ?, 'Guest', 0, 0, None, None, None)""",
                            (reg_id, None, 'Guest', 0, 0, None, None, None)) # can add column to add guest names
            else:
                checkin_dt = now if reg_type == "Walk-in" else None
                attended = 1 if reg_type == "Walk-in" else 0
                cursor.execute(
                    """INSERT INTO event_registered_attendee
                       (registration_id, participant_id, role, need_buddy,
                        checkin_datetime, attendance_status)
                       VALUES (?, ?, 'Registrant', ?, ?, ?)""",
                    (reg_id, pid, 'Registrant', int(need_buddy), attended, checkin_dt))

            conn.commit()
            st.success(f"{reg_type} registration created (ID={reg_id})")
    conn.close()


# ====================
# PAGE 3: CHECK-IN
# ====================
elif page == "Check-in":
    st.title("Event Check-in")
    conn = get_conn()

    # select event
    events = pd.read_sql(
        "SELECT event_id, event_name FROM events ORDER BY start_datetime", conn)
    event_options = {r.Event_Name: r.Event_ID for r in events.itertuples()}
    selected = st.selectbox("Select Event", list(event_options.keys()))
    event_id = event_options[selected]

    # search bar (just like the flowchart: search by name, phone, etc.)
    search = st.text_input("Search attendees (name, partial match)") # need to add participant name to one of these tables to make this work

    df = pd.read_sql("""
        SELECT era.registration_id
             , era.participant_id
             , era.role
             , era.need_buddy
             , era.attendance_status
             , era.checkin_datetime
             , er.payment_status
             , er.payment_method
        FROM event_registration_attendee era
        JOIN event_registration er ON era.registration_id = er.registration_id
        WHERE er.event_id = ?
          AND er.registration_status = 'Registered'
          AND era.participant_id IS NOT NULL
        ORDER BY era.attendance_status ASC, era.participant_id
    """, conn, params=(event_id, f"%{search}%"))

    st.subheader(f"Attendees ({len(df)} found)")

    # show stats
    total = len(df)
    checked = int(df["attendance_status"].sum()) if total > 0 else 0
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Expected", total)
    col2.metric("Checked In", checked)
    col3.metric("Remaining", total - checked)

    # check-in buttons for each attendee
    for _, row in df.iterrows():
        col_name, col_role, col_buddy, col_status, col_action = st.columns([3, 1, 1, 1, 2])
        col_name.write(row["participant_id"]) # can join with participant table to show name instead of ID
        col_role.write(row["role"])
        col_buddy.write("Buddy" if row["need_buddy"] else "")

        if row["attendance_status"] == 1:
            col_status.write("Checked in")
        else:
            col_status.write("Not yet")
            if col_action.button("Check in", key=f"checkin_{row['registration_id']}"):
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                cursor.execute(
                    """UPDATE event_registration_attendee
                       SET checkin_datetime = ?, attendance_status = 1
                       WHERE registration_id = ?""",
                    (now, row["registration_id"]))
                conn.commit()
                st.rerun()
    conn.close()


# ====================
# PAGE 4: ANALYTICS
# ====================
elif page == "Analytics":
    st.title("Analytics Dashboard")
    conn = get_conn()

    # ----- KPI row ----- 
    kpis = pd.read_sql("""
        WITH totals AS (
            SELECT COUNT(DISTINCT e.event_id) AS events
                 , COUNT(DISTINCT p.participant_id) AS participants
                 , COUNT(DISTINCT er.registration_id) AS registrations
                 , SUM(CASE WHEN era.attendance_status = 1 THEN 1 ELSE 0 END) AS attended
            FROM events e
            LEFT JOIN event_registration er ON e.event_id = er.event_id
            LEFT JOIN participants p ON er.participant_id = p.participant_id
            LEFT JOIN event_registration_attendee era
                ON er.registration_id = era.registration_id
        )
        SELECT * FROM totals
    """, conn).iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Events", int(kpis["events"]))
    c2.metric("Participants", int(kpis["participants"]))
    c3.metric("Registrations", int(kpis["registrations"]))
    c4.metric("Total Attended", int(kpis["attended"]))

    # ----- Attendance by event ----- 
    st.subheader("Attendance by Event")
    df_att = pd.read_sql("""
        WITH event_att AS (
            SELECT e.event_name
                 , COUNT(era.registration_id) AS Registered
                 , SUM(CASE WHEN era.attendance_status = 1 THEN 1 ELSE 0 END) AS Attended
            FROM events e
            LEFT JOIN event_registration er
                ON e.event_id = er.event_id
               AND er.registration_status = 'Registered'
            LEFT JOIN event_registration_attendee era
                ON er.registration_id = era.registration_id
            GROUP BY e.event_id
        )
        SELECT * FROM event_att
    """, conn)
    st.bar_chart(df_att.set_index("event_name"))

    # ----- Revenue ----- 
    st.subheader("Revenue & Budget")
    df_rev = pd.read_sql("""
        WITH ticket_counts AS (
            SELECT er.event_id
                 , COUNT(era.registration_id) AS Tickets
            FROM event_registration er
            JOIN event_registration_attendee era
                ON er.registration_id = era.registration_id
            WHERE er.registration_status = 'Registered'
            GROUP BY er.event_id
        )
        SELECT e.event_name
             , ROUND(e.price_per_ticket * COALESCE(tc.Tickets, 0), 2) AS Revenue
             , e.event_estimated_cost AS Est_Cost
             , ROUND(e.price_per_ticket * COALESCE(tc.Tickets, 0)
                     - COALESCE(e.event_estimated_cost, 0), 2) AS Est_Profit
             , RANK() OVER (ORDER BY (e.price_per_ticket * COALESCE(tc.Tickets, 0)
                             - COALESCE(e.event_estimated_cost, 0)) DESC
               ) AS Rank
        FROM events e
        LEFT JOIN ticket_counts tc ON e.event_id = tc.event_id
        ORDER BY Rank
    """, conn)
    st.dataframe(df_rev, use_container_width=True)

    # ----- Channel effectiveness -----
    st.subheader("Registration Channels")
    df_ch = pd.read_sql("""
        SELECT er.channel
             , COUNT(*) AS Registrations
             , ROUND(100.0 * COUNT(*)
                     / SUM(COUNT(*)) OVER (), 1) AS Share_Pct
        FROM event_registration er
        GROUP BY er.channel
        ORDER BY Registrations DESC
    """, conn)
    st.dataframe(df_ch, use_container_width=True)

    # ----- Participant engagement -----
    st.subheader("Participant Engagement")
    df_eng = pd.read_sql("""
        WITH pstats AS (
            SELECT p.participant_name
                 , COUNT(DISTINCT CASE WHEN er.status = 'Registered' THEN er.Event_ID END) AS Active_Events
                 , SUM(CASE WHEN er.status = 'Cancelled' THEN 1 ELSE 0 END) AS Cancellations
            FROM participants p
            LEFT JOIN event_registration er ON p.participant_id = er.participant_id
            GROUP BY p.participant_id
        )
                         
        SELECT participant_name AS Name
             , Active_Events
             , Cancellations
             , DENSE_RANK() OVER (ORDER BY Active_Events DESC) AS Rank
        FROM pstats
        ORDER BY Rank
    """, conn)
    st.dataframe(df_eng, use_container_width=True)

    conn.close()