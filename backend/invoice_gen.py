"""
Invoice generation: DOCX template filling and PDF conversion via ConvertAPI.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from docx import Document
from shared.config import TEMPLATES_DIR, EXPORTS_DIR, CONVERT_API_KEY


def fill_placeholders(doc: Document, data: dict) -> None:
    """Replace {{KEY}} tokens in all paragraphs and table cells."""
    tokens = {f"{{{{{k}}}}}": str(v) for k, v in data.items()}

    def _replace_in_paragraph(para) -> None:
        for key, value in tokens.items():
            if key in para.text:
                for run in para.runs:
                    if key in run.text:
                        run.text = run.text.replace(key, value)

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
    year = data.get("Year", "")
    invoice_no = data.get("Invoice_No", "")
    client_code = data.get("Client_Code", data.get("Client", "")).replace(" ", "_")
    filename = f"{year}_{invoice_no}_{client_code}_Invoice.docx"
    docx_path = os.path.join(EXPORTS_DIR, filename)
    doc.save(docx_path)
    return docx_path


def convert_to_pdf(docx_path: str) -> str:
    """
    Convert a DOCX file to PDF using ConvertAPI.

    Returns the path of the saved PDF file.
    """
    import convertapi

    convertapi.api_credentials = CONVERT_API_KEY
    pdf_path = docx_path.replace(".docx", ".pdf")
    result = convertapi.convert("pdf", {"File": docx_path}, from_format="docx")
    result.save_files(pdf_path)
    return pdf_path
