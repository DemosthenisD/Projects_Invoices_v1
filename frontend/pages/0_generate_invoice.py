"""
Page 0 — Generate Invoice.

Flow:
  1. Select client  → address and VAT number auto-fill
  2. Select project → description and template auto-fill
  3. Enter amount and date → invoice number auto-suggested
  4. Generate DOCX / PDF → download → save record to DB
"""
import sys
import os
from datetime import date as date_type

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import backend.db as db
from backend.invoice_gen import generate_invoice, convert_to_pdf
from shared.ui import require_auth, list_templates

require_auth()

# Reset each render; re-set below only when allocations are entered and balance.
st.session_state.pop("_inv_allocations", None)

# ------------------------------------------------------------------
# Page setup
# ------------------------------------------------------------------

st.title("Generate Invoice")

# ------------------------------------------------------------------
# Load reference data (cached for the session)
# ------------------------------------------------------------------

@st.cache_data(ttl=300)
def _clients():
    return db.get_clients()


@st.cache_data(ttl=300)
def _addresses(client_id: int):
    return db.get_addresses(client_id)


@st.cache_data(ttl=300)
def _projects(client_id: int, include_completed: bool = False):
    if include_completed:
        return [p for p in db.get_projects(client_id=client_id)
                if p.status in ("Active", "Completed", "On Hold")]
    return db.get_projects(client_id=client_id, status="Active")


@st.cache_data(ttl=300)
def _all_projects(include_completed: bool = False):
    if include_completed:
        return [p for p in db.get_projects()
                if p.status in ("Active", "Completed", "On Hold")]
    return db.get_projects(status="Active")




# ------------------------------------------------------------------
# Selection mode
# ------------------------------------------------------------------

col_type, col_mode, col_comp = st.columns([2, 3, 2])
doc_type = col_type.radio(
    "Document type",
    ["Invoice", "Credit Note"],
    horizontal=True,
    help="Credit Notes are stored with negative amounts and negate a previously issued invoice.",
)
selection_mode = col_mode.radio(
    "Start from:",
    ["Client → Project", "Project → Client"],
    horizontal=True,
)
include_completed = col_comp.checkbox(
    "Include completed projects",
    value=False,
    help="Show Active, On Hold, and Completed projects (not just Active).",
)

if doc_type == "Credit Note":
    st.info(
        "**Credit Note mode** — enter the amount to be credited (positive). "
        "It will be stored as a negative amount. Assign the same project as the original invoice."
    )
    related_invoice_number = st.text_input(
        "Original Invoice No (optional)",
        placeholder="e.g. 12/2026",
        help="Reference to the invoice being credited. For record-keeping only.",
    )
else:
    related_invoice_number = ""

all_clients = _clients()
if not all_clients:
    st.error("No clients found. Add clients in the Clients & Projects page first.")
    st.stop()

# ------------------------------------------------------------------
# Step 1 — Client or Project (depending on mode)
# ------------------------------------------------------------------

if selection_mode == "Project → Client":
    all_projs = _all_projects(include_completed)
    if not all_projs:
        st.error("No active projects found.")
        st.stop()
    client_by_id = {c.id: c for c in all_clients}
    proj_labels = [
        f"{client_by_id[p.client_id].name} — {p.name}"
        if p.client_id in client_by_id else p.name
        for p in all_projs
    ]
    selected_label = st.selectbox("Project", proj_labels)
    project = all_projs[proj_labels.index(selected_label)]
    client = client_by_id[project.client_id]
    selected_project_name = project.name
    st.caption(f"Client auto-selected: **{client.name}**")
else:
    # Client → Project: type filter then client dropdown
    CLIENT_TYPES = ["All", "managed", "external", "internal"]
    type_filter = st.radio(
        "Client type", CLIENT_TYPES, horizontal=True, index=1,
        help="Filter the client list by type before selecting.",
    )
    if type_filter == "All":
        clients = all_clients
    else:
        clients = [c for c in all_clients if c.client_type == type_filter]

    if not clients:
        st.info(f"No {type_filter} clients found.")
        st.stop()

    client_names = [c.name for c in clients]
    selected_client_name = st.selectbox("Client", client_names)
    client = next(c for c in clients if c.name == selected_client_name)

    projects = _projects(client.id, include_completed)
    project_names = [p.name for p in projects] if projects else []

    if project_names:
        selected_project_name = st.selectbox("Project", project_names)
        project = next(p for p in projects if p.name == selected_project_name)
    else:
        st.info("No active projects for this client.")
        selected_project_name = st.text_input("Project name", value="")
        project = None

