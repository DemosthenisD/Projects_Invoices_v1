"""
Invoice generation: DOCX template filling and PDF conversion via ConvertAPI.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from docx import Document
from shared.config import TEMPLATES_DIR, EXPORTS_DIR, CONVERT_API_KEY


def fill_placeholders(doc: Document, data: dict) -> None:
    """Replace {{KEY}} tokens in all paragraphs and table cells.

    Handles tokens split across multiple runs by consolidating the full
    paragraph text, replacing, then writing back to the first run.
    """
    tokens = {f"{{{{{k}}}}}": str(v) for k, v in data.items()}

    def _replace_in_paragraph(para) -> None:
        full_text = para.text
        if not any(key in full_text for key in tokens):
            return
        if not para.runs:
            return
        new_text = full_text
        for key, value in tokens.items():
            new_text = new_text.replace(key, value)
        para.runs[0].text = new_text
        for run in para.runs[1:]:
            run.text = ""

    for para in doc.paragraphs:
        _replace_in_paragraph(para)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    _replace_in_paragraph(para)


def generate_invoice(data: dict, template_name: str, fmt: str = "PDF") -> str:
    """
    Fill the named DOCX template with data and save to exports/.

    Returns the path of the saved DOCX file.
    data keys should match the {{PLACEHOLDER}} names in the template.
    """
    template_path = os.path.join(TEMPLATES_DIR, f"{template_name}.docx")
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found: {template_path}")

    doc = Document(template_path)
    fill_placeholders(doc, data)

    os.makedirs(EXPORTS_DIR, exist_ok=True)
    year = data.get("placeholder6", "")
    invoice_no = data.get("placeholder5", "")
    client_code = data.get("placeholder1", "").replace(" ", "_")
    filename = f"{year}_{invoice_no}_{client_code}_Invoice.docx"
    docx_path = os.path.join(EXPORTS_DIR, filename)
    doc.save(docx_path)
    return docx_path


def convert_to_pdf(docx_path: str) -> str:
    """
    Convert a DOCX file to PDF using ConvertAPI.

    Returns the path of the saved PDF file.
    """
    import requests
    import urllib3
    import convertapi

    # Set both attributes: api_secret (v1.5.x) and api_credentials (v1.7+).
    convertapi.api_secret = CONVERT_API_KEY
    convertapi.api_credentials = CONVERT_API_KEY

    pdf_path = docx_path.replace(".docx", ".pdf")

    # Corporate SSL-inspection proxies present certs signed by an internal CA
    # that Python's ssl module can't verify. Disable verification only for
    # these convertapi calls (local app — no user data in transit).
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    _orig = requests.Session.request

    def _no_ssl(self, *args, **kwargs):
        kwargs["verify"] = False
        return _orig(self, *args, **kwargs)

    requests.Session.request = _no_ssl
    try:
        result = convertapi.convert("pdf", {"File": docx_path}, from_format="docx")
        # save_files expects a directory; it returns the list of saved paths.
        saved = result.save_files(os.path.dirname(pdf_path))
        if not saved:
            raise RuntimeError("ConvertAPI returned no output files")
        # Rename to our expected filename if ConvertAPI used a different name.
        if saved[0] != pdf_path:
            import shutil
            shutil.move(saved[0], pdf_path)
    finally:
        requests.Session.request = _orig  # always restore

    return pdf_path
