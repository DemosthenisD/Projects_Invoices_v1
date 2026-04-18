# InvoiceApp

Personal invoice management tool built with Streamlit and SQLite.

## Setup

```bash
pip install -r requirements.txt
```

Copy `.streamlit/secrets.toml.example` (or create `.streamlit/secrets.toml`) and fill in:

```toml
username = "Demosthenis"
password = "your-password"
CONVERT_API_KEY = "your-convertapi-secret"
```

## Running the app

**Must be run from the repo root:**

```bash
streamlit run frontend/App.py
```

The app opens at http://localhost:8501.

## Running tests

```bash
python -m pytest tests/ -v
```

## Pages

| Page | Description |
|------|-------------|
| Generate Invoice | Fill client/project details, generate DOCX or PDF invoice |
| Invoice Log | Browse, filter, and download past invoices; export to Excel |
| Clients & Projects | CRUD for clients, projects, and billing addresses |
| Pipeline / CRM | Track project pipeline stages and deal values |
| Dashboard | Revenue charts, VAT summary, YTD vs prior year |

## Notes

- Database is stored at `data/invoiceapp.db` (excluded from git)
- Generated invoices are saved to `exports/` (excluded from git)
- PDF conversion uses [ConvertAPI](https://www.convertapi.com/) — requires a valid API key
- The corporate SSL proxy at Milliman requires the ConvertAPI call to run with SSL verification disabled (already handled in `backend/invoice_gen.py`)
