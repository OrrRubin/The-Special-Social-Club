"""
pages/1_Manage_Data.py  --  the new ADMIN page.

Streamlit automatically discovers any *.py file inside a `pages/` folder and
adds it to the sidebar navigation. Because of that, this page appears ALONGSIDE
your original app.py WITHOUT a single edit to app.py. Operators use app.py for
the day-to-day flow (register, check-in, dashboard) and this page when they need
to fix or remove data.

This page is pure wiring: it pulls reads from repo, hands them to the generic
editable_table widget, and points each grid's save/delete at the matching repo
function. Dropdowns are built from the allowed-value lists in repo so an operator
can never enter a value the database's CHECK constraints would reject.
"""

import streamlit as st

import repo
from ui_helpers import (
    require_login, logout_button, editable_table, export_buttons, safe_autorefresh,
)

st.set_page_config(page_title="SSC · Manage Data", page_icon="🛠️", layout="wide")

# --- Phase 1: gate the whole page -----------------------------------------
operator, role = require_login()
can_write = role == "operator"
st.sidebar.success(f"Signed in as {operator} ({role})")
logout_button()

st.title("🛠️ Manage Data")
st.caption(
    "Edit cells directly, then click outside the cell to save. "
    "Deletions ask for confirmation. Use **Audit / Undo** to reverse a mistake."
)
if not can_write:
    st.info("You are signed in as a viewer. Editing and deleting are disabled.")

tabs = st.tabs(
    ["Events", "Locations", "Event types", "People", "Registrations", "Audit / Undo"]
)

# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------
with tabs[0]:
    editable_table(
        "Events",
        repo.get_events(),
        pk_col="event_id",
        editable_cols=[
            "event_name", "location_id", "event_type_id",
            "start_datetime", "end_datetime", "age_rating",
            "price_per_ticket", "event_description",
        ],
        on_save=lambda pk, ch: repo.update_event(pk, ch, operator),
        on_delete=lambda pk: repo.soft_delete_event(pk, operator),
        column_config={
            "location_id": st.column_config.SelectboxColumn(
                "location_id", options=[l["location_id"] for l in repo.get_locations()]),
            "event_type_id": st.column_config.SelectboxColumn(
                "event_type_id", options=[t["etype_id"] for t in repo.get_event_types()]),
            "price_per_ticket": st.column_config.NumberColumn("price_per_ticket", min_value=0.0),
        },
        can_write=can_write,
    )

# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------
with tabs[1]:
    editable_table(
        "Locations",
        repo.get_locations(),
        pk_col="location_id",
        editable_cols=[
            "location_name", "street_number", "postal_code", "city",
            "country", "capacity_info", "accessibility_info", "description",
        ],
        on_save=lambda pk, ch: repo.update_location(pk, ch, operator),
        on_delete=lambda pk: repo.soft_delete_location(pk, operator),
        can_write=can_write,
    )

# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------
with tabs[2]:
    editable_table(
        "Event types",
        repo.get_event_types(),
        pk_col="etype_id",
        editable_cols=["etype_name", "description"],
        on_save=lambda pk, ch: repo.update_event_type(pk, ch, operator),
        on_delete=lambda pk: repo.soft_delete_event_type(pk, operator),
        can_write=can_write,
    )

# ---------------------------------------------------------------------------
# People (participants)
# ---------------------------------------------------------------------------
with tabs[3]:
    st.caption(
        "Boolean fields (groupchat / connect / marketing) are shown read-only "
        "here to protect the 'unknown' state; change them through the "
        "registration screens in the main app."
    )
    editable_table(
        "People",
        repo.get_participants(),
        pk_col="participant_id",
        editable_cols=[
            "participant_name", "email", "phone_number",
            "place_of_residence", "dob", "organization",
        ],
        on_save=lambda pk, ch: repo.update_participant(pk, ch, operator),
        on_delete=lambda pk: repo.soft_delete_participant(pk, operator),
        can_write=can_write,
    )

# ---------------------------------------------------------------------------
# Registrations (+ nested attendees)
# ---------------------------------------------------------------------------
with tabs[4]:
    editable_table(
        "Registrations",
        repo.get_registrations(),
        pk_col="registration_id",
        editable_cols=["channel", "source", "status", "notes"],
        on_save=lambda pk, ch: repo.update_registration(pk, ch, operator),
        on_delete=lambda pk: repo.delete_registration(pk, operator),
        column_config={
            "channel": st.column_config.SelectboxColumn("channel", options=repo.CHANNELS),
            "status": st.column_config.SelectboxColumn("status", options=repo.REG_STATUS),
        },
        can_write=can_write,
    )

    st.divider()
    st.markdown("#### Attendees of a registration")
    regs = repo.get_registrations()
    if regs:
        label_by_id = {
            r["registration_id"]: f"#{r['registration_id']} · {r['event_name']} · by {r['registered_by_name']}"
            for r in regs
        }
        chosen = st.selectbox(
            "Choose a registration", list(label_by_id),
            format_func=lambda x: label_by_id[x],
        )
        editable_table(
            f"Attendees of #{chosen}",
            repo.get_attendees(chosen),
            pk_col=["registration_id", "participant_id"],   # composite key
            editable_cols=["role", "attendance_status", "need_buddy",
                           "payment_status", "payment_method"],
            on_save=lambda pk, ch: repo.update_attendee(pk[0], pk[1], ch, operator),
            on_delete=lambda pk: repo.delete_attendee(pk[0], pk[1], operator),
            column_config={
                "role": st.column_config.SelectboxColumn("role", options=repo.ROLES),
                "attendance_status": st.column_config.SelectboxColumn(
                    "attendance_status", options=repo.ATTENDANCE),
                "payment_status": st.column_config.SelectboxColumn(
                    "payment_status", options=repo.PAYMENT_STATUS),
                "payment_method": st.column_config.SelectboxColumn(
                    "payment_method", options=repo.PAYMENT_METHOD),
            },
            can_write=can_write,
        )

# ---------------------------------------------------------------------------
# Audit / Undo
# ---------------------------------------------------------------------------
with tabs[5]:
    st.markdown("#### Recent changes")
    safe_autorefresh(seconds=8, key="audit_live")
    audit = repo.get_audit(100)
    export_buttons(__import__("pandas").DataFrame(audit), "audit_log")
    st.dataframe(audit, use_container_width=True, hide_index=True)

    st.divider()
    if can_write:
        st.markdown("#### Undo the last change")
        st.caption("Reverses the most recent edit or soft-delete. Hard-deleted "
                   "registrations are kept in the log for manual restore.")
        if st.button("↩️ Undo last action", type="primary"):
            msg = repo.undo_last_action(operator)
            st.success(msg)
            st.rerun()
