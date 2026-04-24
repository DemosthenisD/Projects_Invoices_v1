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


# ---------------------------------------------------------------------------
# HR / Review models (Sprint 10)
# ---------------------------------------------------------------------------

MILLIMAN_STATUSES = [
    "Analyst",
    "Consultant",
    "Recognised Professional",
    "Approved Professional",
    "Signature Authority",
    "Principal - Signature Authority",
]

EXTERNAL_LEVELS = [
    "Analyst",
    "Junior Consultant",
    "Consultant",
    "Senior Consultant",
    "Manager",
    "Senior Manager",
    "Principal",
]

# Performance review score groups and their sub-items (used by pages 13 & 14)
SCORE_GROUPS: dict[str, list[str]] = {
    "Professionalism": [
        "Deliverance assignments",
        "Modelling skills",
        "Problem solving",
        "Reporting skills",
        "Presentations skills",
        "Project management",
        "Innovation",
    ],
    "Management": [
        "Chargeability",
        "Acquisition capability",
        "Leverage (# colleagues)",
        "Internal network",
        "Visibility in the market",
        "Recruitment efforts",
    ],
    "Social Skills": [
        "Managing expectations",
        "Client satisfaction",
        "Teamwork",
        "Developing people",
        "Communication",
    ],
}


@dataclass
class ConsultantProfile:
    id: int
    emp_nbr: str
    employment_date: str = ""        # YYYY-MM-DD
    prior_exp_years: float = 0.0     # years of experience before joining Milliman
    milliman_status: str = ""        # e.g. "Approved Professional"
    external_level: str = ""         # e.g. "Senior Consultant"
    languages: str = ""              # free text e.g. "Greek (A), English (A)"
    tools: str = ""                  # free text e.g. "Prophet (B), VBA (A)"
    current_role: str = ""           # e.g. "Consultant"
    notes: str = ""
    created_at: str = ""


@dataclass
class AnnualSalaryHistory:
    id: int
    emp_nbr: str
    year: int
    starting_salary: float = 0.0        # carried from prior year's updated_salary
    exams_passed: float = 0.0           # can be fractional (e.g. 1.5)
    exam_raise_per_exam: float = 1000.0  # £/exam — resettable each year
    other_raise: float = 0.0            # discretionary raise £
    effective_date: str = ""            # YYYY-MM-DD — date salary change takes effect
    objective_bonus_pct: float = 0.0    # manager-entered % e.g. 0.07 for 7%
    bonus_paid: float = 0.0             # actual bonus paid (historical record)
    proposed_rate: float = 0.0          # proposed new hourly billing rate
    notes: str = ""


@dataclass
class BillingBasis:
    id: int
    emp_nbr: str
    year: int
    source: str = "manual"           # 'time_tracking' or 'manual'
    billed: float = 0.0
    capped_paid_prebill: float = 0.0
    capped_unpaid_prebill: float = 0.0
    charged_off: float = 0.0
    paid: float = 0.0
    unbilled: float = 0.0
    hourly_rate: float = 0.0          # used to convert £ basis → equivalent hours
    notes: str = ""
    created_at: str = ""


@dataclass
class ReviewScore:
    id: int
    emp_nbr: str
    year: int
    score_group: str   # 'Professionalism' / 'Management' / 'Social Skills'
    item_name: str
    score: float = 0.0
