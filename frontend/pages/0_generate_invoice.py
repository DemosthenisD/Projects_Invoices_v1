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
from shared.config import CONVERT_API_KEY

# ------------------------------------------------------------------
# Auth guard
# ------------------------------------------------------------------

if not st.session_state.get("authenticated", False):
    st.warning("Please sign in from the Home page.")
    st.stop()

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
def _projects(client_id: int):
    return db.get_projects(client_id=client_id, status="Active")


@st.cache_data(ttl=300)
def _available_templates():
    from shared.config import TEMPLATES_DIR
    files = [
        f.replace(".docx", "")
        for f in os.listdir(TEMPLATES_DIR)
        if f.endswith(".docx") and not f.startswith("filled")
    ]
    return sorted(files)


# ------------------------------------------------------------------
# Step 1 — Client
# ------------------------------------------------------------------

clients = _clients()
if not clients:
    st.error("No clients found. Add clients in the Clients & Projects page first.")
    st.stop()

client_names = [c.name for c in clients]
selected_client_name = st.selectbox("Client", client_names)
client = next(c for c in clients if c.name == selected_client_name)

col1, col2 = st.columns(2)

with col1:
    addresses = _addresses(client.id)
    address_options = [a.address for a in addresses]
    if address_options:
        address = st.selectbox("Address", address_options)
    else:
        address = st.text_input("Address", placeholder="Enter billing address")

with col2:
    vat_no = st.text_input("Client VAT No", value=client.vat_number or "")

# ------------------------------------------------------------------
# Step 2 — Project
# ------------------------------------------------------------------

projects = _projects(client.id)
project_names = [p.name for p in projects] if projects else []

if project_names:
    selected_project_name = st.selectbox("Project", project_names)
    project = next(p for p in projects if p.name == selected_project_name)
    default_description = project.description
    default_vat_pct = project.vat_pct
    default_template = project.template
else:
    st.info("No active projects for this client. Description, VAT and template will use defaults.")
    selected_project_name = st.text_input("Project name", value="")
    project = None
    default_description = ""
    default_vat_pct = 19.0
    default_template = "template1_v3"

description = st.text_area("Description", value=default_description, height=80)

col1, col2 = st.columns(2)
with col1:
    vat_pct = st.number_input("VAT %", min_value=0.0, max_value=100.0,
                               value=float(default_vat_pct), step=1.0)
with col2:
    available_templates = _available_templates()
    template_index = (
        available_templates.index(default_template)
        if default_template in available_templates
        else 0
    )
    template_name = st.selectbox("Invoice Template", available_templates, index=template_index)

# ------------------------------------------------------------------
# Step 3 — Amount, Date, Invoice Number
# ------------------------------------------------------------------

col1, col2, col3 = st.columns(3)

with col1:
    invoice_date = st.date_input("Invoice Date", value=date_type.today())
    year = invoice_date.year

with col2:
    amount = st.number_input("Amount (net, €)", min_value=0.0, step=100.0)

with col3:
    suggested_no = db.get_next_invoice_number(year)
    invoice_number = st.text_input("Invoice No", value=str(suggested_no))

vat_amount = round(amount * vat_pct / 100, 2)
gross = round(amount + vat_amount, 2)

st.markdown(
    f"**VAT ({vat_pct:.0f}%):** €{vat_amount:,.2f} &nbsp;|&nbsp; "
    f"**Gross:** €{gross:,.2f}"
)

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

if generate_clicked:
    if not amount:
        st.error("Amount must be greater than zero.")
        st.stop()

    total_net   = round(amount + expenses_net, 2)
    total_vat   = round(vat_amount + expenses_vat, 2)
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
        "placeholder5":    invoice_number,
        "placeholder6":    str(year),
        "placeholder7":    description or selected_project_name,
        "placeholder8":    f"{amount:,.2f}",
        "placeholder9":    f"{vat_amount:,.2f}",
        "placeholder8_Exp": f"{expenses_net:,.2f}",
        "placeholder9_Exp": f"{expenses_vat:,.2f}",
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
            if not CONVERT_API_KEY:
                st.error("ConvertAPI key not configured. Add CONVERT_API_KEY to secrets.toml.")
                st.stop()
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
        amount=amount,
        vat_amount=vat_amount,
        vat_pct=vat_pct,
        project_id=project_id,
        address=address,
        project_name=selected_project_name,
        description=description,
        template=template_name,
        fmt=fmt,
        file_path=output_path,
        expenses_net=expenses_net,
        expenses_vat=expenses_vat,
    )

    # Invalidate invoice number cache so next suggestion is correct
    db.get_next_invoice_number.cache_clear() if hasattr(db.get_next_invoice_number, "cache_clear") else None

    with open(output_path, "rb") as f:
        file_bytes = f.read()

    file_ext = "pdf" if fmt == "PDF" else "docx"
    download_name = f"{year}_{invoice_number}_{client.client_code or client.name}_Invoice.{file_ext}"

    st.success(f"Invoice generated and saved. Invoice #{invoice_number} — {client.name}")
    st.download_button(
        label=f"Download {fmt}",
        data=file_bytes,
        file_name=download_name,
        mime=mime,
    )