col1, col2 = st.columns(2)

with col1:
    addresses = _addresses(client.id)
    address_options = [
        "\n".join(line.rstrip() for line in a.address.splitlines())
        for a in addresses
    ]
    if address_options:
        address = st.selectbox("Address", address_options)
    else:
        address = st.text_input("Address", placeholder="Enter billing address")

with col2:
    vat_no = st.text_input("Client VAT No", value=client.vat_number or "")

# ------------------------------------------------------------------
# Step 2 — Defaults from project
# ------------------------------------------------------------------

if project:
    default_description = project.description
    default_vat_pct = project.vat_pct
    default_template = project.template
else:
    default_description = ""
    default_vat_pct = 0.0
    default_template = "template1_v3"

description = st.text_area("Description (shown on invoice)", value=default_description, height=80)
comment = st.text_input("Internal comment (not shown on invoice)", placeholder="e.g. PO reference, notes for accounting…")

col1, col2 = st.columns(2)
with col1:
    vat_pct = st.number_input("VAT %", min_value=0.0, max_value=100.0,
                               value=float(default_vat_pct or 0.0), step=1.0)
with col2:
    available_templates = list_templates()
    template_index = (
        available_templates.index(default_template)
        if default_template and default_template in available_templates
        else 0
    )
    template_name = st.selectbox("Invoice Template", available_templates, index=template_index)

# ------------------------------------------------------------------
# Step 3 — Amount, Date, Invoice ID
# ------------------------------------------------------------------

col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

with col1:
    invoice_date = st.date_input("Invoice Date", value=date_type.today(),
                                  help="Date will appear on the invoice as DD/MM/YYYY.")
    year = invoice_date.year

with col2:
    amount = st.number_input("Amount (net, €)", min_value=0.0, step=100.0)

with col3:
    suggested_no = db.get_next_invoice_number(year)
    invoice_number = st.text_input(
        "Invoice ID",
        value=str(suggested_no),
        help="Sequential log counter per year. Auto-suggested; override if needed.",
    )

with col4:
    invoice_ref = f"{invoice_number}/{year}"
    st.text_input(
        "Invoice No (on invoice)",
        value=invoice_ref,
        disabled=True,
        help="This is how the Invoice No will appear on the invoice document.",
    )

vat_amount = round(amount * vat_pct / 100, 2)
gross = round(amount + vat_amount, 2)

st.markdown(
    f"**VAT ({vat_pct:.0f}%):** €{vat_amount:,.2f} &nbsp;|&nbsp; "
    f"**Gross:** €{gross:,.2f}"
)

# ------------------------------------------------------------------
# Step 3b — Project Code Allocation (optional)
# ------------------------------------------------------------------

if project and amount > 0:
    codes = db.get_project_codes(project_id=project.id, status="Active")
    if codes:
        with st.expander("Project Code Allocation (optional)", expanded=False):
            st.caption(
                "Allocate this invoice's net amount across project codes. "
                "Leave all amounts at 0 to use automatic **pro-rata by budget** allocation."
            )
            alloc_inputs = {}
            total_budget = sum(c.budget_amount for c in codes)
            for c in codes:
                prorata = (
                    round(amount * c.budget_amount / total_budget, 2)
                    if total_budget > 0
                    else round(amount / len(codes), 2)
                )
                label = f"{c.client_code}-{c.client_suffix}" + (f" | {c.name}" if c.name else "")
                hint  = f"pro-rata: €{prorata:,.2f}" if c.budget_amount else "pro-rata: equal split"
                alloc_inputs[c.id] = st.number_input(
                    label, min_value=0.0, step=100.0, value=0.0,
                    help=hint, key=f"alloc_{c.id}"
                )
            total_alloc = sum(alloc_inputs.values())
            if total_alloc > 0:
                diff = round(amount - total_alloc, 2)
                if abs(diff) > 0.01:
                    st.warning(f"Allocations sum to €{total_alloc:,.2f} — must equal net amount €{amount:,.2f} (difference: €{diff:,.2f}).")
                else:
                    st.success(f"Allocations balance: €{total_alloc:,.2f} ✓")
                    st.session_state["_inv_allocations"] = [
                        {"project_code_id": cid, "amount": amt}
                        for cid, amt in alloc_inputs.items() if amt > 0
                    ]
            else:
                st.session_state.pop("_inv_allocations", None)
                st.info("No manual allocation entered — pro-rata by budget will be applied automatically.")

# ------------------------------------------------------------------
# Step 4 — Format & Generate
# ------------------------------------------------------------------

