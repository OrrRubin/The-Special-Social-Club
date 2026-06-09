"""
ui_helpers.py  --  reusable Streamlit widgets shared by the admin page.

These are the "Lego bricks". Build each tab of the admin page out of them so
you write the pattern once and reuse it five times.

  require_login()   Phase 1/4 - sidebar password gate, returns (operator, role).
  editable_table()  Phase 2/3 - turns any table into an edit-in-place grid with
                                a confirm-twice delete. Works with single OR
                                composite primary keys.
  export_buttons()  Phase 4   - CSV + Excel download for whatever is on screen.
  safe_autorefresh()Phase 4   - re-runs a live page every N seconds if the
                                optional package is installed; otherwise no-op.
"""

import hashlib
import io

import pandas as pd
import streamlit as st


# ---------------------------------------------------------------------------
# Phase 1/4 : authentication + roles
# ---------------------------------------------------------------------------
def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def require_login():
    """Block the page until a valid operator signs in.

    Credentials live in .streamlit/secrets.toml as:

        [operators]
        alice = { password_sha256 = "<hash>", role = "operator" }
        bob   = { password_sha256 = "<hash>", role = "viewer" }

    Returns (operator_name, role). role is "operator" (can write) or
    "viewer" (read-only). The page uses the role to disable editing.
    """
    if "operator" in st.session_state:
        return st.session_state["operator"], st.session_state["role"]

    st.title("SSC Admin — sign in")
    operators = st.secrets.get("operators", {})

    name = st.text_input("Operator name")
    pw = st.text_input("Password", type="password")
    if st.button("Sign in", type="primary"):
        record = operators.get(name)
        if record and _hash(pw) == record.get("password_sha256"):
            st.session_state["operator"] = name
            st.session_state["role"] = record.get("role", "operator")
            st.rerun()
        else:
            st.error("Invalid name or password.")
    st.stop()  # nothing below renders until logged in


def logout_button():
    if st.sidebar.button("Sign out"):
        for k in ("operator", "role"):
            st.session_state.pop(k, None)
        st.rerun()


# ---------------------------------------------------------------------------
# Phase 4 : live refresh (optional dependency)
# ---------------------------------------------------------------------------
def safe_autorefresh(seconds=5, key="live"):
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=seconds * 1000, key=key)
    except Exception:
        # Package not installed -> give a manual button instead.
        if st.button("🔄 Refresh", key=f"{key}_btn"):
            st.rerun()


# ---------------------------------------------------------------------------
# Phase 4 : export
# ---------------------------------------------------------------------------
def export_buttons(df: pd.DataFrame, basename: str):
    if df is None or df.empty:
        return
    c1, c2 = st.columns(2)
    c1.download_button(
        "⬇️ CSV", df.to_csv(index=False).encode("utf-8"),
        file_name=f"{basename}.csv", mime="text/csv", use_container_width=True,
    )
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="data")
    c2.download_button(
        "⬇️ Excel", buf.getvalue(),
        file_name=f"{basename}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


# ---------------------------------------------------------------------------
# Phase 2/3 : the generic editable table
# ---------------------------------------------------------------------------
def _rowkey(row, pk_cols):
    return "||".join(str(row[c]) for c in pk_cols)


def editable_table(label, rows, pk_col, editable_cols, on_save,
                   on_delete=None, column_config=None, can_write=True):
    """Render `rows` (list of dicts) as an edit-in-place grid.

    Parameters
    ----------
    label         : section heading.
    rows          : list of dicts (e.g. repo.get_locations()).
    pk_col        : str OR list of str. The primary key column(s).
    editable_cols : columns the operator may change. Everything else is locked.
    on_save       : callback(pk_value, changes_dict). pk_value is a single value
                    for a simple key, or a tuple for a composite key.
    on_delete     : callback(pk_value) or None to hide delete.
    column_config : optional dict passed to st.data_editor (dropdowns etc.).
    can_write     : if False (viewer role) the grid is read-only.
    """
    st.markdown(f"#### {label}")
    df = pd.DataFrame(rows)
    if df.empty:
        st.caption("No rows.")
        return

    pk_cols = [pk_col] if isinstance(pk_col, str) else list(pk_col)
    export_buttons(df, label.lower().replace(" ", "_"))

    locked = [c for c in df.columns if c not in editable_cols] if can_write else list(df.columns)
    edited = st.data_editor(
        df,
        key=f"editor_{label}",
        hide_index=True,
        num_rows="fixed",            # operators edit existing rows; new rows go through app.py forms
        disabled=locked,
        column_config=column_config or {},
        use_container_width=True,
    )

    if can_write:
        # ---- detect and save row-level changes -------------------------
        original_by_key = {_rowkey(r, pk_cols): r for r in rows}
        saved = 0
        for _, erow in edited.iterrows():
            key = _rowkey(erow, pk_cols)
            orig = original_by_key.get(key)
            if orig is None:
                continue
            changes = {}
            for col in editable_cols:
                new_val = erow[col]
                old_val = orig.get(col)
                # treat NaN/None equivalently to avoid false "changes"
                if pd.isna(new_val) and (old_val is None or pd.isna(old_val)):
                    continue
                if new_val != old_val:
                    changes[col] = None if pd.isna(new_val) else new_val
            if changes:
                pk_value = erow[pk_cols[0]] if len(pk_cols) == 1 else tuple(erow[c] for c in pk_cols)
                on_save(pk_value, changes)
                saved += 1
        if saved:
            st.toast(f"Saved {saved} change(s).", icon="✅")
            st.rerun()

        # ---- confirm-twice delete --------------------------------------
        if on_delete is not None:
            st.markdown("**Delete a row**")
            options = ["—"] + [_rowkey(r, pk_cols) for r in rows]
            choice = st.selectbox("Pick the row's key", options, key=f"del_sel_{label}")
            confirm_key = f"confirm_{label}"
            if choice != "—":
                if st.button(f"Delete {choice}", key=f"del_btn_{label}"):
                    st.session_state[confirm_key] = choice
                if st.session_state.get(confirm_key) == choice:
                    st.warning(f"This will remove **{choice}**. Click confirm to proceed.")
                    if st.button("✅ Confirm delete", key=f"del_yes_{label}", type="primary"):
                        pk_value = choice if len(pk_cols) == 1 else tuple(choice.split("||"))
                        on_delete(pk_value)
                        st.session_state.pop(confirm_key, None)
                        st.toast("Deleted.", icon="🗑️")
                        st.rerun()
