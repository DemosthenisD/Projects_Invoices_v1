# InvoiceApp — Data Dependencies & Setup Order

## Table Dependencies

```
clients
  └── projects
        └── project_codes   ← time entries MUST match here before import
              ├── time_entries
              ├── invoice_allocations
              └── write_offs
        └── invoices
              └── invoice_allocations
        └── pipeline

consultant_groups  (auto-created when time entries are imported)
  └── consultant_profiles
        ├── annual_salary_history
        └── review_scores

billing_basis  (derived from time_entries + write_offs)
```

**Hard blocks** — these will silently skip or error without the prerequisite:

| Action | What must exist first |
|---|---|
| Import timesheet CSV | `project_codes` matching every `client_code + client_suffix` in the file |
| Add project code (page 6) | `clients` + `projects` |
| Create invoice allocation | `project_codes` |
| Write-off (project-level) | `projects` + `time_entries` |
| Consultant profile (page 13) | `consultant_groups` (auto-populated by timesheet import) |
| Annual review (page 14) | `consultant_profiles` + ideally `billing_basis` |
| Billing basis auto-tab (page 12) | `time_entries` |

---

## Recommended Setup Order

**Step 1 — Clients** (page 3 or 11)
No dependencies. Everything else flows from here.

**Step 2 — Projects** (page 3 or 11)
Requires clients. Page 11 ("Add New Project") can create both client and project in one form.

**Step 3 — Project Codes** (page 6 or 11)
Requires projects. These are the codes that timesheet rows match against — this step must come before any CSV import.

**Step 4 — Import Timesheets** (page 7)
Requires project codes. Automatically creates consultant_groups as a side effect.

**Step 5 — Consultant Profiles** (page 13)
Optional. Requires that timesheet import has already run (so consultant_groups are populated).

**Step 6 — Billing Basis** (page 12)
Optional. Uses time entries to auto-aggregate charges. Required for productivity bonus in annual reviews.

**Step 7 — Generate Invoices** (page 0)
Requires clients; optionally project codes for allocation.

**Step 8 — Write-offs** (page 8)
Requires projects + time entries.

**Step 9 — Annual Reviews** (page 14)
Requires consultant profiles + billing basis.

---

## On the Auto-Creation Idea

You raised a good point: when importing a timesheet, if an unrecognised `client_code + suffix` is encountered, the app could auto-create a placeholder project code rather than silently skipping rows. That is implementable — but it would require knowing which `project_id` to attach the new code to, and since the CSV doesn't carry that, the user would have to map it. It is probably cleaner to enforce **Step 3 before Step 4** and keep the current validation, now that the leading-zero bug is fixed.