with st.expander("Advanced"):
    fmt = st.radio("Output format", ["PDF", "DOCX"], horizontal=True)
    expenses_net = st.number_input("Expenses (net, €)", min_value=0.0, step=10.0)
    expenses_vat = st.number_input("Expenses VAT (€)", min_value=0.0, step=1.0)

st.divider()

col_gen, col_save = st.columns([1, 3])
generate_clicked = col_gen.button("Generate Invoice", type="primary")
st.caption(
    "Clicking **Generate Invoice** creates the DB record and saves the file to the `exports/` folder "
    "(e.g. `exports/2025_42_ClientName_Invoice.pdf`). "
    "The **Download** button that appears after is a convenience copy — "
    "the file is already saved locally even if you do not click Download."
)

if generate_clicked:
    if not amount:
        st.error("Amount must be greater than zero.")
        st.stop()

    # Credit notes: flip sign so stored amounts are negative
    signed_amount     = -round(amount, 2)     if doc_type == "Credit Note" else round(amount, 2)
    signed_vat        = -round(vat_amount, 2) if doc_type == "Credit Note" else round(vat_amount, 2)
    signed_exp_net    = -round(expenses_net, 2)  if doc_type == "Credit Note" else round(expenses_net, 2)
    signed_exp_vat    = -round(expenses_vat, 2)  if doc_type == "Credit Note" else round(expenses_vat, 2)

    total_net     = round(signed_amount + signed_exp_net, 2)
    total_vat     = round(signed_vat + signed_exp_vat, 2)
    invoice_total = round(total_net + total_vat, 2)

    # Template placeholder mapping (all templates use {{placeholderN}} keys):
    # placeholder1 = client name, 2 = address, 3 = client VAT no,
    # 4 = date, 5 = invoice no, 6 = year (v1/v2 templates only),
    # 7 = description, 8 = net fee, 9 = VAT fee,
    # 8_Exp/9_Exp = expenses, 8_Tot/9_Tot = totals, 10 = invoice total
    data = {
        "placeholder1":    client.name_for_invoices or client.name,
        "placeholder2":    address,
        "placeholder3":    vat_no,
        "placeholder4":    invoice_date.strftime("%d/%m/%Y"),
        "placeholder5":    invoice_ref,
        "placeholder6":    str(year),
        "placeholder7":    description or selected_project_name,
        "placeholder8":    f"{signed_amount:,.2f}",
        "placeholder9":    f"{signed_vat:,.2f}",
        "placeholder8_Exp": f"{signed_exp_net:,.2f}",
        "placeholder9_Exp": f"{signed_exp_vat:,.2f}",
        "placeholder8_Tot": f"{total_net:,.2f}",
        "placeholder9_Tot": f"{total_vat:,.2f}",
        "placeholder10":   f"{invoice_total:,.2f}",
    }

    with st.spinner("Generating document…"):
        try:
            docx_path = generate_invoice(data, template_name, fmt)
        except FileNotFoundError as e:
            st.error(str(e))
            st.stop()

        output_path = docx_path
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        if fmt == "PDF":
            try:
                output_path = convert_to_pdf(docx_path)
                mime = "application/pdf"
            except Exception as e:
                st.error(f"PDF conversion failed: {e}")
                st.stop()

    # Save record to DB
    project_id = project.id if project else 0
    db.add_invoice(
        client_id=client.id,
        invoice_number=invoice_number,
        year=year,
        date=invoice_date.isoformat(),
        amount=signed_amount,
        vat_amount=signed_vat,
        vat_pct=vat_pct,
        project_id=project_id,
        address=address,
        project_name=selected_project_name,
        description=description,
        template_used=template_name,
        fmt=fmt,
        file_path=output_path,
        expenses_net=signed_exp_net,
        expenses_vat=signed_exp_vat,
        allocations=st.session_state.get("_inv_allocations") or None,
        comment=comment,
        doc_type=doc_type,
        related_invoice_number=related_invoice_number,
    )
    st.session_state.pop("_inv_allocations", None)

    with open(output_path, "rb") as f:
        file_bytes = f.read()

    file_ext = "pdf" if fmt == "PDF" else "docx"
    download_name = f"{year}_{invoice_number}_{client.client_code or client.name}_Invoice.{file_ext}"

    st.success(f"{doc_type} generated and saved. Invoice No {invoice_ref} (ID: {invoice_number}) — {client.name}")
    st.download_button(
        label=f"Download {fmt}",
        data=file_bytes,
        file_name=download_name,
        mime=mime,
    )
