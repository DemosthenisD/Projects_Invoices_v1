"""
Excel import / export utilities.

import_from_excel() — one-time migration from the legacy Excel workbook into SQLite.
export_to_excel()   — write all SQLite tables back to a multi-sheet .xlsx.

Run standalone to trigger the import:
    python backend/excel_io.py
"""
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.config import DB_PATH, LEGACY_EXCEL
import backend.db as db


def import_from_excel(excel_path: str | None = None) -> None:
    """
    Read the legacy InvoiceLogTemplate Excel workbook and populate SQLite.
    Safe to re-run — INSERT OR IGNORE prevents duplicate rows.
    """
    path = excel_path or LEGACY_EXCEL
    if not os.path.exists(path):
        print(f"Excel file not found: {path}")
        return

    db.init_db()
    xl = pd.ExcelFile(path)

    # --- Clients & Addresses from Client_List ---
    if "Client_List" in xl.sheet_names:
        df_clients = xl.parse("Client_List")
        for _, row in df_clients.iterrows():
            client_name = str(row.get("Client", "")).strip()
            address = str(row.get("Address", "")).strip()
            if not client_name or client_name == "nan":
                continue
            client_id = db.add_client(client_name)
            if address and address != "nan":
                db.add_address(client_id, address)
        print(f"  Imported {len(df_clients)} client/address rows from Client_List")

    # --- Clients & Projects from Project_List ---
    if "Project_List" in xl.sheet_names:
        df_proj = xl.parse("Project_List")
        for _, row in df_proj.iterrows():
            client_name = str(row.get("Client", "")).strip()
            if not client_name or client_name == "nan":
                continue

            # Ensure client exists with richer metadata
            name_for_inv = str(row.get("Client Name (for Invoices)", client_name)).strip()
            client_code = str(row.get("client_code", "")).strip()
            if client_code == "nan":
                client_code = ""

            client_id = db.add_client(
                client_name,
                name_for_invoices=name_for_inv if name_for_inv != "nan" else client_name,
                client_code=client_code,
            )

            project_name = str(row.get("Project", "")).strip()
            if not project_name or project_name == "nan":
                continue

            description = str(row.get("description", "")).strip()
            if description == "nan":
                description = ""

            try:
                vat_pct = float(row.get("VAT %", 19.0))
            except (ValueError, TypeError):
                vat_pct = 19.0

            template = str(row.get("Invoice Template", "template1_v3")).strip()
            if template == "nan":
                template = "template1_v3"

            db.add_project(
                client_id=client_id,
                name=project_name,
                description=description,
                vat_pct=vat_pct,
                template=template,
            )
        print(f"  Imported {len(df_proj)} project rows from Project_List")

    # --- Invoices from InvoiceLogTemplate ---
    if "InvoiceLogTemplate" in xl.sheet_names:
        df_inv = xl.parse("InvoiceLogTemplate")
        count = 0
        for _, row in df_inv.iterrows():
            client_name = str(row.get("Client", "")).strip()
            if not client_name or client_name == "nan":
                continue

            client = db.get_client_by_name(client_name)
            if client is None:
                # Create a minimal client entry if not already present
                client_id = db.add_client(client_name)
            else:
                client_id = client.id

            invoice_number = str(row.get("Invoice No", "")).strip()
            if not invoice_number or invoice_number == "nan":
                continue

            try:
                year = int(row.get("Year", 0))
            except (ValueError, TypeError):
                year = 0

            date_val = row.get("Date", "")
            if hasattr(date_val, "strftime"):
                date_str = date_val.strftime("%Y-%m-%d")
            else:
                date_str = str(date_val).strip()
                if date_str == "nan":
                    date_str = ""

            try:
                amount = float(row.get("Amount", 0))
            except (ValueError, TypeError):
                amount = 0.0

            try:
                vat_pct = float(row.get("VAT %", 19.0))
            except (ValueError, TypeError):
                vat_pct = 19.0

            try:
                vat_amount = float(row.get("VAT Amount", 0))
            except (ValueError, TypeError):
                vat_amount = round(amount * vat_pct / 100, 2)

            try:
                expenses_net = float(row.get("Expenses Net Amount", 0))
            except (ValueError, TypeError):
                expenses_net = 0.0

            try:
                expenses_vat = float(row.get("Expenses VAT Amount", 0))
            except (ValueError, TypeError):
                expenses_vat = 0.0

            project_name = str(row.get("Project", "")).strip()
            if project_name == "nan":
                project_name = ""

            description = str(row.get("description", "")).strip()
            if description == "nan":
                description = ""

            address = str(row.get("Address", "")).strip()
            if address == "nan":
                address = ""

            template = str(row.get("Invoice Template", "")).strip()
            if template == "nan":
                template = ""

            db.add_invoice(
                client_id=client_id,
                invoice_number=invoice_number,
                year=year,
                date=date_str,
                amount=amount,
                vat_amount=vat_amount,
                vat_pct=vat_pct,
                address=address,
                project_name=project_name,
                description=description,
                template=template,
                expenses_net=expenses_net,
                expenses_vat=expenses_vat,
            )
            count += 1

        print(f"  Imported {count} invoice rows from InvoiceLogTemplate")

    print("Import complete.")


def export_to_excel(output_path: str) -> None:
    """
    Export all SQLite data to a multi-sheet Excel file.
    Suitable for ad-hoc analysis or backup.
    """
    import pandas as pd

    # Clients
    clients = db.get_clients()
    clients_data = [
        {
            "Client": c.name,
            "Client Name (for Invoices)": c.name_for_invoices,
            "client_code": c.client_code,
            "VAT Number": c.vat_number,
        }
        for c in clients
    ]

    # Addresses
    all_addresses = []
    for c in clients:
        for addr in db.get_addresses(c.id):
            all_addresses.append({"Client": c.name, "Address": addr.address})

    # Projects
    all_projects = []
    for c in clients:
        for p in db.get_projects(client_id=c.id):
            all_projects.append(
                {
                    "Client": c.name,
                    "Project": p.name,
                    "description": p.description,
                    "VAT %": p.vat_pct,
                    "Invoice Template": p.template,
                    "Status": p.status,
                }
            )

    # Invoices
    invoices = db.get_invoices()
    # Build client id→name map
    client_map = {c.id: c.name for c in clients}
    inv_data = [
        {
            "Year": i.year,
            "Invoice No": i.invoice_number,
            "Date": i.date,
            "Client": client_map.get(i.client_id, ""),
            "Address": i.address,
            "Amount": i.amount,
            "VAT %": i.vat_pct,
            "VAT Amount": i.vat_amount,
            "Project": i.project_name,
            "description": i.description,
            "Invoice Template": i.template,
            "Format": i.format,
            "Expenses Net Amount": i.expenses_net,
            "Expenses VAT Amount": i.expenses_vat,
        }
        for i in invoices
    ]

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame(clients_data).to_excel(writer, sheet_name="Client_List", index=False)
        pd.DataFrame(all_addresses).to_excel(writer, sheet_name="Address_List", index=False)
        pd.DataFrame(all_projects).to_excel(writer, sheet_name="Project_List", index=False)
        pd.DataFrame(inv_data).to_excel(writer, sheet_name="InvoiceLogTemplate", index=False)

    print(f"Exported to: {output_path}")


if __name__ == "__main__":
    print(f"Importing from: {LEGACY_EXCEL}")
    import_from_excel()
    print(f"Database: {DB_PATH}")
