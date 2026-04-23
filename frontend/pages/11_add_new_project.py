"""
Page 11 — Add New Project.

Flat intake form: fill in client, project, and project codes in one place.
On submit the DB creates any missing client record, the project, and all
project codes in the correct tables automatically.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import backend.db as db
from shared.config import TEMPLATES_DIR

if not st.session_state.get("authenticated", False):
    st.warning("Please sign in from the Home page.")
    st.stop()

st.title("Add New Project")
st.caption(
    "Fill in client, project, and project codes in one form. "
    "If the client already exists (matched by name) its existing record is used. "
    "If the project name already exists under that client it is also reused. "
    "Only genuinely new records are created."
)

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _templates() -> list[str]:
    return sorted(
        f.replace(".docx", "")
        for f in os.listdir(TEMPLATES_DIR)
        if f.endswith(".docx") and not f.startswith("filled")
    )


PROJECT_STATUSES = ["Active", "On Hold", "Completed", "Prospect"]

# Initialise session state for dynamic project-code rows
st.session_state.setdefault("_np_codes", [{"suffix": "", "name": "", "budget": 0.0,
                                            "date_start": "", "date_end": "", "status": "Active"}])
st.session_state.setdefault("_np_result", None)

# ------------------------------------------------------------------
# Section 1 — Client
# ------------------------------------------------------------------

st.subheader("1. Client")

existing_clients = db.get_clients()
client_names = [c.name for c in existing_clients]

client_mode = st.radio("Client", ["Select existing client", "Create new client"],
                       horizontal=True, label_visibility="collapsed")

if client_mode == "Select existing client":
    sel_name = st.selectbox("Client name", client_names)
    sel_client = next(c for c in existing_clients if c.name == sel_name)
    c_name            = sel_client.name
    c_name_for_inv    = sel_client.name_for_invoices
    c_code            = sel_client.client_code
    c_vat             = sel_client.vat_number
    st.info(
        f"Code: **{c_code or '—'}** | Invoice name: **{c_name_for_inv or '—'}** | "
        f"VAT: **{c_vat or '—'}**"
    )
else:
    col1, col2 = st.columns(2)
    c_name         = col1.text_input("Client name *", placeholder="Internal reference (e.g. ERGO)")
    c_name_for_inv = col2.text_input("Name for invoices *", placeholder="Legal name on invoices")
    col3, col4 = st.columns(2)
    c_code         = col3.text_input("Client code", placeholder="e.g. 0478ERG78")
    c_vat          = col4.text_input("VAT number",  placeholder="e.g. EL123456789")

st.divider()

# ------------------------------------------------------------------
# Section 2 — Project
# ------------------------------------------------------------------

st.subheader("2. Project")

col1, col2 = st.columns(2)
p_name   = col1.text_input("Project name *", placeholder="e.g. IFRS17 - P3")
p_desc   = col2.text_input("Description",    placeholder="Short description")
col3, col4, col5 = st.columns(3)
p_vat    = col3.number_input("VAT %", min_value=0.0, max_value=100.0, value=19.0, step=1.0)
templates = _templates()
p_tmpl   = col4.selectbox("Invoice Template", templates,
                           index=templates.index("template1_v3") if "template1_v3" in templates else 0)
p_status = col5.selectbox("Status", PROJECT_STATUSES)

st.divider()

# ------------------------------------------------------------------
# Section 3 — Project Codes
# ------------------------------------------------------------------

st.subheader("3. Project Codes")
st.caption(
    "Add one row per billing sub-line (client suffix). "
    "Leave **Date Start** blank for a first-time suffix. "
    "Set **Date Start** only when reusing a suffix that was previously used for another project — "
    "time entries on or after that date will be routed to this project."
)

codes = st.session_state["_np_codes"]

# Dynamic add / remove rows
col_add, col_remove, _ = st.columns([1, 1, 6])
if col_add.button("+ Add row"):
    codes.append({"suffix": "", "name": "", "budget": 0.0,
                  "date_start": "", "date_end": "", "status": "Active"})
    st.rerun()
if col_remove.button("- Remove last row") and len(codes) > 1:
    codes.pop()
    st.rerun()

# Header
hcols = st.columns([1.2, 2, 1.2, 1.5, 1.5, 1.5])
for label, col in zip(["Suffix *", "Name", "Budget (€)", "Date Start", "Date End", "Status"], hcols):
    col.markdown(f"**{label}**")

for i, row in enumerate(codes):
    rcols = st.columns([1.2, 2, 1.2, 1.5, 1.5, 1.5])
    row["suffix"]     = rcols[0].text_input("", value=row["suffix"],     key=f"cs_{i}",
                                             placeholder="01", label_visibility="collapsed")
    row["name"]       = rcols[1].text_input("", value=row["name"],       key=f"cn_{i}",
                                             placeholder="e.g. PM workstream", label_visibility="collapsed")
    row["budget"]     = rcols[2].number_input("", value=row["budget"],   key=f"cb_{i}",
                                               min_value=0.0, step=1000.0, label_visibility="collapsed")
    row["date_start"] = rcols[3].text_input("", value=row["date_start"], key=f"cds_{i}",
                                             placeholder="YYYY-MM-DD", label_visibility="collapsed")
    row["date_end"]   = rcols[4].text_input("", value=row["date_end"],   key=f"cde_{i}",
                                             placeholder="YYYY-MM-DD", label_visibility="collapsed")
    row["status"]     = rcols[5].selectbox("", ["Active", "On Hold", "Completed"], key=f"cst_{i}",
                                            label_visibility="collapsed")

st.divider()

# ------------------------------------------------------------------
# Validation & Submit
# ------------------------------------------------------------------

if st.button("Import to Database", type="primary"):
    errors = []
    if not c_name.strip():
        errors.append("Client name is required.")
    if client_mode == "Create new client" and not c_name_for_inv.strip():
        errors.append("Name for invoices is required when creating a new client.")
    if not p_name.strip():
        errors.append("Project name is required.")
    valid_codes = [r for r in codes if r["suffix"].strip()]
    if not valid_codes:
        errors.append("At least one project code (suffix) is required.")
    for r in valid_codes:
        if r["date_start"].strip() and len(r["date_start"].strip()) != 10:
            errors.append(f"Suffix '{r['suffix']}': Date Start must be YYYY-MM-DD or blank.")
        if r["date_end"].strip() and len(r["date_end"].strip()) != 10:
            errors.append(f"Suffix '{r['suffix']}': Date End must be YYYY-MM-DD or blank.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        created = {"client": False, "project": False, "codes": []}
        try:
            # 1. Client
            client_id = db.add_client(
                name=c_name.strip(),
                name_for_invoices=c_name_for_inv.strip() or c_name.strip(),
                client_code=c_code.strip(),
                vat_number=c_vat.strip(),
            )
            existing_match = next((c for c in existing_clients if c.name == c_name.strip()), None)
            created["client"] = existing_match is None

            # 2. Project
            project_id = db.add_project(
                client_id=client_id,
                name=p_name.strip(),
                description=p_desc.strip(),
                vat_pct=p_vat,
                template=p_tmpl,
                status=p_status,
            )

            # Check if project already existed
            existing_projects = db.get_projects(client_id=client_id)
            existing_proj = next((p for p in existing_projects if p.name == p_name.strip()), None)
            created["project"] = existing_proj is None or existing_proj.id == project_id

            # 3. Project codes
            for r in valid_codes:
                new_id = db.add_project_code(
                    project_id=project_id,
                    client_suffix=r["suffix"].strip(),
                    name=r["name"].strip(),
                    description="",
                    budget_amount=r["budget"],
                    status=r["status"],
                    date_start=r["date_start"].strip(),
                    date_end=r["date_end"].strip(),
                )
                created["codes"].append((r["suffix"].strip(), new_id))

            st.session_state["_np_result"] = {"success": True, "created": created,
                                               "client_name": c_name.strip(),
                                               "project_name": p_name.strip()}
            # Reset code rows
            st.session_state["_np_codes"] = [{"suffix": "", "name": "", "budget": 0.0,
                                               "date_start": "", "date_end": "", "status": "Active"}]
            st.rerun()

        except Exception as exc:
            st.error(f"Import failed: {exc}")

# ------------------------------------------------------------------
# Result banner
# ------------------------------------------------------------------

if result := st.session_state.pop("_np_result", None):
    if result.get("success"):
        c = result["created"]
        lines = []
        if c["client"]:
            lines.append(f"New client **{result['client_name']}** created.")
        else:
            lines.append(f"Existing client **{result['client_name']}** used.")
        if c["project"]:
            lines.append(f"New project **{result['project_name']}** created.")
        else:
            lines.append(f"Existing project **{result['project_name']}** used.")
        lines.append(f"{len(c['codes'])} project code(s) added: " +
                     ", ".join(s for s, _ in c["codes"]))
        st.success("  \n".join(lines))
