"""
One-time script: build template1_v4.docx and template2_v4.docx from the v3 originals.

Changes vs v3:
- Drawn boxes (mc:AlternateContent/w:drawing rectangles in para[10]) are removed.
- Paragraphs 10-15 (tab-spaced placeholder layout) are replaced with a proper
  3-column table:
    Col 1 (boxed): client name, address, client VAT
    Col 2 (spacer): blank, no borders
    Col 3 (boxed): Date, Invoice No, Milliman VAT
  Table cells auto-grow to fit content — no more text overflow.
"""
import os, shutil
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")

SOLID = {"val": "single", "sz": 12, "color": "000000"}   # 1.5pt black
NONE  = {"val": "none",   "sz": "0",  "color": "auto"}


def _border_el(side, spec):
    el = OxmlElement(f"w:{side}")
    el.set(qn("w:val"),   spec.get("val", "none"))
    el.set(qn("w:sz"),    str(spec.get("sz", 0)))
    el.set(qn("w:space"), "0")
    el.set(qn("w:color"), spec.get("color", "auto"))
    return el


def make_cell(col_width_dxa, lines, boxed=True):
    tc = OxmlElement("w:tc")

    # tcPr
    tcPr = OxmlElement("w:tcPr")
    tcW = OxmlElement("w:tcW")
    tcW.set(qn("w:w"), str(col_width_dxa))
    tcW.set(qn("w:type"), "dxa")
    tcPr.append(tcW)

    # borders
    tcBorders = OxmlElement("w:tcBorders")
    border_spec = SOLID if boxed else NONE
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tcBorders.append(_border_el(side, border_spec if side in ("top","left","bottom","right") else NONE))
    tcPr.append(tcBorders)

    # padding: 60 dxa (~1 mm) on all sides
    tcMar = OxmlElement("w:tcMar")
    for side in ("top", "left", "bottom", "right"):
        m = OxmlElement(f"w:{side}")
        m.set(qn("w:w"), "60")
        m.set(qn("w:type"), "dxa")
        tcMar.append(m)
    tcPr.append(tcMar)
    tc.append(tcPr)

    for idx, line in enumerate(lines):
        p = OxmlElement("w:p")
        pPr = OxmlElement("w:pPr")
        spacing = OxmlElement("w:spacing")
        spacing.set(qn("w:before"), "40" if idx == 0 else "0")
        spacing.set(qn("w:after"),  "40" if idx == len(lines) - 1 else "0")
        pPr.append(spacing)
        p.append(pPr)
        if line:
            r = OxmlElement("w:r")
            t = OxmlElement("w:t")
            t.text = line
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            r.append(t)
            p.append(r)
        tc.append(p)

    return tc


def build_v4(tmpl_in, tmpl_out):
    import tempfile, io
    src = os.path.join(TEMPLATES_DIR, tmpl_in)
    dst = os.path.join(TEMPLATES_DIR, tmpl_out)
    shutil.copy2(src, dst)

    doc = Document(dst)
    body = doc.element.body
    children = list(body)

    # 1. Strip <w:drawing> elements from para[10] (the two drawn rectangles)
    para10 = children[10]
    for drawing in para10.findall(".//" + qn("w:drawing")):
        drawing.getparent().remove(drawing)

    # 2. Read the Milliman VAT text from para[14] (kept verbatim, e.g. "VAT: 10260287O")
    milliman_vat = "".join(
        r.text or "" for r in children[14].iter(qn("w:t"))
    ).strip()

    # 3. Remove paras 10-15 from body
    for i in range(10, 16):
        body.remove(children[i])

    # 4. Insertion anchor: new children[9] = blank para before where boxes were
    anchor = list(body)[9]

    # 5. Build table
    # Widths (DXA = twentieths of a point):  Left=5450  Spacer=280  Right=3670
    tbl = OxmlElement("w:tbl")

    tblPr = OxmlElement("w:tblPr")
    tblStyle = OxmlElement("w:tblStyle")
    tblStyle.set(qn("w:val"), "TableNormal")
    tblPr.append(tblStyle)
    tblW = OxmlElement("w:tblW")
    tblW.set(qn("w:w"), "9400")
    tblW.set(qn("w:type"), "dxa")
    tblPr.append(tblW)
    # Suppress all table-level borders (cell-level borders take precedence)
    tblBorders = OxmlElement("w:tblBorders")
    for side in ("top","left","bottom","right","insideH","insideV"):
        tblBorders.append(_border_el(side, NONE))
    tblPr.append(tblBorders)
    tbl.append(tblPr)

    tblGrid = OxmlElement("w:tblGrid")
    for w in (5450, 280, 3670):
        gc = OxmlElement("w:gridCol")
        gc.set(qn("w:w"), str(w))
        tblGrid.append(gc)
    tbl.append(tblGrid)

    tr = OxmlElement("w:tr")
    tr.append(make_cell(5450,
        ["{{placeholder1}}", "{{placeholder2}}", "VAT: {{placeholder3}}"],
        boxed=True))
    tr.append(make_cell(280, [""], boxed=False))
    tr.append(make_cell(3670,
        ["Date: {{placeholder4}}", "Invoice No: {{placeholder5}}", milliman_vat],
        boxed=True))
    tbl.append(tr)

    # 6. Insert table + spacing blank para after anchor
    anchor.addnext(tbl)
    blank = OxmlElement("w:p")
    tbl.addnext(blank)

    # Save to a BytesIO buffer then write to disk (avoids ZipFile locking on Windows paths)
    buf = io.BytesIO()
    doc.save(buf)
    with open(dst, "wb") as f:
        f.write(buf.getvalue())
    print(f"Saved {dst}")


if __name__ == "__main__":
    build_v4("template1_v3.docx", "template1_v4.docx")
    build_v4("template2_v3.docx", "template2_v4.docx")
    print("Done.")
