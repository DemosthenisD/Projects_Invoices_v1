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
    template_used: str = ""   # actual template used when generating (historical record)
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


@dataclass
class ProjectCode:
    id: int
    project_id: int
    client_code: str
    client_suffix: str
    name: str = ""
    description: str = ""
    budget_amount: float = 0.0
    status: str = "Active"
    date_start: str = ""   # YYYY-MM-DD; '' means no lower bound (original use of this suffix)
    date_end: str = ""     # YYYY-MM-DD; '' means open-ended
    created_at: str = ""


@dataclass
class TimeEntry:
    id: int
    period: str           # yyyymm e.g. '202206'
    emp_nbr: str
    consultant: str
    client_code: str
    client_suffix: str
    total_hours: float
    non_z_hours: float
    z_hours: float
    total_charges: float
    non_z_charges: float
    z_charges: float
    project_code_id: int = 0
    project_id: int = 0
    description: str = ""
    batch_ref: str = ""
    created_at: str = ""


@dataclass
class InvoiceAllocation:
    id: int
    invoice_id: int
    project_code_id: int
    amount: float           # net amount (excl. VAT) allocated to this project code
    created_at: str = ""


@dataclass
class WriteOff:
    id: int
    project_id: int
    amount: float
    reason: str
    notes: str = ""
    project_code_id: int = 0
    emp_nbr: str = ""
    consultant: str = ""
    allocation_type: str = "project"  # 'project' (pro-rata) | 'adhoc'
    reversed: int = 0
    reversed_reason: str = ""
    reversed_at: str = ""
    created_at: str = ""
