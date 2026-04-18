from dataclasses import dataclass, field


@dataclass
class Client:
    id: int
    name: str                    # Internal reference name (e.g. "Ethniki CY")
    name_for_invoices: str       # Formal name on invoice documents
    client_code: str = ""        # Short code (e.g. "ETN")
    vat_number: str = ""         # Client's VAT registration number
    created_at: str = ""


@dataclass
class Address:
    id: int
    client_id: int
    address: str


@dataclass
class Project:
    id: int
    client_id: int
    name: str
    description: str = ""
    vat_pct: float = 19.0
    template: str = "template1_v3"
    status: str = "Active"


@dataclass
class Invoice:
    id: int
    client_id: int
    invoice_number: str
    year: int
    date: str
    amount: float
    vat_amount: float
    project_id: int = 0
    vat_pct: float = 19.0
    address: str = ""
    project_name: str = ""
    description: str = ""
    template: str = ""
    format: str = "PDF"
    file_path: str = ""
    expenses_net: float = 0.0
    expenses_vat: float = 0.0
    created_at: str = ""


@dataclass
class PipelineEntry:
    id: int
    project_id: int
    stage: str = "Prospect"      # Prospect / Active / On Hold / Completed
    value: float = 0.0
    notes: str = ""
    updated_at: str = ""
